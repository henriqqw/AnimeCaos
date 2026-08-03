from __future__ import annotations

from collections.abc import Callable
from traceback import format_exc
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()


class FunctionWorker(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            stack = format_exc(limit=2)
            self.signals.failed.emit(f"{exc}\n{stack}")
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()
