from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QPushButton, QScrollArea, QSizePolicy, QTextEdit, QVBoxLayout, QWidget

from animecaos.ui.gui.icons import icon_arrow_left, icon_book, icon_clock, icon_folder, icon_loader, icon_monitor, icon_search, icon_trash, icon_user, icon_x
from animecaos.ui.gui.widgets.animated_button import AnimatedButton
from animecaos.ui.gui.widgets.episode_row import EpisodeRow
from animecaos.ui.gui.widgets.anime_card import generate_dynamic_cover
from animecaos.ui.gui.widgets.empty_state import EmptyState


class _FlowLayout(QVBoxLayout):
    """Grid-based flow layout for cards."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 12) -> None:
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
        for w in self._widgets:
            self._grid.removeWidget(w)
        self._widgets.clear()
        self._row = 0
        self._col = 0


# ═══════════════════════════════════════════════════════════════════
#  ANIME DETAIL VIEW
# ═══════════════════════════════════════════════════════════════════

class AnimeDetailView(QWidget):
    """Full anime details page with cover, synopsis, and episode list."""

    back_clicked = Signal()
    play_clicked = Signal(int)
    download_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_anime: str = ""
        self._episode_count: int = 0
        self._current_episode_idx: int = -1
        self._loading_index: int = -1

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._content = QVBoxLayout(container)
        self._content.setContentsMargins(24, 16, 24, 24)
        self._content.setSpacing(20)

        # ── Back button ──
        header = QHBoxLayout()
        self._back_btn = QPushButton(" Voltar")
        self._back_btn.setObjectName("IconButton")
        self._back_btn.setIcon(QIcon(icon_arrow_left(16, "#A7ACB5")))
        self._back_btn.setIconSize(QSize(16, 16))
        self._back_btn.setStyleSheet("font-size: 14px; padding: 8px 16px;")
        self._back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._back_btn.clicked.connect(self.back_clicked.emit)
        header.addWidget(self._back_btn)
        header.addStretch()
        self._content.addLayout(header)

        # ── Metadata section ──
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(24)

        self._cover_label = QLabel()
        self._cover_label.setFixedSize(200, 280)
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setStyleSheet(
            "background: rgba(255,255,255,0.05); border-radius: 12px;"
        )
        meta_layout.addWidget(self._cover_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(12)

        self._title_label = QLabel("")
        self._title_label.setObjectName("ViewTitle")
        self._title_label.setWordWrap(True)
        info_layout.addWidget(self._title_label)

        self._synopsis = QTextEdit()
        self._synopsis.setReadOnly(True)
        self._synopsis.setFrameShape(QFrame.Shape.NoFrame)
        self._synopsis.setObjectName("MutedText")
        self._synopsis.setStyleSheet(
            "font-size: 13px; color: #A7ACB5; background: transparent; border: none;"
        )
        self._synopsis.setMinimumHeight(80)
        self._synopsis.setMaximumHeight(180)
        info_layout.addWidget(self._synopsis, 1)

        info_layout.addStretch()
        meta_layout.addLayout(info_layout, 1)
        self._content.addLayout(meta_layout)

        # ── Episodes header ──
        ep_header = QHBoxLayout()
        self._ep_title = QLabel("Episodios")
        self._ep_title.setObjectName("SectionTitleLarge")
        ep_header.addWidget(self._ep_title)

        self._ep_count_badge = QLabel("")
        self._ep_count_badge.setObjectName("Badge")
        self._ep_count_badge.setVisible(False)
        ep_header.addWidget(self._ep_count_badge)
        ep_header.addStretch()
        self._content.addLayout(ep_header)

        # Loading
        self._loading_label = QLabel("Carregando episodios...")
        self._loading_label.setObjectName("MutedText")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setVisible(False)
        self._content.addWidget(self._loading_label)

        # Episodes container
        self._episodes_container = QWidget()
        self._episodes_container.setStyleSheet("background: transparent;")
        self._episodes_layout = QVBoxLayout(self._episodes_container)
        self._episodes_layout.setContentsMargins(0, 0, 0, 0)
        self._episodes_layout.setSpacing(4)
        self._content.addWidget(self._episodes_container)

        # Empty state
        self._episodes_empty = EmptyState(
            icon_monitor(48, "rgba(255,255,255,0.12)"),
            "Nenhum episodio carregado",
            "Aguarde o carregamento...",
        )
        self._episodes_empty.setVisible(False)
        self._content.addWidget(self._episodes_empty)

        self._content.addStretch()
        self._scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

        self._episode_rows: list[EpisodeRow] = []

    def set_anime(self, name: str) -> None:
        self._current_anime = name
        self._title_label.setText(name)
        # Show dynamic cover immediately while real cover loads async
        if name:
            self._cover_label.setPixmap(generate_dynamic_cover(name, 200, 280, radius=12))
        else:
            self._cover_label.clear()
            self._cover_label.setStyleSheet(
                "background: rgba(255,255,255,0.05); border-radius: 12px;"
            )
        self._synopsis.setText("Buscando detalhes...")
        self._clear_episodes()
        self._loading_label.setVisible(True)
        self._episodes_empty.setVisible(False)

    def set_metadata(self, description: str | None, cover_path: str | None) -> None:
        if description:
            self._synopsis.setText(description)
        else:
            self._synopsis.setText("Sem sinopse disponivel.")

        if cover_path and os.path.exists(cover_path):
            self._set_cover(cover_path)

    def _set_cover(self, path: str) -> None:
        w, h = 200, 280
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
        clip.addRoundedRect(0, 0, w, h, 12, 12)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self._cover_label.setPixmap(rounded)

    def set_episodes(self, titles: list[str], current_index: int = -1) -> None:
        self._loading_label.setVisible(False)
        self._clear_episodes()
        self._episode_count = len(titles)

        if not titles:
            self._episodes_empty.setVisible(True)
            self._ep_count_badge.setVisible(False)
            return

        self._episodes_empty.setVisible(False)
        self._ep_count_badge.setText(f"{len(titles)} eps")
        self._ep_count_badge.setVisible(True)

        for i, title in enumerate(titles):
            row = EpisodeRow(i, title, url="")
            row.play_clicked.connect(lambda _t, _u, idx=i: self.play_clicked.emit(idx))
            row.download_clicked.connect(lambda _t, _u, idx=i: self.download_clicked.emit(idx))
            if i == current_index:
                row.set_playing(True)
            self._episode_rows.append(row)
            self._episodes_layout.addWidget(row)

    def highlight_episode(self, index: int) -> None:
        self._current_episode_idx = index
        for row in self._episode_rows:
            row.set_playing(row.number == index)

    def set_episode_loading(self, index: int, loading: bool) -> None:
        """Show an inline spinner on one episode row, or clear it.

        Only one row is ever in the loading state at a time: starting a new
        load clears any previously loading row.
        """
        if loading:
            self._clear_all_loading_rows()
            self._loading_index = index
            self._apply_loading(index, True)
        elif index == self._loading_index:
            self._loading_index = -1
            self._apply_loading(index, False)

    def clear_loading(self) -> None:
        """Clear whatever episode row is currently showing a spinner."""
        if self._loading_index != -1:
            self._apply_loading(self._loading_index, False)
            self._loading_index = -1
        else:
            self._clear_all_loading_rows()

    def _clear_all_loading_rows(self) -> None:
        for row in self._episode_rows:
            if row._loading:
                row.set_loading(False)
        self._loading_index = -1

    def _apply_loading(self, index: int, loading: bool) -> None:
        for row in self._episode_rows:
            if row.number == index:
                row.set_loading(loading)
                break

    def _clear_episodes(self) -> None:
        self._loading_index = -1
        for row in self._episode_rows:
            row.setParent(None)
            row.deleteLater()
        self._episode_rows.clear()

    def scroll_to_episode(self, index: int) -> None:
        if 0 <= index < len(self._episode_rows):
            self._scroll.ensureWidgetVisible(self._episode_rows[index])

    @property
    def anime_name(self) -> str:
        return self._current_anime

    @property
    def episode_count(self) -> int:
        return self._episode_count


# ═══════════════════════════════════════════════════════════════════
#  ACCOUNT VIEW
# ═══════════════════════════════════════════════════════════════════

