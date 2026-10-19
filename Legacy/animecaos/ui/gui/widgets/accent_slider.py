"""
Hand-painted horizontal slider used anywhere a QSlider would otherwise be
shown.

A plain QSlider renders with the OS's native (Fusion) style on this app's
dark theme: a barely-visible groove and a tiny square handle with almost no
contrast — it reads as an unstyled leftover next to the rest of the
hand-painted controls (ToggleCheckbox, AnimatedButton). This draws an
explicit track/fill/handle instead, the same approach ToggleCheckbox uses
for QCheckBox. API is a drop-in subset of QSlider (setRange, setSingleStep,
value/setValue, valueChanged) so it swaps in without touching call sites.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

_ACCENT = QColor(212, 66, 66)


class AccentSlider(QWidget):
    """Small hand-painted horizontal slider with an accent-colored fill."""

    valueChanged = Signal(int)

    _TRACK_H = 4
    _HANDLE_R = 7
    _HANDLE_R_ACTIVE = 8.5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._minimum = 0
        self._maximum = 100
        self._single_step = 1
        self._value = 0
        self._hover = False
        self._dragging = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

    # ── QSlider-compatible API ──────────────────────────────────

    def setRange(self, minimum: int, maximum: int) -> None:
        self._minimum = minimum
        self._maximum = max(maximum, minimum)
        clamped = min(max(self._value, self._minimum), self._maximum)
        if clamped != self._value:
            self._value = clamped
        self.update()

    def setSingleStep(self, step: int) -> None:
        self._single_step = max(1, step)

    def value(self) -> int:
        return self._value

    def setValue(self, value: int) -> None:
        clamped = min(max(int(value), self._minimum), self._maximum)
        if clamped == self._value:
            return
        self._value = clamped
        self.update()
        self.valueChanged.emit(self._value)

    # ── geometry ─────────────────────────────────────────────────

    def _handle_radius(self) -> float:
        return self._HANDLE_R_ACTIVE if (self._hover or self._dragging) else self._HANDLE_R

    def _track_rect(self) -> QRectF:
        r = self._HANDLE_R_ACTIVE  # fixed margin so the track never shifts on hover
        y = self.height() / 2 - self._TRACK_H / 2
        return QRectF(r, y, max(0.0, self.width() - 2 * r), self._TRACK_H)

    def _value_to_x(self, value: int) -> float:
        track = self._track_rect()
        span = self._maximum - self._minimum
        if span <= 0:
            return track.left()
        fraction = (value - self._minimum) / span
        return track.left() + fraction * track.width()

    def _x_to_value(self, x: float) -> int:
        track = self._track_rect()
        if track.width() <= 0:
            return self._minimum
        fraction = (x - track.left()) / track.width()
        fraction = min(max(fraction, 0.0), 1.0)
        return round(self._minimum + fraction * (self._maximum - self._minimum))

    # ── painting ─────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = self._track_rect()
        handle_x = self._value_to_x(self._value)
        handle_y = self.height() / 2
        handle_r = self._handle_radius()

        bg_path = QPainterPath()
        bg_path.addRoundedRect(track, self._TRACK_H / 2, self._TRACK_H / 2)
        p.fillPath(bg_path, QColor(255, 255, 255, 28))

        if handle_x > track.left():
            fill_rect = QRectF(track.left(), track.top(), handle_x - track.left(), track.height())
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, self._TRACK_H / 2, self._TRACK_H / 2)
            p.fillPath(fill_path, _ACCENT)

        handle_center = QPointF(handle_x, handle_y)
        if self.hasFocus():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(212, 66, 66, 60))
            p.drawEllipse(handle_center, handle_r + 4, handle_r + 4)

        p.setPen(QPen(_ACCENT, 1.5))
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(handle_center, handle_r, handle_r)

        p.end()

    # ── interaction ──────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.setValue(self._x_to_value(event.position().x()))
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self.setValue(self._x_to_value(event.position().x()))

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.update()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self.setValue(self._value - self._single_step)
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self.setValue(self._value + self._single_step)
        elif event.key() == Qt.Key.Key_Home:
            self.setValue(self._minimum)
        elif event.key() == Qt.Key.Key_End:
            self.setValue(self._maximum)
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta > 0:
            self.setValue(self._value + self._single_step)
        elif delta < 0:
            self.setValue(self._value - self._single_step)
        event.accept()
