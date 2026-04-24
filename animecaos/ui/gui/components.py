"""
Reusable UI components for the AnimeCaos redesign.

- EmptyState: placeholder for empty lists (with Lucide icon pixmap)
- AnimeCard: visual card with cover thumbnail
- HorizontalCardScroll: horizontal scrollable row of cards
- EpisodeRow: rich episode list item with play feedback animation
"""
from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import (
    Qt,
    Signal,
    QSize,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    Property,
    QObject,
    QEvent,
)
from PySide6.QtGui import (
    QPixmap, QPainter, QPainterPath, QFont, QCursor, QIcon, QColor,
    QLinearGradient, QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from .icons import (
    icon_play,
    icon_download,
    icon_clock,
    icon_star,
    icon_search,
    icon_search_x,
    icon_monitor,
)


# ── Dynamic Cover Generator ─────────────────────────────────────

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

    # Clip to rounded rect
    clip = QPainterPath()
    clip.addRoundedRect(0, 0, width, height, radius, radius)
    painter.setClipPath(clip)

    # Gradient background
    grad = QLinearGradient(0, 0, width * 0.3, height)
    grad.setColorAt(0.0, c1)
    grad.setColorAt(1.0, c2)
    painter.fillRect(0, 0, width, height, grad)

    # Subtle overlay for depth
    overlay = QLinearGradient(0, 0, 0, height)
    overlay.setColorAt(0.0, QColor(0, 0, 0, 0))
    overlay.setColorAt(1.0, QColor(0, 0, 0, 80))
    painter.fillRect(0, 0, width, height, overlay)

    # Title text
    font = QFont("Segoe UI", 1)
    font.setWeight(QFont.Weight.Bold)
    # Scale font to fit ~70% width
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


# ── Empty State ──────────────────────────────────────────────────

class EmptyState(QWidget):
    """Shown when a section has no data. Displays icon pixmap + title + subtitle."""

    def __init__(
        self,
        icon_pixmap: QPixmap | None = None,
        title: str = "Nada aqui ainda",
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        if icon_pixmap:
            icon_label = QLabel()
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setPixmap(icon_pixmap)
            layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setObjectName("EmptyStateTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("EmptyStateSubtitle")
            sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub_label.setWordWrap(True)
            layout.addWidget(sub_label)


# ── Anime Card ───────────────────────────────────────────────────

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

        # Cover image
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
            # Dynamic placeholder cover based on title
            title = data.get("title", "")
            if title:
                self.cover_label.setPixmap(
                    generate_dynamic_cover(title, self.CARD_WIDTH - 12, self.COVER_HEIGHT)
                )
        layout.addWidget(self.cover_label)

        # Title (max 2 lines)
        self.title_label = QLabel(data.get("title", ""))
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(34)
        self.title_label.setStyleSheet(
            "font-size: 12px; font-weight: 500; color: #E6E7EA;"
        )
        layout.addWidget(self.title_label)

        # Badge (optional)
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


# ── Horizontal Card Scroll ───────────────────────────────────────

class HorizontalCardScroll(QWidget):
    """Horizontal scrollable row of AnimeCard widgets with section header."""

    card_clicked = Signal(object)
    card_double_clicked = Signal(object)

    def __init__(
        self,
        title: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        if title:
            header = QHBoxLayout()
            lbl = QLabel(title)
            lbl.setObjectName("SectionTitle")
            header.addWidget(lbl)
            header.addStretch()
            outer.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(AnimeCard.CARD_HEIGHT + 14)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._row_layout = QHBoxLayout(self._container)
        self._row_layout.setContentsMargins(0, 0, 0, 0)
        self._row_layout.setSpacing(12)
        self._row_layout.addStretch()

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll)

        # Redirect vertical wheel → horizontal scroll
        self._scroll.viewport().installEventFilter(self)
        self._container.installEventFilter(self)

        self._cards: list[AnimeCard] = []
        self._empty_state: EmptyState | None = None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel:
            delta = event.angleDelta().y()
            if delta == 0:
                delta = -event.angleDelta().x()
            bar = self._scroll.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
            return True
        return super().eventFilter(obj, event)

    def set_cards(self, items: list[dict[str, Any]]) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        if self._empty_state:
            self._empty_state.setParent(None)
            self._empty_state.deleteLater()
            self._empty_state = None

        while self._row_layout.count():
            self._row_layout.takeAt(0)

        if not items:
            return

        for data in items:
            card = AnimeCard(data)
            card.clicked.connect(self.card_clicked.emit)
            card.double_clicked.connect(self.card_double_clicked.emit)
            self._cards.append(card)
            self._row_layout.addWidget(card)

        self._row_layout.addStretch()

    def set_empty(self, icon_pixmap: QPixmap | None, title: str, subtitle: str) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        while self._row_layout.count():
            self._row_layout.takeAt(0)

        if self._empty_state:
            self._empty_state.setParent(None)
            self._empty_state.deleteLater()

        self._empty_state = EmptyState(icon_pixmap, title, subtitle)
        self._empty_state.setFixedHeight(AnimeCard.CARD_HEIGHT)
        self._row_layout.addStretch()
        self._row_layout.addWidget(self._empty_state)
        self._row_layout.addStretch()

    def get_card(self, index: int) -> AnimeCard | None:
        if 0 <= index < len(self._cards):
            return self._cards[index]
        return None

    def card_count(self) -> int:
        return len(self._cards)

    def update_card_cover(self, title: str, cover_path: str) -> None:
        for card in self._cards:
            if card.data.get("title") == title:
                card.set_cover_from_path(cover_path)
                break


# ── Episode Row ──────────────────────────────────────────────────

class EpisodeRow(QFrame):
    """Rich episode list item with play and download icon buttons + loading feedback."""

    play_clicked = Signal(int)
    download_clicked = Signal(int)

    def __init__(
        self,
        index: int,
        title: str,
        is_current: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("EpisodeRow")
        self.index = index
        self._is_loading = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Episode number
        self._num_label = QLabel(f"{index + 1:02d}")
        self._num_label.setFixedWidth(30)
        self._num_label.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {'#D44242' if is_current else '#A7ACB5'};"
        )
        layout.addWidget(self._num_label)

        # Title
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet("font-size: 13px; color: #E6E7EA;")
        self._title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._title_label, 1)

        # Loading indicator (hidden by default)
        self._loading_label = QLabel("Carregando...")
        self._loading_label.setStyleSheet("font-size: 11px; color: #D44242; font-weight: 500;")
        self._loading_label.setVisible(False)
        layout.addWidget(self._loading_label)

        # Play button with Lucide icon
        self._play_btn = QPushButton()
        self._play_btn.setObjectName("IconButton")
        self._play_btn.setIcon(QIcon(icon_play(16, "#F2F3F5")))
        self._play_btn.setIconSize(QSize(16, 16))
        self._play_btn.setToolTip("Reproduzir")
        self._play_btn.setFixedSize(32, 32)
        self._play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._play_btn.clicked.connect(self._on_play)
        layout.addWidget(self._play_btn)

        # Download button with Lucide icon
        self._dl_btn = QPushButton()
        self._dl_btn.setObjectName("IconButton")
        self._dl_btn.setIcon(QIcon(icon_download(16, "#A7ACB5")))
        self._dl_btn.setIconSize(QSize(16, 16))
        self._dl_btn.setToolTip("Baixar")
        self._dl_btn.setFixedSize(32, 32)
        self._dl_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._dl_btn.clicked.connect(lambda: self.download_clicked.emit(self.index))
        layout.addWidget(self._dl_btn)

    def _on_play(self) -> None:
        self.show_loading()
        self.play_clicked.emit(self.index)

    def show_loading(self) -> None:
        """Show loading feedback when play is clicked."""
        self._is_loading = True
        self._loading_label.setVisible(True)
        self._play_btn.setEnabled(False)
        self._dl_btn.setEnabled(False)
        self.setStyleSheet(
            "QFrame#EpisodeRow { background-color: rgba(212, 66, 66, 0.10); "
            "border: 1px solid rgba(212, 66, 66, 0.25); }"
        )

        # Stop any previous pulse before creating a new one
        if hasattr(self, "_pulse_anim") and self._pulse_anim is not None:
            self._pulse_anim.stop()
            self._pulse_anim = None

        # Pulsing animation on loading label
        self._pulse_effect = QGraphicsOpacityEffect(self._loading_label)
        self._pulse_effect.setOpacity(1.0)
        self._loading_label.setGraphicsEffect(self._pulse_effect)
        self._pulse_anim = QPropertyAnimation(self._pulse_effect, b"opacity", self._loading_label)
        self._pulse_anim.setDuration(800)
        self._pulse_anim.setStartValue(1.0)
        self._pulse_anim.setEndValue(0.3)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)
        self._pulse_anim.start()

    def hide_loading(self) -> None:
        """Stop loading feedback."""
        self._is_loading = False
        self._loading_label.setVisible(False)
        self._play_btn.setEnabled(True)
        self._dl_btn.setEnabled(True)
        if hasattr(self, "_pulse_anim"):
            self._pulse_anim.stop()
        self._loading_label.setGraphicsEffect(None)

    def set_current(self, current: bool) -> None:
        self.hide_loading()
        if current:
            self._num_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #D44242;")
            self.setStyleSheet(
                "QFrame#EpisodeRow { background-color: rgba(212, 66, 66, 0.15); "
                "border: 1px solid rgba(212, 66, 66, 0.3); }"
            )
        else:
            self._num_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #A7ACB5;")
            self.setStyleSheet("")
