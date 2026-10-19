"""Adaptive, closed-loop rate limiter shared by every outbound API call.

Replaces the two identical naive spacers (anilist_rate_limiter.py and
mal_rate_limiter.py), which had three fatal flaws:

1. **The floor was above the ceiling.** `MIN_INTERVAL_SECONDS = 0.65` is
   60/0.65 = 92.3 req/min against a documented 90/min limit — so sustained
   traffic produced a 429 *by construction*. Worse, AniList has served a
   degraded ~30/min for years, far below the documented number.
2. **It was open-loop.** AniList returns `X-RateLimit-Limit`,
   `X-RateLimit-Remaining` and `X-RateLimit-Reset` on every response and
   none of them were ever read, so the app had no idea how much budget was
   left and a 429 never caused it to slow down.
3. **It slept while holding the lock**, so N blocked workers serialized
   behind each other *and* occupied their thread-pool slots the whole time,
   starving unrelated work (episode loading) that shared the pool.

This one is a rolling-window budget with header feedback and a circuit
breaker:

    acquire(priority) ──> budget free?  ──yes──> record + go
                              │
                              no
                              ↓
                     wait until oldest request
                     leaves the 60s window
                     (or refuse, if PREFETCH)

Reserving a slice of the budget for FOREGROUND work is what keeps the app
responsive under load: background prefetch gets refused rather than being
allowed to consume the quota a user-initiated action is about to need.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from enum import IntEnum

log = logging.getLogger(__name__)

WINDOW_SECONDS = 60.0

# AniList documents 90/min but has served a degraded 30/min for years.
# Starting conservative and letting the response headers raise the ceiling
# is strictly safer than starting optimistic and getting 429'd to discover
# the truth.
ANILIST_DEFAULT_LIMIT = 30
MAL_DEFAULT_LIMIT = 60

# Fraction of the budget reserved for user-initiated work.
FOREGROUND_RESERVE = 0.20


class Priority(IntEnum):
    """Lower value = more important. Ordering matters: the scheduler sorts
    on this directly."""

    FOREGROUND = 0  # user is waiting: opened a detail page, submitted a search
    VISIBLE = 1     # on screen but not blocking: cards in the viewport
    PREFETCH = 2    # speculative: offscreen, spotlight scan, stats polling


class RateLimited(Exception):
    """Raised instead of queueing when the circuit is open, or when a
    low-priority request would eat into the foreground reserve."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"rate limited, retry in {retry_after:.0f}s")
        self.retry_after = retry_after


class RateLimiter:
    def __init__(
        self,
        name: str,
        limit_per_min: int,
        *,
        window: float = WINDOW_SECONDS,
    ) -> None:
        self._name = name
        self._limit = limit_per_min
        self._window = window
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        # Circuit breaker: absolute monotonic deadline; None = closed.
        self._open_until: float | None = None
        self._server_remaining: int | None = None

    # ── Introspection (drives the UI banner) ─────────────────────────
    @property
    def name(self) -> str:
        return self._name

    @property
    def limit(self) -> int:
        with self._lock:
            return self._limit

    @property
    def is_open(self) -> bool:
        """True while the circuit breaker is tripped (we're 429'd)."""
        with self._lock:
            return self._circuit_open_locked(time.monotonic())

    @property
    def retry_after(self) -> float:
        """Seconds until the circuit closes; 0 when it's already closed."""
        with self._lock:
            if self._open_until is None:
                return 0.0
            return max(0.0, self._open_until - time.monotonic())

    def _circuit_open_locked(self, now: float) -> bool:
        if self._open_until is None:
            return False
        if now >= self._open_until:
            # Half-open: let traffic through again and see what happens.
            self._open_until = None
            self._server_remaining = None
            log.info("%s: rate limit window elapsed, resuming", self._name)
            return False
        return True

    # ── Budget accounting ────────────────────────────────────────────
    def _prune_locked(self, now: float) -> None:
        cutoff = now - self._window
        while self._calls and self._calls[0] <= cutoff:
            self._calls.popleft()

    def _budget_for(self, priority: Priority) -> int:
        """Effective ceiling for this priority. Non-foreground work stops
        short of the full limit so a user action always has room."""
        if priority == Priority.FOREGROUND:
            return self._limit
        return max(1, int(self._limit * (1.0 - FOREGROUND_RESERVE)))

    def acquire(
        self,
        priority: Priority = Priority.FOREGROUND,
        *,
        timeout: float | None = None,
    ) -> None:
        """Reserve one slot, blocking until the rolling window has room.

        Raises RateLimited immediately (rather than blocking) when the
        circuit is open, or when a PREFETCH request would starve the
        foreground reserve — callers are expected to fall back to cache.

        Unlike the old implementation this never sleeps holding the lock;
        it waits on a Condition, so other threads can still record
        completions and observe response headers meanwhile.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cv:
            while True:
                now = time.monotonic()

                if self._circuit_open_locked(now):
                    raise RateLimited(self._open_until - now)  # type: ignore[operator]

                self._prune_locked(now)
                budget = self._budget_for(priority)

                # Trust the server's own count over our local one when it's
                # lower — our window and AniList's aren't aligned, and its
                # number is authoritative.
                if (
                    self._server_remaining is not None
                    and priority != Priority.FOREGROUND
                    and self._server_remaining <= self._limit * FOREGROUND_RESERVE
                ):
                    raise RateLimited(self._window)

                if len(self._calls) < budget:
                    self._calls.append(now)
                    return

                # Window full: wait until the oldest call ages out.
                wait = (self._calls[0] + self._window) - now
                if priority == Priority.PREFETCH:
                    # Speculative work never blocks; the caller serves stale
                    # cache instead of occupying a worker for ~a minute.
                    raise RateLimited(max(0.0, wait))
                if deadline is not None:
                    remaining = deadline - now
                    if remaining <= 0:
                        raise RateLimited(max(0.0, wait))
                    wait = min(wait, remaining)
                self._cv.wait(timeout=max(0.01, wait))

    def observe_response(self, headers: object) -> None:
        """Feed a response's rate-limit headers back into the budget.

        This is what makes the limiter closed-loop: if AniList says the
        real ceiling is 30 rather than 90, we adapt on the first response
        instead of discovering it via a 429.
        """
        get = getattr(headers, "get", None)
        if get is None:
            return

        with self._cv:
            limit = _as_int(get("X-RateLimit-Limit"))
            if limit and limit > 0 and limit != self._limit:
                log.info("%s: server limit is %d/min (was %d)", self._name, limit, self._limit)
                self._limit = limit

            remaining = _as_int(get("X-RateLimit-Remaining"))
            if remaining is not None:
                self._server_remaining = remaining

            self._cv.notify_all()

    def note_rate_limited(self, headers: object = None) -> float:
        """Trip the circuit breaker after a 429. Returns the cooldown.

        `Retry-After` is a delta in seconds, but `X-RateLimit-Reset` is an
        absolute Unix timestamp — the old code assigned the latter straight
        into a "seconds to wait" field, which is how the UI could end up
        promising a ~1.7-billion-second wait.
        """
        cooldown = self._window
        get = getattr(headers, "get", None) if headers is not None else None
        if get is not None:
            retry_after = _as_int(get("Retry-After"))
            if retry_after is not None and retry_after > 0:
                cooldown = float(retry_after)
            else:
                reset = _as_int(get("X-RateLimit-Reset"))
                if reset is not None and reset > 0:
                    # Absolute epoch seconds -> delta from now.
                    delta = reset - time.time()
                    if 0 < delta <= 3600:
                        cooldown = float(delta)

        cooldown = max(1.0, min(cooldown, 3600.0))
        with self._cv:
            self._open_until = time.monotonic() + cooldown
            self._server_remaining = 0
            log.warning("%s: 429 received, backing off %.0fs", self._name, cooldown)
        return cooldown

    def reset(self) -> None:
        """Clear all state. Tests only."""
        with self._cv:
            self._calls.clear()
            self._open_until = None
            self._server_remaining = None
            self._cv.notify_all()

    def stats(self) -> dict[str, object]:
        with self._lock:
            now = time.monotonic()
            self._prune_locked(now)
            return {
                "name": self._name,
                "limit": self._limit,
                "used_in_window": len(self._calls),
                "server_remaining": self._server_remaining,
                "circuit_open": self._open_until is not None and now < self._open_until,
            }


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


# ── Process-wide instances ───────────────────────────────────────────
anilist_limiter = RateLimiter("anilist", ANILIST_DEFAULT_LIMIT)
mal_limiter = RateLimiter("mal", MAL_DEFAULT_LIMIT)
