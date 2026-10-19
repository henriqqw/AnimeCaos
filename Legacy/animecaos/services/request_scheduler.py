"""Priority scheduler that turns bursts of per-item lookups into batches.

The old code dispatched one worker per item — per history entry, per search
result, per watchlist anime, per hovered card — straight onto the global
QThreadPool (whose max thread count was never configured, so 8-16 ran at
once). Each of those workers then blocked inside the rate limiter *while
holding its pool slot*, so an unrelated action like loading an episode
queued behind a cover-fetch storm.

This scheduler fixes both halves of that:

**Coalescing.** Lookups submitted close together accumulate in a pending
buffer for a short window, then flush as ONE batched request:

    hover card A ─┐
    hover card B ─┼─ 120ms window ─> 1 request (aliases a0..a2)
    hover card C ─┘

Sweeping the mouse across a row of 20 cards used to cost 20-40 requests. It
now costs one or two, and most of those are cache hits anyway.

**Priority + bounded concurrency.** A dedicated 3-worker pool, separate
from the global QThreadPool, so API work can never starve playback or
episode loading again. FOREGROUND work (the user is waiting) jumps ahead of
PREFETCH (speculative), and PREFETCH is dropped outright when the user
navigates away rather than being carried out pointlessly.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

from animecaos.services.anilist_client import AniListClient, ApiResult, ApiStatus
from animecaos.services.rate_limiter import Priority

log = logging.getLogger(__name__)

MAX_WORKERS = 3
COALESCE_SECONDS = 0.12

MediaCallback = Callable[[str, dict | None, ApiResult], None]


class RequestScheduler:
    def __init__(
        self,
        client: AniListClient,
        *,
        max_workers: int = MAX_WORKERS,
        coalesce: float = COALESCE_SECONDS,
    ) -> None:
        self._client = client
        self._coalesce = coalesce
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="anilist"
        )
        # title -> callbacks waiting on it, bucketed by priority so a
        # foreground request for a title already queued as prefetch gets
        # promoted rather than duplicated.
        self._pending: dict[Priority, dict[str, list[MediaCallback]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._cv = threading.Condition()
        self._stopping = False
        self._flusher = threading.Thread(
            target=self._flush_loop, name="anilist-coalescer", daemon=True
        )
        self._flusher.start()

    # ── Public API ───────────────────────────────────────────────────
    def submit_media(
        self,
        title: str,
        callback: MediaCallback,
        *,
        priority: Priority = Priority.VISIBLE,
    ) -> None:
        """Request one title's media record; the result arrives via
        `callback`. Calls made within the coalescing window are merged into
        a single batched request."""
        if not title:
            return
        with self._cv:
            if self._stopping:
                return
            # Already queued at a higher (or equal) priority? Just attach.
            for existing in sorted(self._pending.keys()):
                if existing <= priority and title in self._pending[existing]:
                    self._pending[existing][title].append(callback)
                    self._cv.notify()
                    return
            # Queued at a lower priority — promote it, carrying its
            # callbacks along so the user-initiated request isn't stuck
            # behind speculative work.
            for existing in list(self._pending.keys()):
                if existing > priority and title in self._pending[existing]:
                    waiting = self._pending[existing].pop(title)
                    self._pending[priority][title].extend(waiting)
                    break
            self._pending[priority][title].append(callback)
            self._cv.notify()

    def run(
        self,
        fn: Callable[..., Any],
        *args: Any,
        priority: Priority = Priority.FOREGROUND,
        **kwargs: Any,
    ) -> Future:
        """Run arbitrary work on the bounded API pool (page queries and
        other things that don't batch)."""
        return self._pool.submit(fn, *args, **kwargs)

    def cancel_prefetch(self) -> int:
        """Drop queued speculative work — called when the user navigates
        away, so we don't spend quota answering a question nobody is
        waiting for anymore."""
        with self._cv:
            dropped = len(self._pending.get(Priority.PREFETCH, {}))
            self._pending.pop(Priority.PREFETCH, None)
        return dropped

    def pending_count(self) -> int:
        with self._cv:
            return sum(len(titles) for titles in self._pending.values())

    def shutdown(self, wait: bool = False) -> None:
        with self._cv:
            self._stopping = True
            self._pending.clear()
            self._cv.notify_all()
        self._pool.shutdown(wait=wait)

    # ── Coalescing loop ──────────────────────────────────────────────
    def _flush_loop(self) -> None:
        while True:
            with self._cv:
                while not self._any_pending() and not self._stopping:
                    self._cv.wait()
                if self._stopping:
                    return
                # Something arrived — hold the full window so its
                # neighbours (the rest of the visible row, the rest of the
                # watchlist) can join the same request.
                #
                # Must loop to an absolute deadline rather than a single
                # wait(): every submit_media() notifies this condition, so
                # a plain wait(timeout) gets woken by the very arrivals
                # it's supposed to be waiting for and the window collapses
                # to nothing (measured: 20 hovers -> 10 requests of 2,
                # instead of 2 requests of 10).
                deadline = time.monotonic() + self._coalesce
                while not self._stopping:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    self._cv.wait(remaining)
                if self._stopping:
                    return
                batch = self._take_batch_locked()

            if batch:
                priority, work = batch
                self._pool.submit(self._run_batch, priority, work)

    def _any_pending(self) -> bool:
        return any(titles for titles in self._pending.values())

    def _take_batch_locked(
        self,
    ) -> tuple[Priority, dict[str, list[MediaCallback]]] | None:
        """Take the highest-priority pending bucket. Priority is an IntEnum
        ordered most-important-first, so min() is the right pick."""
        for priority in sorted(self._pending.keys()):
            titles = self._pending[priority]
            if titles:
                self._pending[priority] = defaultdict(list)
                return priority, dict(titles)
        return None

    def _run_batch(
        self, priority: Priority, work: dict[str, list[MediaCallback]]
    ) -> None:
        titles = list(work.keys())
        try:
            results, last = self._client.fetch_media_batch(titles, priority=priority)
        except Exception as exc:  # noqa: BLE001 - a worker crash must not kill the loop
            log.warning("scheduler: batch failed: %s", exc)
            results, last = {}, ApiResult(ApiStatus.NETWORK_ERROR, message=str(exc))

        for title, callbacks in work.items():
            # Absent (vs. present-and-None) means we never got to ask —
            # rate limited or the request failed. Don't let callers
            # mistake that for "AniList has no such anime".
            if title in results:
                media = results[title]
                outcome = last
            else:
                media = None
                outcome = last if not last.ok else ApiResult(ApiStatus.NETWORK_ERROR)

            for cb in callbacks:
                try:
                    cb(title, media, outcome)
                except Exception:
                    log.exception("scheduler: callback for %r failed", title)
