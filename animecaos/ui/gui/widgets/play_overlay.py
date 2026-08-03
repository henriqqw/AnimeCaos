"""
Animated overlay popup shown while resolving + opening the video player.
Centered on the parent window with spinning ring, anime/episode info, and dynamic messages.
Auto-dismisses when play finishes or on error.
"""
from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Property,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QWidget


_RING_RADIUS = 28
_RING_STROKE = 3.0
_WIDTH = 380
_HEIGHT = 220
_FADE_MS = 200


class PlayOverlay(QWidget):
    """Frameless overlay shown during episode playback loading."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(_WIDTH, _HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setVisible(False)

        self._opacity = 0.0
        self._ring_angle = 0.0
        self._anime_name = ""
        self._episode_label = ""
        self._status_text = "Abrindo player..."
        self._elapsed_ms = 0
        self._closing = False

        self._status_messages: list[tuple[int, str]] = [
            (0,     "Abrindo player..."),
            (3000,  "Resolvendo URL do episodio..."),
            (8000,  "Conectando ao servidor de video..."),
            (15000, "Aguarde, carregando stream..."),
            (25000, "Quase la..."),
        ]
        self._next_msg = 1

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

        self._fade = QPropertyAnimation(self, b"overlayOpacity", self)
        self._fade.setDuration(_FADE_MS)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ── Qt property ──
    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, v: float) -> None:
        self._opacity = v
        self.update()
        if self._closing and v <= 0:
            self._timer.stop()
            self.setVisible(False)
            self._closing = False

    overlayOpacity = Property(float, _get_opacity, _set_opacity)

    # ── Public API ──
    def show_loading(self, anime: str, episode_index: int) -> None:
        self._anime_name = anime
        self._episode_label = f"Episodio {episode_index + 1}"
        self._status_text = self._status_messages[0][1]
        self._next_msg = 1
        self._elapsed_ms = 0
        self._ring_angle = 0.0
        self._closing = False

        self._center_on_parent()
        self.setVisible(True)
        self.raise_()
        self._timer.start()

        self._fade.stop()
        self._fade.setStartValue(self._opacity)
        self._fade.setEndValue(1.0)
        self._fade.start()

    @Slot()
    def dismiss(self) -> None:
        self._closing = True
        self._fade.stop()
        self._fade.setStartValue(self._opacity)
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _center_on_parent(self) -> None:
        p = self.parentWidget()
        if p:
            x = (p.width() - _WIDTH) // 2
            y = (p.height() - _HEIGHT) // 2
            self.move(x, y)

    # ── Animation tick ──
    def _tick(self) -> None:
        self._ring_angle = (self._ring_angle + 4.0) % 360.0
        self._elapsed_ms += 16

        if self._next_msg < len(self._status_messages):
            ms, msg = self._status_messages[self._next_msg]
            if self._elapsed_ms >= ms:
                self._status_text = msg
                self._next_msg += 1

        self.update()

    # ── Paint ──
    def paintEvent(self, event) -> None:
        if self._opacity <= 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        a = self._opacity
        w, h = self.width(), self.height()
        cx = w / 2.0

        # Background card
        bg = QPainterPath()
        bg.addRoundedRect(QRectF(0, 0, w, h), 16, 16)
        p.fillPath(bg, QColor(14, 15, 20, int(240 * a)))

        # Border
        border_pen = QPen(QColor(255, 255, 255, int(25 * a)), 1.0)
        p.setPen(border_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 16, 16)

        # Subtle accent glow
        from PySide6.QtGui import QRadialGradient
        glow = QRadialGradient(QPointF(cx, 70), 80)
        glow.setColorAt(0.0, QColor(212, 66, 66, int(20 * a)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillPath(bg, glow)

        # ── Spinning ring ──
        ring_y = 60
        # Track
        track_pen = QPen(QColor(255, 255, 255, int(18 * a)), _RING_STROKE)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(track_pen)
        p.drawEllipse(QPointF(cx, ring_y), _RING_RADIUS, _RING_RADIUS)

        # Arc
        arc_rect = QRectF(cx - _RING_RADIUS, ring_y - _RING_RADIUS,
                          _RING_RADIUS * 2, _RING_RADIUS * 2)
        gradient = QConicalGradient(QPointF(cx, ring_y), self._ring_angle)
        gradient.setColorAt(0.0, QColor(212, 66, 66, int(240 * a)))
        gradient.setColorAt(0.25, QColor(212, 66, 66, int(60 * a)))
        gradient.setColorAt(0.3, QColor(212, 66, 66, 0))
        arc_pen = QPen(gradient, _RING_STROKE)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc_pen)
        p.drawArc(arc_rect, int(self._ring_angle * 16), 90 * 16)

        # ── Anime name ──
        font_title = QFont("Segoe UI", 13)
        font_title.setWeight(QFont.Weight.DemiBold)
        p.setFont(font_title)
        p.setPen(QColor(242, 243, 245, int(255 * a)))

        title_text = self._anime_name
        if len(title_text) > 40:
            title_text = title_text[:38] + "..."
        title_rect = QRectF(20, ring_y + _RING_RADIUS + 16, w - 40, 22)
        p.drawText(title_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, title_text)

        # ── Episode label ──
        font_ep = QFont("Segoe UI", 11)
        font_ep.setWeight(QFont.Weight.Normal)
        p.setFont(font_ep)
        p.setPen(QColor(212, 66, 66, int(220 * a)))

        ep_rect = QRectF(20, ring_y + _RING_RADIUS + 40, w - 40, 18)
        p.drawText(ep_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self._episode_label)

        # ── Status text ──
        font_status = QFont("Segoe UI", 11)
        p.setFont(font_status)
        p.setPen(QColor(167, 172, 181, int(200 * a)))

        status_rect = QRectF(20, ring_y + _RING_RADIUS + 62, w - 40, 20)
        p.drawText(status_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self._status_text)

        p.end()
