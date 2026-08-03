"""Compact rotating spinner widget used for inline loading indicators."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Property
from PySide6.QtGui import QColor, QConicalGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget


class LoadingSpinner(QWidget):
    """A small self-contained spinning arc loader, consistent with the global overlay ring."""

    def __init__(self, size: int = 20, stroke: float = 2.0, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._stroke = stroke
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._rotate)

    def _rotate(self) -> None:
        self._angle = (self._angle + 30.0) % 360.0
        self.update()

    def start(self) -> None:
        self._angle = 0.0
        self._timer.start()
        self.update()

    def stop(self) -> None:
        self._timer.stop()
        self.update()

    def paintEvent(self, event) -> None:
        if not self._timer.isActive():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.width()
        cy = s / 2.0
        r = (s - self._stroke) / 2.0

        track_pen = QPen(QColor(255, 255, 255, 25), self._stroke)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(track_pen)
        p.drawEllipse(QRectF(self._stroke / 2, self._stroke / 2, r * 2, r * 2))

        rect = QRectF(self._stroke / 2, self._stroke / 2, r * 2, r * 2)
        gradient = QConicalGradient(cy, cy, self._angle)
        gradient.setColorAt(0.0, QColor(212, 66, 66, 255))
        gradient.setColorAt(0.3, QColor(212, 66, 66, 60))
        gradient.setColorAt(0.4, QColor(212, 66, 66, 0))
        arc_pen = QPen(gradient, self._stroke)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc_pen)
        p.drawArc(rect, int(self._angle * 16), 100 * 16)
        p.end()