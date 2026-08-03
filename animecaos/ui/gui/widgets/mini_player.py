"""
Persistent mini-player bar with Lucide icons.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QCursor, QPixmap, QPainter, QPainterPath, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .anime_card import generate_dynamic_cover
from animecaos.ui.gui.icons import icon_skip_back, icon_skip_forward, icon_x


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

        # Autoplay checkbox
        self.autoplay_checkbox = QCheckBox("Auto-play")
        self.autoplay_checkbox.setChecked(True)
        self.autoplay_checkbox.setToolTip("Reproduzir proximo episodio automaticamente")
        layout.addWidget(self.autoplay_checkbox)

        # Previous
        self._prev_btn = QPushButton()
        self._prev_btn.setObjectName("IconButton")
        self._prev_btn.setIcon(QIcon(icon_skip_back(18, "#F2F3F5")))
        self._prev_btn.setIconSize(QSize(18, 18))
        self._prev_btn.setToolTip("Episodio anterior")
        self._prev_btn.setFixedSize(36, 36)
        self._prev_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._prev_btn.clicked.connect(self.prev_clicked.emit)
        layout.addWidget(self._prev_btn)

        # Next
        self._next_btn = QPushButton()
        self._next_btn.setObjectName("IconButton")
        self._next_btn.setIcon(QIcon(icon_skip_forward(18, "#F2F3F5")))
        self._next_btn.setIconSize(QSize(18, 18))
        self._next_btn.setToolTip("Proximo episodio")
        self._next_btn.setFixedSize(36, 36)
        self._next_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._next_btn.clicked.connect(self.next_clicked.emit)
        layout.addWidget(self._next_btn)

        # Close
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
