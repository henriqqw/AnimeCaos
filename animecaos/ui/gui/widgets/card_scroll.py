from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from .anime_card import AnimeCard
from .empty_state import EmptyState


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

        self._scroll.viewport().installEventFilter(self)
        self._container.installEventFilter(self)

        self._cards: list[AnimeCard] = []
        self._empty_state: EmptyState | None = None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Wheel:
            dx = event.angleDelta().x()
            dy = event.angleDelta().y()
            if abs(dy) >= abs(dx):
                return False
            delta = dx if dx != 0 else -dy
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

    def trim_to(self, max_cards: int) -> None:
        while len(self._cards) > max_cards:
            card = self._cards.pop()
            self._row_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()

    def remove_card(self, title: str) -> None:
        for card in list(self._cards):
            if card.data.get("title") == title:
                self._row_layout.removeWidget(card)
                card.setParent(None)
                card.deleteLater()
                self._cards.remove(card)
                break

    def update_card_cover(self, title: str, cover_path: str) -> None:
        for card in self._cards:
            if card.data.get("title") == title:
                card.set_cover_from_path(cover_path)
                break
