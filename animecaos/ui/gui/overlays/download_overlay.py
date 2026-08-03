"""
Premium download overlay with animated progress, percentage, speed, and open-folder action.
Rendered entirely via QPainter for a glass-card aesthetic matching the app design.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Property,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QCursor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

_WIDTH = 420
_HEIGHT = 300
_FADE_MS = 200
_BAR_H = 6
_BAR_RADIUS = 3


class DownloadOverlay(QWidget):
    """Centered overlay showing download progress with percentage and actions."""

    cancel_requested = Signal()
    open_folder_requested = Signal(str)

    # ── States ──
    _ST_RESOLVING = 0
    _ST_DOWNLOADING = 1
    _ST_DONE = 2
    _ST_ERROR = 3

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(_WIDTH, _HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setVisible(False)
        self.setMouseTracking(True)

        self._opacity = 0.0
        self._state = self._ST_RESOLVING
        self._ring_angle = 0.0
        self._anime_name = ""
        self._episode_label = ""
        self._status_text = "Resolvendo URL..."
        self._percent = 0.0
        self._speed_text = ""
        self._eta_text = ""
        self._download_dir = ""
        self._error_text = ""
        self._closing = False

        # Button hover tracking
        self._hover_primary = False
        self._hover_secondary = False

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

        self._fade = QPropertyAnimation(self, b"overlayOpacity", self)
        self._fade.setDuration(_FADE_MS)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ── Qt Property ──
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
    def show_resolving(self, anime: str, episode_index: int) -> None:
        self._anime_name = anime
        self._episode_label = f"Episodio {episode_index + 1}"
        self._status_text = "Resolvendo URL do episodio..."
        self._state = self._ST_RESOLVING
        self._percent = 0.0
        self._speed_text = ""
        self._eta_text = ""
        self._download_dir = ""
        self._error_text = ""
        self._ring_angle = 0.0
        self._closing = False
        self._hover_primary = False
        self._hover_secondary = False

        self._center_on_parent()
        self.setVisible(True)
        self.raise_()
        self._timer.start()

        self._fade.stop()
        self._fade.setStartValue(self._opacity)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def set_downloading(self) -> None:
        self._state = self._ST_DOWNLOADING
        self._status_text = "Baixando..."
        self.update()

    def update_progress(self, line: str) -> None:
        """Parse yt-dlp output line for progress info."""
        if self._state == self._ST_RESOLVING:
            self._state = self._ST_DOWNLOADING

        # Parse percentage: "  [download]  45.2% of ..."
        pct_match = re.search(r'(\d+(?:\.\d+)?)%', line)
        if pct_match:
            self._percent = min(float(pct_match.group(1)), 100.0)

        # Parse speed: "... at 2.5MiB/s ..."
        speed_match = re.search(r'at\s+([\d.]+\s*\S+/s)', line)
        if speed_match:
            self._speed_text = speed_match.group(1)

        # Parse ETA: "... ETA 00:42"
        eta_match = re.search(r'ETA\s+(\S+)', line)
        if eta_match:
            self._eta_text = eta_match.group(1)

        if self._percent >= 100:
            self._status_text = "Finalizando..."
        else:
            self._status_text = "Baixando..."

        self.update()

    def show_done(self, download_dir: str) -> None:
        self._state = self._ST_DONE
        self._percent = 100.0
        self._download_dir = download_dir
        self._status_text = "Download concluido!"
        self._speed_text = ""
        self._eta_text = ""
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()

    def show_error(self, error: str) -> None:
        self._state = self._ST_ERROR
        self._error_text = error[:80] if len(error) > 80 else error
        self._status_text = "Falha no download"
        self.update()

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

    # ── Animation Tick ──
    def _tick(self) -> None:
        self._ring_angle = (self._ring_angle + 4.0) % 360.0
        self.update()

    # ── Button Rectangles ──
    def _primary_btn_rect(self) -> QRectF:
        w = self.width()
        if self._state == self._ST_DONE:
            btn_w = 170
            btn_h = 36
            x = w / 2 - btn_w - 6
            y = self.height() - 56
            return QRectF(x, y, btn_w, btn_h)
        elif self._state == self._ST_ERROR:
            btn_w = 120
            btn_h = 36
            x = (w - btn_w) / 2
            y = self.height() - 56
            return QRectF(x, y, btn_w, btn_h)
        else:
            # Cancel button
            btn_w = 120
            btn_h = 36
            x = (w - btn_w) / 2
            y = self.height() - 56
            return QRectF(x, y, btn_w, btn_h)

    def _secondary_btn_rect(self) -> QRectF:
        w = self.width()
        btn_w = 170
        btn_h = 36
        x = w / 2 + 6
        y = self.height() - 56
        return QRectF(x, y, btn_w, btn_h)

    # ── Mouse Events ──
    def mouseMoveEvent(self, event) -> None:
        pos = event.position() if hasattr(event, 'position') else event.localPos()
        primary = self._primary_btn_rect().contains(pos)
        secondary = self._secondary_btn_rect().contains(pos) if self._state == self._ST_DONE else False

        changed = (primary != self._hover_primary) or (secondary != self._hover_secondary)
        self._hover_primary = primary
        self._hover_secondary = secondary

        if primary or secondary:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

        if changed:
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position() if hasattr(event, 'position') else event.localPos()

        if self._primary_btn_rect().contains(pos):
            if self._state == self._ST_DONE:
                self._open_folder()
            elif self._state == self._ST_ERROR:
                self.dismiss()
            else:
                self.cancel_requested.emit()
                self.dismiss()
        elif self._state == self._ST_DONE and self._secondary_btn_rect().contains(pos):
            self.dismiss()

    def _open_folder(self) -> None:
        path = self._download_dir
        if not path or not os.path.isdir(path):
            return
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    # ── Paint ──
    def paintEvent(self, event) -> None:
        if self._opacity <= 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        a = self._opacity
        w, h = self.width(), self.height()
        cx = w / 2.0

        # ── Background card ──
        bg = QPainterPath()
        bg.addRoundedRect(QRectF(0, 0, w, h), 16, 16)
        p.fillPath(bg, QColor(14, 15, 20, int(245 * a)))

        # Border
        p.setPen(QPen(QColor(255, 255, 255, int(25 * a)), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 16, 16)

        # Accent glow
        glow = QRadialGradient(QPointF(cx, 60), 90)
        glow.setColorAt(0.0, QColor(212, 66, 66, int(18 * a)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillPath(bg, glow)

        if self._state == self._ST_DONE:
            self._paint_done(p, a, w, h, cx)
        elif self._state == self._ST_ERROR:
            self._paint_error(p, a, w, h, cx)
        else:
            self._paint_progress(p, a, w, h, cx)

        p.end()

    def _paint_progress(self, p: QPainter, a: float, w: float, h: float, cx: float) -> None:
        # ── Download icon (arrow down into tray) ──
        icon_y = 40.0
        icon_s = 1.4
        pen = QPen(QColor(212, 66, 66, int(220 * a)), 2.2 * icon_s)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # Arrow shaft
        p.drawLine(QPointF(cx, icon_y - 8 * icon_s), QPointF(cx, icon_y + 8 * icon_s))
        # Arrow head
        p.drawLine(QPointF(cx, icon_y + 8 * icon_s), QPointF(cx - 5 * icon_s, icon_y + 3 * icon_s))
        p.drawLine(QPointF(cx, icon_y + 8 * icon_s), QPointF(cx + 5 * icon_s, icon_y + 3 * icon_s))
        # Tray
        p.drawLine(QPointF(cx - 10 * icon_s, icon_y + 12 * icon_s), QPointF(cx + 10 * icon_s, icon_y + 12 * icon_s))

        # ── Title + Episode ──
        y_base = icon_y + 18 * icon_s + 12

        font_title = QFont("Segoe UI", 13)
        font_title.setWeight(QFont.Weight.DemiBold)
        p.setFont(font_title)
        p.setPen(QColor(242, 243, 245, int(255 * a)))
        title_text = self._anime_name
        if len(title_text) > 38:
            title_text = title_text[:36] + "..."
        p.drawText(QRectF(20, y_base, w - 40, 22),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, title_text)

        font_ep = QFont("Segoe UI", 11)
        p.setFont(font_ep)
        p.setPen(QColor(212, 66, 66, int(220 * a)))
        p.drawText(QRectF(20, y_base + 24, w - 40, 18),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self._episode_label)

        # ── Progress bar ──
        bar_y = y_base + 56
        bar_margin = 32
        bar_w = w - bar_margin * 2
        bar_rect = QRectF(bar_margin, bar_y, bar_w, _BAR_H)

        # Track
        track = QPainterPath()
        track.addRoundedRect(bar_rect, _BAR_RADIUS, _BAR_RADIUS)
        p.fillPath(track, QColor(255, 255, 255, int(20 * a)))

        # Fill
        if self._percent > 0:
            fill_w = max(_BAR_H, bar_w * (self._percent / 100.0))
            fill_rect = QRectF(bar_margin, bar_y, fill_w, _BAR_H)
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, _BAR_RADIUS, _BAR_RADIUS)

            grad = QLinearGradient(bar_margin, 0, bar_margin + fill_w, 0)
            grad.setColorAt(0.0, QColor(212, 66, 66, int(255 * a)))
            grad.setColorAt(1.0, QColor(230, 90, 90, int(255 * a)))
            p.fillPath(fill_path, grad)

            # Glow on fill tip
            if self._percent < 100:
                tip_x = bar_margin + fill_w
                tip_glow = QRadialGradient(QPointF(tip_x, bar_y + _BAR_H / 2), 12)
                tip_glow.setColorAt(0.0, QColor(212, 66, 66, int(60 * a)))
                tip_glow.setColorAt(1.0, QColor(212, 66, 66, 0))
                p.fillRect(QRectF(tip_x - 12, bar_y - 6, 24, _BAR_H + 12), tip_glow)

        # ── Percentage + Speed + ETA ──
        info_y = bar_y + _BAR_H + 10
        font_info = QFont("Segoe UI", 11)
        font_info.setWeight(QFont.Weight.DemiBold)
        p.setFont(font_info)

        if self._state == self._ST_DOWNLOADING:
            # Percentage left
            p.setPen(QColor(242, 243, 245, int(255 * a)))
            p.drawText(QRectF(bar_margin, info_y, bar_w / 2, 18),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                        f"{self._percent:.1f}%")

            # Speed + ETA right
            font_info.setWeight(QFont.Weight.Normal)
            p.setFont(font_info)
            p.setPen(QColor(167, 172, 181, int(200 * a)))
            right_text = ""
            if self._speed_text:
                right_text = self._speed_text
            if self._eta_text:
                right_text += f"  •  ETA {self._eta_text}"
            if right_text:
                p.drawText(QRectF(bar_margin + bar_w / 2, info_y, bar_w / 2, 18),
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, right_text)
        else:
            # Resolving state — status text centered, full width
            font_info.setWeight(QFont.Weight.Normal)
            p.setFont(font_info)
            p.setPen(QColor(167, 172, 181, int(220 * a)))
            p.drawText(QRectF(bar_margin, info_y, bar_w, 18),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                        self._status_text)

        # ── Cancel button ──
        self._draw_button(p, a, self._primary_btn_rect(), "Cancelar", self._hover_primary,
                          accent=False)

    def _paint_done(self, p: QPainter, a: float, w: float, h: float, cx: float) -> None:
        # ── Checkmark circle ──
        check_y = 55.0
        circle_r = 24.0

        # Circle
        circle_pen = QPen(QColor(76, 175, 80, int(220 * a)), 2.5)
        circle_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(circle_pen)
        p.setBrush(QColor(76, 175, 80, int(25 * a)))
        p.drawEllipse(QPointF(cx, check_y), circle_r, circle_r)

        # Checkmark
        check_pen = QPen(QColor(76, 175, 80, int(255 * a)), 3.0)
        check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        check_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(check_pen)
        p.drawLine(QPointF(cx - 10, check_y + 1), QPointF(cx - 3, check_y + 8))
        p.drawLine(QPointF(cx - 3, check_y + 8), QPointF(cx + 11, check_y - 7))

        # ── Success text ──
        y_base = check_y + circle_r + 16

        font_title = QFont("Segoe UI", 15)
        font_title.setWeight(QFont.Weight.Bold)
        p.setFont(font_title)
        p.setPen(QColor(242, 243, 245, int(255 * a)))
        p.drawText(QRectF(20, y_base, w - 40, 24),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    "Download Concluido!")

        # Anime + episode
        font_sub = QFont("Segoe UI", 11)
        p.setFont(font_sub)
        p.setPen(QColor(167, 172, 181, int(220 * a)))
        sub_text = self._anime_name
        if len(sub_text) > 36:
            sub_text = sub_text[:34] + "..."
        sub_text += f"  •  {self._episode_label}"
        p.drawText(QRectF(20, y_base + 28, w - 40, 18),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, sub_text)

        # Path
        font_path = QFont("Segoe UI", 10)
        p.setFont(font_path)
        p.setPen(QColor(167, 172, 181, int(150 * a)))
        display_path = self._download_dir.replace(os.path.expanduser("~"), "~")
        p.drawText(QRectF(20, y_base + 50, w - 40, 16),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, display_path)

        # ── Buttons ──
        self._draw_button(p, a, self._primary_btn_rect(), "Abrir Pasta", self._hover_primary,
                          accent=True)
        self._draw_button(p, a, self._secondary_btn_rect(), "Fechar", self._hover_secondary,
                          accent=False)

    def _paint_error(self, p: QPainter, a: float, w: float, h: float, cx: float) -> None:
        # ── X circle ──
        err_y = 55.0
        circle_r = 24.0

        circle_pen = QPen(QColor(212, 66, 66, int(220 * a)), 2.5)
        circle_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(circle_pen)
        p.setBrush(QColor(212, 66, 66, int(25 * a)))
        p.drawEllipse(QPointF(cx, err_y), circle_r, circle_r)

        x_pen = QPen(QColor(212, 66, 66, int(255 * a)), 3.0)
        x_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(x_pen)
        p.drawLine(QPointF(cx - 9, err_y - 9), QPointF(cx + 9, err_y + 9))
        p.drawLine(QPointF(cx + 9, err_y - 9), QPointF(cx - 9, err_y + 9))

        # ── Error text ──
        y_base = err_y + circle_r + 16

        font_title = QFont("Segoe UI", 15)
        font_title.setWeight(QFont.Weight.Bold)
        p.setFont(font_title)
        p.setPen(QColor(242, 243, 245, int(255 * a)))
        p.drawText(QRectF(20, y_base, w - 40, 24),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    "Falha no Download")

        font_err = QFont("Segoe UI", 11)
        p.setFont(font_err)
        p.setPen(QColor(212, 66, 66, int(200 * a)))
        p.drawText(QRectF(20, y_base + 30, w - 40, 36),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
                    | Qt.TextFlag.TextWordWrap,
                    self._error_text)

        # ── Close button ──
        self._draw_button(p, a, self._primary_btn_rect(), "Fechar", self._hover_primary,
                          accent=False)

    def _draw_button(self, p: QPainter, a: float, rect: QRectF, text: str,
                     hovered: bool, accent: bool) -> None:
        btn_path = QPainterPath()
        btn_path.addRoundedRect(rect, 10, 10)

        if accent:
            if hovered:
                p.fillPath(btn_path, QColor(224, 82, 82, int(75 * a)))
                p.setPen(QPen(QColor(224, 82, 82, int(130 * a)), 1.0))
            else:
                p.fillPath(btn_path, QColor(212, 66, 66, int(55 * a)))
                p.setPen(QPen(QColor(212, 66, 66, int(100 * a)), 1.0))
        else:
            if hovered:
                p.fillPath(btn_path, QColor(255, 255, 255, int(22 * a)))
                p.setPen(QPen(QColor(255, 255, 255, int(45 * a)), 1.0))
            else:
                p.fillPath(btn_path, QColor(255, 255, 255, int(14 * a)))
                p.setPen(QPen(QColor(255, 255, 255, int(35 * a)), 1.0))

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 10, 10)

        font = QFont("Segoe UI", 12)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        if accent:
            p.setPen(QColor(255, 255, 255, int(240 * a)))
        else:
            p.setPen(QColor(200, 203, 210, int(230 * a)))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
