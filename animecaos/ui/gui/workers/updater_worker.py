from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class UpdaterCheckWorkerSignals(QObject):
    succeeded = Signal(bool)
    failed = Signal(str)
    finished = Signal()


class UpdaterCheckWorker(QRunnable):
    def __init__(self, updater_service) -> None:
        super().__init__()
        self._updater_service = updater_service
        self.signals = UpdaterCheckWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            has_update = self._updater_service.check_for_updates()
            self.signals.succeeded.emit(has_update)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        finally:
            self.signals.finished.emit()
