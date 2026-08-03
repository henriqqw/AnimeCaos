from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


def _title_hue(title: str) -> int:
    """Deterministic hue (0-359) from title string."""
    h = 0
    for ch in title:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % 360


def generate_dynamic_cover(title: str, width: int, height: int, radius: int = 8) -> QPixmap:
    """Create a gradient cover with the anime title when no image is available."""
    hue = _title_hue(title)
    c1 = QColor.fromHsl(hue, 140, 45)
    c2 = QColor.fromHsl((hue + 40) % 360, 120, 30)

    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    clip = QPainterPath()
    clip.addRoundedRect(0, 0, width, height, radius, radius)
    painter.setClipPath(clip)

    grad = QLinearGradient(0, 0, width * 0.3, height)
    grad.setColorAt(0.0, c1)
    grad.setColorAt(1.0, c2)
    painter.fillRect(0, 0, width, height, grad)

    overlay = QLinearGradient(0, 0, 0, height)
    overlay.setColorAt(0.0, QColor(0, 0, 0, 0))
    overlay.setColorAt(1.0, QColor(0, 0, 0, 80))
    painter.fillRect(0, 0, width, height, overlay)

    font = QFont("Segoe UI", 1)
    font.setWeight(QFont.Weight.Bold)
    font.setPixelSize(max(14, width // 7))
    painter.setFont(font)
    painter.setPen(QPen(QColor(255, 255, 255, 230)))

    margin = int(width * 0.1)
    text_rect = pixmap.rect().adjusted(margin, height // 3, -margin, -margin)
    painter.drawText(
        text_rect,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom | Qt.TextFlag.TextWordWrap,
        title.upper(),
    )

    painter.end()
    return pixmap


class AnimeCard(QFrame):
    """Visual card with cover thumbnail, title, and optional badge."""

    clicked = Signal(object)
    double_clicked = Signal(object)

    CARD_WIDTH = 150
    COVER_HEIGHT = 210
    CARD_HEIGHT = 280

    def __init__(self, data: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AnimeCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.data = data

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 8)
        layout.setSpacing(6)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(self.CARD_WIDTH - 12, self.COVER_HEIGHT)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet(
            "background: rgba(255,255,255,0.05); border-radius: 8px;"
        )
        self.cover_label.setText("")

        cover_path = data.get("cover_path")
        if cover_path and os.path.exists(str(cover_path)):
            self._set_cover(str(cover_path))
        else:
            title = data.get("title", "")
            if title:
                self.cover_label.setPixmap(
                    generate_dynamic_cover(title, self.CARD_WIDTH - 12, self.COVER_HEIGHT)
                )
        layout.addWidget(self.cover_label)

        self.title_label = QLabel(data.get("title", ""))
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(34)
        self.title_label.setStyleSheet(
            "font-size: 12px; font-weight: 500; color: #E6E7EA;"
        )
        layout.addWidget(self.title_label)

        badge_text = data.get("badge", "")
        if badge_text:
            badge = QLabel(badge_text)
            badge.setObjectName("Caption")
            layout.addWidget(badge)

        layout.addStretch()

    def _set_cover(self, path: str) -> None:
        w = self.CARD_WIDTH - 12
        h = self.COVER_HEIGHT
        source = QPixmap(path)
        if source.isNull():
            return

        scaled = source.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (scaled.width() - w) // 2
        y = (scaled.height() - h) // 2
        cropped = scaled.copy(x, y, w, h)

        rounded = QPixmap(w, h)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, 8, 8)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()

        self.cover_label.setPixmap(rounded)

    def set_cover_from_path(self, path: str) -> None:
        self._set_cover(path)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.data)
        super().mouseDoubleClickEvent(event)
