"""Download queue: simultaneous downloads, batch downloads, and downloads
that keep running in the background — three separate user requests that all
came down to the same architectural gap. Before this, MainWindow tracked a
single `_active_download_worker` and simply refused a second download
("Ja existe um download em andamento") while the first was in flight.

The resolver (AnimeService.resolve_player_url's signature) and the download
worker factory (DownloadWorker's constructor signature) are both injected,
which is what makes this testable against a scriptable fake instead of real
network/Selenium/yt-dlp — see tests/test_download_queue.py.

Concurrency note: resolve_player_url is already serialized by AnimeService's
internal lock, so N simultaneous resolutions naturally queue up on their own;
only the yt-dlp downloads themselves actually run in parallel, up to
max_concurrent. That's the intended behavior, not a limitation to work around.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from animecaos.services.downloads_service import DownloadsService, sanitize_anime_filename

if TYPE_CHECKING:
    from animecaos.ui.gui.workers.download_worker import DownloadWorker

# FunctionWorker/DownloadWorker are imported lazily inside the methods that
# use them (not at module level): animecaos.services is a lower layer than
# animecaos.ui.gui, and animecaos/ui/gui/__init__.py eagerly imports
# main_window (via .app), which imports THIS module — an eager top-level
# import here would be a circular import the moment anything imports
# animecaos.ui.gui.* before main_window has finished loading it once.

_ACTIVE_STATUSES = ("resolving", "downloading")

# yt-dlp's default progress line looks like:
#   [download]  45.2% of   123.45MiB at    1.23MiB/s ETA 00:12
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)%")
_SPEED_RE = re.compile(r"at\s+(\S+)")
_ETA_RE = re.compile(r"ETA\s+(\S+)")


@dataclass
class QueueItem:
    id: int
    anime: str
    episode_index: int
    status: str = "queued"  # queued | resolving | downloading | done | failed | cancelled
    percent: float = 0.0
    speed: str = ""
    eta: str = ""
    error: str = ""
    file_path: str | None = None


def _parse_progress_line(line: str) -> dict:
    """Best-effort extraction of percent/speed/eta from one yt-dlp progress
    line. Any field not found is simply omitted — callers only update what
    was actually parsed, so a stray non-progress log line never clobbers the
    last known-good values."""
    result: dict = {}
    m = _PERCENT_RE.search(line)
    if m:
        try:
            result["percent"] = float(m.group(1))
        except ValueError:
            pass
    m = _SPEED_RE.search(line)
    if m:
        result["speed"] = m.group(1)
    m = _ETA_RE.search(line)
    if m:
        result["eta"] = m.group(1)
    return result


class DownloadQueueService(QObject):
    item_added = Signal(object)
    item_changed = Signal(object)
    all_finished = Signal()

    def __init__(
        self,
        resolver: Callable[[str, int], str],
        downloads_service: DownloadsService,
        thread_pool: QThreadPool,
        max_concurrent: int = 2,
        download_worker_factory: Callable[[str, str], QRunnable] | None = None,
    ) -> None:
        super().__init__()
        self._resolver = resolver
        self._downloads_service = downloads_service
        self._thread_pool = thread_pool
        self._max_concurrent = max(1, max_concurrent)
        if download_worker_factory is None:
            from animecaos.ui.gui.workers.download_worker import DownloadWorker

            download_worker_factory = DownloadWorker
        self._download_worker_factory = download_worker_factory

        self._items: dict[int, QueueItem] = {}
        self._order: list[int] = []
        self._workers: dict[int, object] = {}
        self._next_id = 1

    # ── Public API ───────────────────────────────────────────────

    def enqueue(self, anime: str, episode_index: int) -> QueueItem:
        item = QueueItem(id=self._next_id, anime=anime, episode_index=episode_index)
        self._next_id += 1
        self._items[item.id] = item
        self._order.append(item.id)
        self.item_added.emit(item)
        self._maybe_start_next()
        return item

    def enqueue_many(self, anime: str, indices: list[int]) -> list[QueueItem]:
        return [self.enqueue(anime, index) for index in indices]

    def find_active_or_queued(self, anime: str, episode_index: int) -> QueueItem | None:
        """The single place duplicate-download checks go through: is this
        anime/episode already queued, resolving, or downloading? Ignores
        items that finished (done/failed/cancelled) — those are no longer
        "in the way" of a new download."""
        for item_id in self._order:
            item = self._items[item_id]
            if (
                item.anime == anime
                and item.episode_index == episode_index
                and item.status in ("queued", *_ACTIVE_STATUSES)
            ):
                return item
        return None

    def cancel(self, item_id: int) -> bool:
        item = self._items.get(item_id)
        if item is None or item.status in ("done", "failed", "cancelled"):
            return False
        was_active = item.status in _ACTIVE_STATUSES
        worker = self._workers.pop(item_id, None)
        if worker is not None and hasattr(worker, "cancel"):
            worker.cancel()
        item.status = "cancelled"
        self.item_changed.emit(item)
        if was_active:
            self._maybe_start_next()
        self._check_all_finished()
        return True

    def cancel_all(self) -> None:
        for item_id in list(self._order):
            self.cancel(item_id)

    def set_max_concurrent(self, n: int) -> None:
        self._max_concurrent = max(1, n)
        self._maybe_start_next()

    @property
    def active(self) -> list[QueueItem]:
        return [self._items[i] for i in self._order if self._items[i].status in _ACTIVE_STATUSES]

    @property
    def pending(self) -> list[QueueItem]:
        return [self._items[i] for i in self._order if self._items[i].status == "queued"]

    # ── Internal: scheduling ─────────────────────────────────────

    def _maybe_start_next(self) -> None:
        while len(self.active) < self._max_concurrent:
            next_item = next(
                (self._items[i] for i in self._order if self._items[i].status == "queued"), None
            )
            if next_item is None:
                break
            self._start_resolving(next_item)

    def _start_resolving(self, item: QueueItem) -> None:
        from animecaos.ui.gui.workers.base import FunctionWorker

        item.status = "resolving"
        self.item_changed.emit(item)

        worker = FunctionWorker(self._resolver, item.anime, item.episode_index)
        self._workers[item.id] = worker
        worker.signals.succeeded.connect(lambda url, iid=item.id: self._on_resolved(iid, url))
        worker.signals.failed.connect(lambda err, iid=item.id: self._on_resolve_failed(iid, err))
        self._thread_pool.start(worker)

    def _on_resolved(self, item_id: int, player_url: object) -> None:
        item = self._items.get(item_id)
        if item is None or item.status == "cancelled":
            return

        out_dir = self._downloads_service.anime_dir(item.anime)
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_anime = sanitize_anime_filename(item.anime)
        out_name = f"{safe_anime} - EP{item.episode_index + 1}.%(ext)s"
        out_template = str(out_dir / out_name)

        item.status = "downloading"
        self.item_changed.emit(item)

        dl_worker = self._download_worker_factory(str(player_url), out_template)
        self._workers[item_id] = dl_worker
        dl_worker.signals.progress.connect(lambda line, iid=item_id: self._on_download_progress(iid, line))
        dl_worker.signals.succeeded.connect(lambda path, iid=item_id: self._on_download_succeeded(iid, path))
        dl_worker.signals.failed.connect(lambda err, iid=item_id: self._on_download_failed(iid, err))
        self._thread_pool.start(dl_worker)

    def _on_resolve_failed(self, item_id: int, error: str) -> None:
        item = self._items.get(item_id)
        if item is None or item.status == "cancelled":
            return
        item.status = "failed"
        item.error = error.splitlines()[0] if error else "Falha ao resolver URL do episodio."
        self._workers.pop(item_id, None)
        self.item_changed.emit(item)
        self._maybe_start_next()
        self._check_all_finished()

    def _on_download_progress(self, item_id: int, line: str) -> None:
        item = self._items.get(item_id)
        if item is None or item.status == "cancelled":
            return
        parsed = _parse_progress_line(line)
        if not parsed:
            return
        if "percent" in parsed:
            item.percent = parsed["percent"]
        if "speed" in parsed:
            item.speed = parsed["speed"]
        if "eta" in parsed:
            item.eta = parsed["eta"]
        self.item_changed.emit(item)

    def _on_download_succeeded(self, item_id: int, file_path: str) -> None:
        item = self._items.get(item_id)
        if item is None or item.status == "cancelled":
            return
        item.status = "done"
        item.percent = 100.0
        item.file_path = file_path
        self._workers.pop(item_id, None)
        self.item_changed.emit(item)
        self._maybe_start_next()
        self._check_all_finished()

    def _on_download_failed(self, item_id: int, error: str) -> None:
        item = self._items.get(item_id)
        if item is None or item.status == "cancelled":
            return
        item.status = "failed"
        item.error = error
        self._workers.pop(item_id, None)
        self.item_changed.emit(item)
        self._maybe_start_next()
        self._check_all_finished()

    def _check_all_finished(self) -> None:
        if not self.active and not self.pending:
            self.all_finished.emit()
