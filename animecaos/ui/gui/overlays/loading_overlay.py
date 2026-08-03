"""
Premium animated loading overlay for list widgets.
Skeleton shimmer + pulsing dot spinner with smooth fade transitions.
Uses a stacked wrapper approach to render on top of QListWidget.
"""
from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Property,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QStackedLayout, QWidget


class _OverlayCanvas(QWidget):
    """Internal paint surface for the loading animation."""

    _SKELETON_ROWS = 6
    _ROW_HEIGHT = 36
    _ROW_GAP = 8
    _ROW_RADIUS = 8
    _SHIMMER_WIDTH = 0.35
    _DOT_COUNT = 3
    _DOT_RADIUS = 4
    _DOT_SPACING = 14

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setVisible(False)

        self._opacity = 0.0
        self._phase = 0.0
        self._dot_phase = 0.0
        self._status_text = "Buscando..."
        self._hiding = False
        self._elapsed_ms = 0

        self._status_messages: list[tuple[int, str]] = []
        self._next_msg_index = 0

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._tick)

        self._fade_anim = QPropertyAnimation(self, b"overlayOpacity", self)
        self._fade_anim.setDuration(280)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.finished.connect(self._on_fade_finished)

    # -- Qt property --
    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, v: float) -> None:
        self._opacity = v
        if v > 0 and not self.isVisible():
            self.setVisible(True)
            self.raise_()
        self.update()

    overlayOpacity = Property(float, _get_opacity, _set_opacity)

    def show_loading(self, text: str, messages: list[tuple[int, str]] | None = None) -> None:
        self._status_text = text
        self._phase = 0.0
        self._dot_phase = 0.0
        self._elapsed_ms = 0
        self._hiding = False

        self._status_messages = messages or []
        self._next_msg_index = 0

        self.setVisible(True)
        self.raise_()
        self._anim_timer.start()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def hide_loading(self) -> None:
        self._hiding = True
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _on_fade_finished(self) -> None:
        if self._hiding and self._opacity <= 0:
            self.setVisible(False)
            self._anim_timer.stop()
            self._hiding = False

    def _tick(self) -> None:
        dt = 16.0 / 1000.0
        self._phase = (self._phase + dt * 0.45) % 1.0
        self._dot_phase = (self._dot_phase + dt * 2.5) % (math.pi * 2)
        self._elapsed_ms += 16

        # Advance status messages based on elapsed time
        if self._next_msg_index < len(self._status_messages):
            threshold_ms, msg = self._status_messages[self._next_msg_index]
            if self._elapsed_ms >= threshold_ms:
                self._status_text = msg
                self._next_msg_index += 1

        self.update()

    def paintEvent(self, event) -> None:
        if self._opacity <= 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        alpha = self._opacity

        # 1. Dim background
        p.fillRect(self.rect(), QColor(11, 12, 15, int(200 * alpha)))

        # 2. Skeleton shimmer rows
        start_y = 16
        margin_x = 16
        available_w = w - margin_x * 2
        widths = [1.0, 0.82, 0.93, 0.72, 0.88, 0.65]

        for i in range(self._SKELETON_ROWS):
            row_w = int(available_w * widths[i % len(widths)])
            y = start_y + i * (self._ROW_HEIGHT + self._ROW_GAP)
            if y + self._ROW_HEIGHT > h - 60:
                break

            rect = QRectF(margin_x, y, row_w, self._ROW_HEIGHT)
            path = QPainterPath()
            path.addRoundedRect(rect, self._ROW_RADIUS, self._ROW_RADIUS)

            base = QColor(255, 255, 255, int(18 * alpha))
            p.fillPath(path, base)

            # Shimmer: a highlight band sweeps left-to-right
            shimmer_pos = self._phase  # 0→1

            grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
            clr_t = QColor(255, 255, 255, 0)
            clr_h = QColor(255, 255, 255, int(30 * alpha))

            hw = self._SHIMMER_WIDTH / 2
            c = shimmer_pos
            grad.setColorAt(0.0, clr_t)
            if c - hw > 0.01:
                grad.setColorAt(c - hw, clr_t)
            if 0.01 < c < 0.99:
                grad.setColorAt(c, clr_h)
            if c + hw < 0.99:
                grad.setColorAt(c + hw, clr_t)
            grad.setColorAt(1.0, clr_t)

            p.save()
            p.setClipPath(path)
            p.fillRect(rect, grad)
            p.restore()

        # 3. Dot spinner + status text
        center_y = h - 36
        center_x = w / 2

        total_dots_width = (self._DOT_COUNT - 1) * self._DOT_SPACING
        dot_start_x = center_x - total_dots_width / 2

        for i in range(self._DOT_COUNT):
            offset = math.sin(self._dot_phase - i * 0.6) * 0.5 + 0.5
            r = self._DOT_RADIUS * (0.6 + 0.4 * offset)
            dot_alpha = int((100 + 155 * offset) * alpha)
            color = QColor(212, 66, 66, dot_alpha)

            cx = dot_start_x + i * self._DOT_SPACING
            cy = center_y - 2 - math.sin(self._dot_phase - i * 0.6) * 3

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        text_color = QColor(166, 172, 181, int(220 * alpha))
        p.setPen(QPen(text_color))
        font = p.font()
        font.setPixelSize(12)
        font.setWeight(font.Weight.Medium)
        p.setFont(font)

        text_rect = QRectF(0, center_y + 8, w, 20)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self._status_text)

        p.end()


class LoadingOverlay:
    """
    Wraps a target QWidget (e.g. QListWidget) inside a QWidget with a
    QStackedLayout so that an animated overlay can render on top.

    Usage:
        overlay = LoadingOverlay(my_list_widget)
        layout.addWidget(overlay.wrapper, 1)   # add wrapper instead of the list
        overlay.show_loading("Buscando...")
        overlay.hide_loading()
    """

    def __init__(self, target: QWidget) -> None:
        self.target = target

        self.wrapper = QWidget()
        self.wrapper.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedLayout(self.wrapper)
        self._stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self._stack.setContentsMargins(0, 0, 0, 0)

        self._canvas = _OverlayCanvas()

        # In StackAll mode, higher index renders on top.
        # Target at index 0 (bottom), canvas at index 1 (top).
        self._stack.addWidget(target)        # index 0
        self._stack.addWidget(self._canvas)  # index 1

    def show_loading(self, text: str = "Buscando...", messages: list[tuple[int, str]] | None = None) -> None:
        self._canvas.show_loading(text, messages)

    def hide_loading(self) -> None:
        self._canvas.hide_loading()

    def set_status(self, text: str) -> None:
        self._canvas._status_text = text
        self._canvas.update()
