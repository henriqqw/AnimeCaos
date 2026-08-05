from __future__ import annotations

import datetime
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from animecaos.ui.gui.icons import icon_clock, icon_loader
from animecaos.ui.gui.widgets.anime_card import AnimeCard
from animecaos.ui.gui.widgets.card_scroll import HorizontalCardScroll
from animecaos.ui.gui.widgets.spotlight_banner import SpotlightBanner


class _AniListOfflineBanner(QFrame):
    """Dismissible warning banner shown when AniList API is unavailable."""

    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background: rgba(212,100,50,0.15); border: 1px solid rgba(212,100,50,0.4);"
            " border-radius: 10px; }"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 12, 12)
        row.setSpacing(12)

        self._icon = QLabel("!")
        self._icon.setStyleSheet("color: #D46432; font-size: 18px; font-weight: 900; background: transparent; border: none;")
        self._icon.setFixedWidth(22)
        row.addWidget(self._icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            "color: #F2C97D; font-size: 13px; font-weight: 700; background: transparent; border: none;"
        )
        self._desc_lbl = QLabel()
        self._desc_lbl.setStyleSheet(
            "color: rgba(242,201,125,0.75); font-size: 12px; background: transparent; border: none;"
        )
        self._desc_lbl.setWordWrap(True)
        text_col.addWidget(self._title_lbl)
        text_col.addWidget(self._desc_lbl)
        row.addLayout(text_col, 1)

        close_btn = QPushButton("x")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: rgba(242,201,125,0.6);"
            " font-size: 14px; } QPushButton:hover { color: #F2C97D; }"
        )
        close_btn.clicked.connect(self._dismiss)
        row.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

    def update_status(self, title: str, description: str) -> None:
        self._title_lbl.setText(title)
        self._desc_lbl.setText(description)

    def _dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()


class _AniListOfflineBanner(QFrame):
    """Dismissible warning banner shown when AniList API is unavailable."""

    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background: rgba(212,100,50,0.15); border: 1px solid rgba(212,100,50,0.4);"
            " border-radius: 10px; }"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 12, 12)
        row.setSpacing(12)

        self._icon = QLabel("!")
        self._icon.setStyleSheet("color: #D46432; font-size: 18px; font-weight: 900; background: transparent; border: none;")
        self._icon.setFixedWidth(22)
        row.addWidget(self._icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            "color: #F2C97D; font-size: 13px; font-weight: 700; background: transparent; border: none;"
        )
        self._desc_lbl = QLabel()
        self._desc_lbl.setStyleSheet(
            "color: rgba(242,201,125,0.75); font-size: 12px; background: transparent; border: none;"
        )
        self._desc_lbl.setWordWrap(True)
        text_col.addWidget(self._title_lbl)
        text_col.addWidget(self._desc_lbl)
        row.addLayout(text_col, 1)

        close_btn = QPushButton("x")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: rgba(242,201,125,0.6);"
            " font-size: 14px; } QPushButton:hover { color: #F2C97D; }"
        )
        close_btn.clicked.connect(self._dismiss)
        row.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

    def update_status(self, title: str, description: str) -> None:
        self._title_lbl.setText(title)
        self._desc_lbl.setText(description)

    def _dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()


class HomeView(QWidget):
    """Landing view with Continue Watching section."""

    history_clicked = Signal(object)
    discover_clicked = Signal(object)
    anilist_page_requested = Signal(int)  # anilist_id
    list_toggle_requested = Signal(object)
    preview_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        # Scrolling the page moves cards out from under any shown hover-preview
        # panel (which is reparented onto the top-level window and doesn't
        # move with them), so it must close rather than float in place.
        self._scroll.verticalScrollBar().valueChanged.connect(lambda _: AnimeCard.suppress_previews())

        # Root container — zero margins so spotlight fills edge to edge
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── AniList offline banner (inside padded inner) ──
        self._offline_banner = _AniListOfflineBanner()
        self._offline_banner.hide()

        # ── Spotlight Hero — full width, no side margins ──
        self.spotlight = SpotlightBanner()
        self.spotlight.watch_clicked.connect(self.discover_clicked.emit)
        self.spotlight.anilist_clicked.connect(self.anilist_page_requested.emit)
        self.spotlight.hide()
        root_layout.addWidget(self.spotlight)

        # ── Inner padded section for all other content ──
        inner_widget = QWidget()
        inner_widget.setStyleSheet("background: transparent;")
        self._content = QVBoxLayout(inner_widget)
        self._content.setContentsMargins(24, 20, 24, 24)
        self._content.setSpacing(24)

        self._content.addWidget(self._offline_banner)

        # ── Em Alta ──
        self.trending_section = HorizontalCardScroll("Em Alta")
        self.trending_section.card_clicked.connect(self.discover_clicked.emit)
        self.trending_section.list_toggle_requested.connect(self.list_toggle_requested.emit)
        self.trending_section.preview_requested.connect(self.preview_requested.emit)
        self.trending_section.set_empty(
            icon_loader(36, "rgba(255,255,255,0.15)"),
            "Carregando...",
            "",
        )
        self._content.addWidget(self.trending_section)

        # ── Continue Watching ──
        self.history_section = HorizontalCardScroll("Continue Assistindo")
        self.history_section.card_clicked.connect(self.history_clicked.emit)
        self.history_section.list_toggle_requested.connect(self.list_toggle_requested.emit)
        self.history_section.preview_requested.connect(self.preview_requested.emit)
        self.history_section.set_empty(
            icon_clock(36, "rgba(255,255,255,0.15)"),
            "Nenhum historico",
            "Os animes que voce assistir aparecerao aqui",
        )
        self._content.addWidget(self.history_section)

        # ── Temporada Atual ──
        self._seasonal_title = self._current_season_label()
        self.seasonal_section = HorizontalCardScroll(self._seasonal_title)
        self.seasonal_section.card_clicked.connect(self.discover_clicked.emit)
        self.seasonal_section.list_toggle_requested.connect(self.list_toggle_requested.emit)
        self.seasonal_section.preview_requested.connect(self.preview_requested.emit)
        self.seasonal_section.set_empty(
            icon_loader(36, "rgba(255,255,255,0.15)"),
            "Carregando...",
            "",
        )
        self._content.addWidget(self.seasonal_section)

        self._content.addStretch()

        root_layout.addWidget(inner_widget)

        self._scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

    @staticmethod
    def _current_season_label() -> str:
        from datetime import datetime
        month = datetime.now().month
        year = datetime.now().year
        if month <= 3:
            season = "Inverno"
        elif month <= 6:
            season = "Primavera"
        elif month <= 9:
            season = "Verão"
        else:
            season = "Outono"
        return f"Temporada Atual — {season} {year}"

    def set_history_cards(self, items: list[dict[str, Any]]) -> None:
        if items:
            self.history_section.set_cards(items)
        else:
            self.history_section.set_empty(
                icon_clock(36, "rgba(255,255,255,0.15)"),
                "Nenhum historico",
                "Os animes que voce assistir aparecerao aqui",
            )

    def update_card_cover(self, title: str, cover_path: str) -> None:
        self.history_section.update_card_cover(title, cover_path)

    def set_trending_cards(self, items: list[Any]) -> None:
        if items:
            self.trending_section.set_cards(items)
        else:
            self.trending_section.set_empty(
                icon_loader(36, "rgba(255,255,255,0.10)"),
                "Sem resultados",
                "Nao foi possivel carregar os dados",
            )

    def set_seasonal_cards(self, items: list[Any]) -> None:
        if items:
            self.seasonal_section.set_cards(items)
        else:
            self.seasonal_section.set_empty(
                icon_loader(36, "rgba(255,255,255,0.10)"),
                "Sem resultados",
                "Nao foi possivel carregar os dados",
            )

    def remove_trending_card(self, title: str) -> None:
        self.trending_section.remove_card(title)

    def remove_seasonal_card(self, title: str) -> None:
        self.seasonal_section.remove_card(title)

    def trim_discover_sections(self, max_cards: int = 10) -> None:
        self.trending_section.trim_to(max_cards)
        self.seasonal_section.trim_to(max_cards)

    def set_spotlights(self, cards: list[dict]) -> None:
        self.spotlight.set_cards(cards)

    def set_spotlight_banner(self, path: str) -> None:
        self.spotlight.set_banner(path)

    def set_spotlight_cover(self, path: str) -> None:
        self.spotlight.set_cover(path)

    def update_discover_cover(self, title: str, cover_path: str) -> None:
        self.trending_section.update_card_cover(title, cover_path)
        self.seasonal_section.update_card_cover(title, cover_path)

    def update_card_preview(
        self, title: str, score: float | None = None, episodes: int | None = None,
        description: str | None = None,
    ) -> None:
        self.trending_section.update_card_preview(title, score, episodes, description)
        self.seasonal_section.update_card_preview(title, score, episodes, description)
        self.history_section.update_card_preview(title, score, episodes, description)

    def update_card_in_list(self, title: str, in_list: bool) -> None:
        self.trending_section.update_card_in_list(title, in_list)
        self.seasonal_section.update_card_in_list(title, in_list)
        self.history_section.update_card_in_list(title, in_list)

    def show_anilist_offline_banner(self, title: str, description: str) -> None:
        self._offline_banner.update_status(title, description)
        self._offline_banner.show()

    def hide_anilist_offline_banner(self) -> None:
        self._offline_banner.hide()


# ═══════════════════════════════════════════════════════════════════
#  SEARCH VIEW
# ═══════════════════════════════════════════════════════════════════

