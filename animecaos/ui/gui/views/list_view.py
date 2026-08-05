from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from animecaos.ui.gui.icons import icon_bookmark
from animecaos.ui.gui.widgets.anime_card import AnimeCard
from animecaos.ui.gui.widgets.empty_state import EmptyState


class _FlowLayout(QVBoxLayout):
    """Grid-based flow layout for cards."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 14) -> None:
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)
        self._spacing = spacing
        self._widgets: list[QWidget] = []
        self._flow_widget = QWidget()
        self._flow_widget.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._flow_widget)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(spacing)
        self._col_count = 7
        self._row = 0
        self._col = 0
        super().addWidget(self._flow_widget)

    def addWidget(self, widget: QWidget) -> None:
        self._widgets.append(widget)
        self._grid.addWidget(widget, self._row, self._col)
        self._col += 1
        if self._col >= self._col_count:
            self._col = 0
            self._row += 1

    def removeWidget(self, widget: QWidget) -> None:
        self._grid.removeWidget(widget)
        if widget in self._widgets:
            self._widgets.remove(widget)

    def clear_all(self) -> None:
        # Destroy the old flow_widget+grid entirely so that QGridLayout does not
        # retain residual row/column structure (empty rows would keep taking up
        # vertical space and shift subsequent cards to wrong positions).
        if self._flow_widget is not None:
            super().removeWidget(self._flow_widget)
            self._flow_widget.setParent(None)
            self._flow_widget.deleteLater()

        self._flow_widget = QWidget()
        self._flow_widget.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._flow_widget)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(self._spacing)
        super().addWidget(self._flow_widget)

        self._widgets.clear()
        self._row = 0
        self._col = 0


class ListView(QWidget):
    """User's personal watchlist. Animes are added from the detail page and
    can be removed either from there or directly off a card here."""

    anime_clicked = Signal(object)
    remove_clicked = Signal(str)
    preview_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        # Scrolling the page moves cards out from under any shown hover-preview
        # panel (which is reparented onto the top-level window and doesn't
        # move with them), so it must close rather than float in place.
        self._scroll.verticalScrollBar().valueChanged.connect(lambda _: AnimeCard.suppress_previews())

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._content = QVBoxLayout(container)
        self._content.setContentsMargins(24, 16, 24, 24)
        self._content.setSpacing(16)

        header = QHBoxLayout()
        title_lbl = QLabel("Minha Lista")
        title_lbl.setObjectName("SectionTitleLarge")
        header.addWidget(title_lbl)

        self._count_badge = QLabel("")
        self._count_badge.setObjectName("Badge")
        self._count_badge.setVisible(False)
        header.addWidget(self._count_badge)

        header.addStretch()
        self._content.addLayout(header)

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: transparent;")
        self._grid_layout = _FlowLayout(self._grid_container, spacing=14)
        self._content.addWidget(self._grid_container)

        self._empty_state = EmptyState(
            icon_bookmark(48, "rgba(255,255,255,0.12)"),
            "Sua lista está vazia",
            "Adicione animes à sua lista na página de detalhes\npara encontrá-los facilmente aqui depois",
        )
        self._empty_state.setMinimumHeight(300)
        self._content.addWidget(self._empty_state)

        self._content.addStretch()
        self._scroll.setWidget(container)
        outer.addWidget(self._scroll)

        self._cards: list[AnimeCard] = []
        self.set_animes([])

    def set_animes(self, items: list[dict[str, Any]]) -> None:
        self._clear_cards()

        if not items:
            self._empty_state.setVisible(True)
            self._grid_container.setVisible(False)
            self._count_badge.setVisible(False)
            return

        self._empty_state.setVisible(False)
        self._grid_container.setVisible(True)
        count = len(items)
        self._count_badge.setText(f"{count} anime{'s' if count > 1 else ''}")
        self._count_badge.setVisible(True)

        for data in items:
            data.setdefault("in_list", True)
            card = AnimeCard(data, removable=True)
            card.clicked.connect(self.anime_clicked.emit)
            card.remove_clicked.connect(lambda d: self.remove_clicked.emit(d.get("title", "")))
            # Every card here is already in the watchlist by definition, so the
            # hover panel's bookmark toggle means the same thing as the X button.
            card.list_toggle_clicked.connect(lambda d: self.remove_clicked.emit(d.get("title", "")))
            card.preview_requested.connect(self.preview_requested.emit)
            self._cards.append(card)
            self._grid_layout.addWidget(card)

    def update_cover(self, title: str, cover_path: str) -> None:
        for card in self._cards:
            if card.data.get("title") == title:
                card.set_cover_from_path(cover_path)
                break

    def update_card_preview(
        self, title: str, score: float | None = None, episodes: int | None = None,
        description: str | None = None,
    ) -> None:
        for card in self._cards:
            if card.data.get("title") == title:
                card.set_preview_data(score=score, episodes=episodes, description=description)
                break

    def _clear_cards(self) -> None:
        AnimeCard.suppress_previews()
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        self._grid_layout.clear_all()
