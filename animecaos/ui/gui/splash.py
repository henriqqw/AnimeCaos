"""
Animated splash screen matching the AnimeCaos dark theme.

- Radial glow background
- App icon with fade-in + subtle scale
- Branded title with staggered letter reveal
- Pulsing progress ring
- Timed status messages
- Smooth fade-out transition before main window appears
"""
from __future__ import annotations

import math
import os
import sys

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSequentialAnimationGroup,
    QSize,
    Qt,
    QTimer,
    Property,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from animecaos import __version__


def _icon_path() -> str:
    try:
        base = sys._MEIPASS
    except AttributeError:
        base = os.path.abspath(".")
    return os.path.join(base, "public", "icon.png")


_STATUS_STEPS: list[tuple[int, str]] = [
    (0,    "Inicializando..."),
    (600,  "Carregando plugins..."),
    (1200, "Preparando interface..."),
    (1800, "Quase pronto..."),
]

_BRAND = "animecaos"
_ACCENT = QColor(212, 66, 66)
_BG_DARK = QColor(11, 12, 15)
_BG_MID = QColor(16, 18, 24)
_TEXT_PRIMARY = QColor(242, 243, 245)
_TEXT_MUTED = QColor(167, 172, 181)

_WIDTH = 420
_HEIGHT = 340
_ANIM_DURATION_MS = 2400
_FADE_OUT_MS = 350


class SplashScreen(QWidget):
    """Frameless animated splash screen."""

    finished = Signal()

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(_WIDTH, _HEIGHT)

        # State
        self._progress = 0.0      # 0..1 overall progress
        self._ring_angle = 0.0    # spinning ring
        self._text_reveal = 0.0   # 0..1 letter reveal
        self._opacity = 0.0       # master opacity
        self._status_text = _STATUS_STEPS[0][1]
        self._next_status = 1
        self._elapsed_ms = 0
        self._closing = False

        # Load icon
        self._icon = QPixmap(_icon_path())
        if not self._icon.isNull():
            self._icon = self._icon.scaled(
                QSize(64, 64),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        # 60-fps tick
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

        # Fade-in
        self._fade = QPropertyAnimation(self, b"masterOpacity", self)
        self._fade.setDuration(400)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ── Qt property ──────────────────────────────────────────────
    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, v: float) -> None:
        self._opacity = v
        self.update()
        if self._closing and v <= 0:
            self._timer.stop()
            self.close()
            self.finished.emit()

    masterOpacity = Property(float, _get_opacity, _set_opacity)

    # ── Public API ───────────────────────────────────────────────
    def start(self) -> None:
        self._center_on_screen()
        self.show()
        self._timer.start()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def finish(self) -> None:
        """Trigger smooth fade-out then emit finished()."""
        self._closing = True
        self._fade.stop()
        self._fade.setDuration(_FADE_OUT_MS)
        self._fade.setStartValue(self._opacity)
        self._fade.setEndValue(0.0)
        self._fade.start()

    # ── Internals ────────────────────────────────────────────────
    def _center_on_screen(self) -> None:
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - _WIDTH) // 2
            y = geo.y() + (geo.height() - _HEIGHT) // 2
            self.move(x, y)

    def _tick(self) -> None:
        dt = 16
        self._elapsed_ms += dt

        # Progress 0→1 over the animation duration
        self._progress = min(1.0, self._elapsed_ms / _ANIM_DURATION_MS)

        # Ring spin
        self._ring_angle = (self._ring_angle + 3.6) % 360.0

        # Text reveal (ease-out curve)
        t = min(1.0, self._elapsed_ms / 1400.0)
        self._text_reveal = 1.0 - (1.0 - t) ** 3  # cubic ease-out

        # Status messages
        if self._next_status < len(_STATUS_STEPS):
            ms_threshold, msg = _STATUS_STEPS[self._next_status]
            if self._elapsed_ms >= ms_threshold:
                self._status_text = msg
                self._next_status += 1

        self.update()

    # ── Paint ────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        if self._opacity <= 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        a = self._opacity

        # 1. Background: rounded rect with radial glow
        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(0, 0, w, h), 18, 18)
        p.setClipPath(bg_path)

        # Solid dark fill
        p.fillRect(self.rect(), QColor(11, 12, 15, int(245 * a)))

        # Subtle radial glow from center
        glow = QRadialGradient(QPointF(cx, cy - 20), w * 0.55)
        glow.setColorAt(0.0, QColor(212, 66, 66, int(28 * a)))
        glow.setColorAt(0.5, QColor(212, 66, 66, int(8 * a)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), glow)

        # Border
        p.setClipping(False)
        border_pen = QPen(QColor(255, 255, 255, int(40 * a)), 1.0)
        p.setPen(border_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 18, 18)

        # 2. Progress ring (behind icon)
        ring_cy = 100
        ring_r = 42
        self._draw_ring(p, cx, ring_cy, ring_r, a)

        # 3. Icon (centered in ring)
        if not self._icon.isNull():
            icon_opacity = min(1.0, self._elapsed_ms / 600.0)
            p.setOpacity(a * icon_opacity)

            iw, ih = self._icon.width(), self._icon.height()
            # Rounded clip for icon
            icon_rect = QRectF(cx - iw / 2, ring_cy - ih / 2, iw, ih)
            icon_clip = QPainterPath()
            icon_clip.addRoundedRect(icon_rect, 12, 12)
            p.setClipPath(icon_clip)
            p.drawPixmap(int(icon_rect.x()), int(icon_rect.y()), self._icon)
            p.setClipping(False)
            p.setOpacity(1.0)

        # 4. Brand title with staggered reveal
        title_y = ring_cy + ring_r + 34
        self._draw_title(p, cx, title_y, a)

        # 5. Version badge
        version_y = title_y + 28
        self._draw_version(p, cx, version_y, a)

        # 6. Status text
        status_y = h - 44
        self._draw_status(p, cx, status_y, a)

        # 7. Bottom progress bar
        bar_y = h - 20
        self._draw_progress_bar(p, w, bar_y, a)

        p.end()

    def _draw_ring(self, p: QPainter, cx: float, cy: float, r: float, a: float) -> None:
        ring_opacity = min(1.0, self._elapsed_ms / 800.0)
        pen_w = 2.5

        # Track
        track_color = QColor(255, 255, 255, int(20 * a * ring_opacity))
        p.setPen(QPen(track_color, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Spinning arc
        arc_rect = QRectF(cx - r, cy - r, r * 2, r * 2)
        arc_span = 90 * 16  # 90 degrees
        start_angle = int(self._ring_angle * 16)

        gradient = QConicalGradient(QPointF(cx, cy), self._ring_angle)
        gradient.setColorAt(0.0, QColor(212, 66, 66, int(220 * a * ring_opacity)))
        gradient.setColorAt(0.25, QColor(212, 66, 66, int(60 * a * ring_opacity)))
        gradient.setColorAt(0.3, QColor(212, 66, 66, 0))

        pen = QPen(QBrush(gradient), pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(arc_rect, start_angle, arc_span)

    def _draw_title(self, p: QPainter, cx: float, y: float, a: float) -> None:
        font = QFont("Segoe UI", 22)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        fm = QFontMetrics(font)

        total_w = fm.horizontalAdvance(_BRAND)
        start_x = cx - total_w / 2

        revealed_count = int(self._text_reveal * len(_BRAND))

        x = start_x
        for i, ch in enumerate(_BRAND):
            char_w = fm.horizontalAdvance(ch)
            if i < revealed_count:
                # "anime" = white, "caos" = red
                if i < 5:
                    color = QColor(242, 243, 245, int(255 * a))
                else:
                    color = QColor(212, 66, 66, int(255 * a))
            else:
                color = QColor(242, 243, 245, int(30 * a))

            p.setPen(color)
            p.drawText(QPointF(x, y), ch)
            x += char_w

    def _draw_version(self, p: QPainter, cx: float, y: float, a: float) -> None:
        ver_opacity = min(1.0, max(0.0, (self._elapsed_ms - 800) / 500.0))
        if ver_opacity <= 0:
            return

        text = f"v{__version__}"
        font = QFont("Segoe UI", 10)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(text)
        th = fm.height()

        badge_w = tw + 16
        badge_h = th + 6
        badge_rect = QRectF(cx - badge_w / 2, y - th / 2 - 1, badge_w, badge_h)

        badge_path = QPainterPath()
        badge_path.addRoundedRect(badge_rect, 5, 5)

        oa = a * ver_opacity
        p.fillPath(badge_path, QColor(212, 66, 66, int(35 * oa)))

        border = QPen(QColor(212, 66, 66, int(90 * oa)), 1.0)
        p.setPen(border)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(badge_rect, 5, 5)

        p.setPen(QColor(212, 66, 66, int(220 * oa)))
        p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_status(self, p: QPainter, cx: float, y: float, a: float) -> None:
        font = QFont("Segoe UI", 11)
        font.setWeight(QFont.Weight.Normal)
        p.setFont(font)

        p.setPen(QColor(167, 172, 181, int(200 * a)))
        rect = QRectF(0, y, self.width(), 20)
        p.drawText(rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self._status_text)

    def _draw_progress_bar(self, p: QPainter, w: float, y: float, a: float) -> None:
        bar_h = 3
        margin = 40
        bar_w = w - margin * 2
        bar_rect = QRectF(margin, y, bar_w, bar_h)

        # Track
        track_path = QPainterPath()
        track_path.addRoundedRect(bar_rect, bar_h / 2, bar_h / 2)
        p.fillPath(track_path, QColor(255, 255, 255, int(18 * a)))

        # Fill
        fill_w = bar_w * self._progress
        if fill_w > 0:
            fill_rect = QRectF(margin, y, fill_w, bar_h)
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, bar_h / 2, bar_h / 2)

            grad = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
            grad.setColorAt(0.0, QColor(212, 66, 66, int(200 * a)))
            grad.setColorAt(1.0, QColor(234, 90, 90, int(255 * a)))
            p.fillPath(fill_path, grad)
