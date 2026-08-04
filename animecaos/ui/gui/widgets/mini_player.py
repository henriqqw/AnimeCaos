"""
Persistent mini-player bar with Lucide icons.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal, QPointF, QRectF, QSize
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .anime_card import generate_dynamic_cover
from animecaos.ui.gui.icons import icon_skip_back, icon_skip_forward, icon_x


class _AutoplayToggle(QWidget):
    """Small hand-painted checkbox for the autoplay setting.

    A plain QCheckBox was used before, but the app's global QSS only fills
    the checked indicator with a solid accent color and draws no checkmark
    glyph on top — so it visually reads as a decorative colored square
    rather than a checkbox. This draws an explicit check instead."""

    toggled = Signal(bool)

    _BOX = 16
    _GAP = 8
    _RIGHT_PAD = 3  # safety margin so minor metric/render rounding can't clip the label

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self._checked = True
        self._hover = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # Width is NOT computed here: at construction time the widget isn't
        # parented yet, so self.font() is still the pre-QSS default font,
        # not the "Segoe UI" font the app's global stylesheet applies once
        # mounted — measuring now under-sized the box and clipped the label.
        # sizeHint() (below) always measures the *current* font instead.

    def sizeHint(self) -> QSize:
        text_width = QFontMetrics(self.font()).horizontalAdvance(self._text)
        return QSize(self._BOX + self._GAP + text_width + self._RIGHT_PAD, 24)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self.updateGeometry()

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        checked = bool(checked)
        if checked == self._checked:
            return
        self._checked = checked
        self.update()
        self.toggled.emit(self._checked)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self.font())

        box_rect = QRectF(0, (self.height() - self._BOX) / 2, self._BOX, self._BOX)
        box_path = QPainterPath()
        box_path.addRoundedRect(box_rect, 4, 4)

        if self._checked:
            p.fillPath(box_path, QColor(212, 66, 66, 255))
            p.setPen(QPen(QColor(212, 66, 66), 1.0))
        else:
            p.fillPath(box_path, QColor(255, 255, 255, 28 if self._hover else 15))
            p.setPen(QPen(QColor(255, 255, 255, 90), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(box_rect, 4, 4)

        if self._checked:
            check_pen = QPen(QColor(255, 255, 255), 2.0)
            check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            check_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(check_pen)
            x, y = box_rect.left(), box_rect.top()
            p.drawLine(QPointF(x + 3.5, y + 8.5), QPointF(x + 6.5, y + 11.5))
            p.drawLine(QPointF(x + 6.5, y + 11.5), QPointF(x + 12.5, y + 4.5))

        p.setPen(QColor(200, 203, 210, 235 if self._checked or self._hover else 190))
        text_rect = QRectF(self._BOX + self._GAP, 0, self.width() - self._BOX - self._GAP, self.height())
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)

        p.end()


class MiniPlayer(QFrame):
    """Fixed bar at the bottom showing current playback info and controls."""

    prev_clicked = Signal()
    next_clicked = Signal()
    close_clicked = Signal()
    bar_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MiniPlayer")
        self.setFixedHeight(62)
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(14)

        # Thumbnail
        self._thumb = QLabel()
        self._thumb.setFixedSize(40, 40)
        self._thumb.setStyleSheet("background: rgba(255,255,255,0.06); border-radius: 6px;")
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._thumb)

        # Info section (clickable)
        info_widget = QWidget()
        info_widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        self._anime_label = QLabel("")
        self._anime_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #F2F3F5;")
        info_layout.addWidget(self._anime_label)

        self._episode_label = QLabel("")
        self._episode_label.setStyleSheet("font-size: 11px; color: #A7ACB5;")
        info_layout.addWidget(self._episode_label)

        info_widget.mousePressEvent = lambda e: self.bar_clicked.emit()
        layout.addWidget(info_widget, 1)

        # Autoplay toggle (a setting, not a transport control — kept visually
        # distinct from the buttons below via a divider and extra spacing)
        self.autoplay_checkbox = _AutoplayToggle("Auto-play")
        self.autoplay_checkbox.setToolTip("Reproduzir proximo episodio automaticamente")
        layout.addWidget(self.autoplay_checkbox)

        layout.addSpacing(4)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFixedWidth(1)
        divider.setFixedHeight(26)
        divider.setStyleSheet("background: rgba(255,255,255,0.08); border: none;")
        layout.addWidget(divider)
        layout.addSpacing(10)

        # Transport controls — prev/next grouped tightly as one unit
        transport = QHBoxLayout()
        transport.setSpacing(4)
        transport.setContentsMargins(0, 0, 0, 0)

        self._prev_btn = QPushButton()
        self._prev_btn.setObjectName("IconButton")
        self._prev_btn.setIcon(QIcon(icon_skip_back(18, "#F2F3F5")))
        self._prev_btn.setIconSize(QSize(18, 18))
        self._prev_btn.setToolTip("Episodio anterior")
        self._prev_btn.setFixedSize(36, 36)
        self._prev_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._prev_btn.clicked.connect(self.prev_clicked.emit)
        transport.addWidget(self._prev_btn)

        self._next_btn = QPushButton()
        self._next_btn.setObjectName("IconButton")
        self._next_btn.setIcon(QIcon(icon_skip_forward(18, "#F2F3F5")))
        self._next_btn.setIconSize(QSize(18, 18))
        self._next_btn.setToolTip("Proximo episodio")
        self._next_btn.setFixedSize(36, 36)
        self._next_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._next_btn.clicked.connect(self.next_clicked.emit)
        transport.addWidget(self._next_btn)

        layout.addLayout(transport)
        layout.addSpacing(10)

        # Close — a dismissive action, kept apart from transport controls
        self._close_btn = QPushButton()
        self._close_btn.setObjectName("IconButton")
        self._close_btn.setIcon(QIcon(icon_x(18, "#A7ACB5")))
        self._close_btn.setIconSize(QSize(18, 18))
        self._close_btn.setToolTip("Fechar player")
        self._close_btn.setFixedSize(36, 36)
        self._close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._close_btn.clicked.connect(self._on_close)
        layout.addWidget(self._close_btn)

    def show_playback(
        self,
        anime: str,
        episode_index: int,
        episode_count: int,
        cover_path: str | None = None,
    ) -> None:
        self._anime_label.setText(anime)
        self._episode_label.setText(f"Episodio {episode_index + 1} de {episode_count}")
        self._prev_btn.setEnabled(episode_index > 0)
        self._next_btn.setEnabled(episode_index < episode_count - 1)
        if cover_path:
            self._set_thumb(cover_path)
        else:
            self._thumb.setPixmap(generate_dynamic_cover(anime, 40, 40, radius=6))
        self.setVisible(True)

    def update_controls(self, episode_index: int, episode_count: int) -> None:
        self._episode_label.setText(f"Episodio {episode_index + 1} de {episode_count}")
        self._prev_btn.setEnabled(episode_index > 0)
        self._next_btn.setEnabled(episode_index < episode_count - 1)

    def _set_thumb(self, path: str) -> None:
        source = QPixmap(path)
        if source.isNull():
            return
        scaled = source.scaled(
            40, 40,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (scaled.width() - 40) // 2
        y = (scaled.height() - 40) // 2
        cropped = scaled.copy(x, y, 40, 40)
        rounded = QPixmap(40, 40)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, 40, 40, 6, 6)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self._thumb.setPixmap(rounded)

    def _on_close(self) -> None:
        self.setVisible(False)
        self.close_clicked.emit()

    def is_autoplay(self) -> bool:
        return self.autoplay_checkbox.isChecked()
