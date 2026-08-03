from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class MangaDownloadWorkerSignals(QObject):
    progress = Signal(int, int)  # pages_done, total
    succeeded = Signal(str)      # path to .cbz
    failed = Signal(str)
    finished = Signal()


class MangaDownloadWorker(QRunnable):
    """Downloads all pages for a chapter and saves as .cbz."""

    def __init__(
        self,
        manga_service,
        download_service,
        manga_title: str,
        chapter_label: str,
        page_urls: list[str],
    ) -> None:
        super().__init__()
        self._manga_service = manga_service
        self._download_service = download_service
        self._manga_title = manga_title
        self._chapter_label = chapter_label
        self._page_urls = page_urls
        self._cancelled = False
        self.signals = MangaDownloadWorkerSignals()

    def cancel(self) -> None:
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        try:
            pages: list[bytes] = []
            total = len(self._page_urls)
            for i, url in enumerate(self._page_urls):
                if self._cancelled:
                    self.signals.failed.emit("Cancelado.")
                    return
                data = self._manga_service.download_page(url)
                if data is None:
                    self.signals.failed.emit(f"Falha ao baixar página {i + 1}.")
                    return
                pages.append(data)
                self.signals.progress.emit(i + 1, total)
            path = self._download_service.save_chapter(
                self._manga_title, self._chapter_label, pages
            )
            self.signals.succeeded.emit(path)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        finally:
            self.signals.finished.emit()
