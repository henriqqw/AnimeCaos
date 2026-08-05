from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from animecaos.services.downloads_service import DownloadEntry
from animecaos.services.manga_download_service import MangaDownloadEntry
from animecaos.ui.gui.icons import icon_book, icon_folder, icon_monitor, icon_trash
from animecaos.ui.gui.widgets.animated_button import AnimatedButton
from animecaos.ui.gui.widgets.anime_card import AnimeCard, generate_dynamic_cover
from animecaos.ui.gui.widgets.empty_state import EmptyState


_COVER_W, _COVER_H = 56, 80
_MAX_VISIBLE_EPS = 2


class _DownloadRow(QFrame):
    play_clicked   = Signal(object)
    delete_clicked = Signal(object)

    def __init__(self, entry: DownloadEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self.setObjectName("DownloadRow")
        self.setStyleSheet(
            "QFrame#DownloadRow { background: transparent; border-radius: 4px; }"
            "QFrame#DownloadRow:hover { background: rgba(255,255,255,0.04); }"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(10)

        ep_lbl = QLabel(f"EP {entry.episode_num:02d}")
        ep_lbl.setFixedWidth(42)
        ep_lbl.setFixedHeight(18)
        ep_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ep_lbl.setStyleSheet(
            "background: rgba(255,255,255,0.07); border-radius: 3px;"
            "color: #9CA3AF; font-size: 10px; font-weight: 700;"
        )
        row.addWidget(ep_lbl)

        title_lbl = QLabel(f"Epis\u00f3dio {entry.episode_num}")
        title_lbl.setStyleSheet("font-size: 12px; color: #C9CBD0;")
        row.addWidget(title_lbl, 1)

        size_lbl = QLabel(entry.size_str)
        size_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        size_lbl.setStyleSheet("font-size: 11px; color: #6B7280; min-width: 48px;")
        row.addWidget(size_lbl)

        play_btn = QPushButton("\u25b6\u2009Assistir")
        play_btn.setObjectName("PrimaryButton")
        play_btn.setFixedHeight(24)
        play_btn.setStyleSheet("QPushButton#PrimaryButton { font-size: 11px; padding: 0 10px; }")
        play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        play_btn.clicked.connect(lambda checked=False, e=entry: self.play_clicked.emit(e))
        row.addWidget(play_btn)

        del_btn = QPushButton()
        del_btn.setIcon(QIcon(icon_trash(13, "#4B5563")))
        del_btn.setFixedSize(24, 24)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setToolTip("Remover")
        del_btn.setStyleSheet(
            "QPushButton { background: transparent;"
            " border: 1px solid rgba(255,255,255,0.06); border-radius: 4px; }"
            "QPushButton:hover { border-color: rgba(229,115,115,0.35);"
            " background: rgba(229,115,115,0.10); }"
        )
        del_btn.clicked.connect(lambda checked=False, e=entry: self.delete_clicked.emit(e))
        row.addWidget(del_btn)


class _AnimeGroupCard(QFrame):
    play_clicked   = Signal(object)
    delete_clicked = Signal(object)

    def __init__(
        self,
        anime: str,
        entries: list,
        cover_path: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GlassPanel")
        self._anime = anime
        self._extra_rows: list[_DownloadRow] = []
        self._expanded = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 10)
        outer.setSpacing(14)

        # ── Cover (anchored top, no stretch) ─────────────────────
        self._cover_lbl = QLabel()
        self._cover_lbl.setFixedSize(_COVER_W, _COVER_H)
        self._cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if cover_path:
            self._apply_cover(cover_path)
        else:
            self._cover_lbl.setPixmap(generate_dynamic_cover(anime, _COVER_W, _COVER_H, radius=6))
        outer.addWidget(self._cover_lbl, 0, Qt.AlignmentFlag.AlignTop)

        # ── Content (fills remaining width, no stretch at bottom) ─
        content = QVBoxLayout()
        content.setContentsMargins(0, 1, 0, 0)
        content.setSpacing(0)

        title_lbl = QLabel(anime)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #F2F3F5;")
        title_lbl.setWordWrap(True)
        content.addWidget(title_lbl)
        content.addSpacing(2)

        ep_count = len(entries)
        total_mb = sum(e.file_size for e in entries) / (1024 * 1024)
        size_str = f"{total_mb / 1024:.1f} GB" if total_mb >= 1024 else f"{total_mb:.0f} MB"
        meta_lbl = QLabel(
            f"{ep_count}\u00a0epis\u00f3dio{'s' if ep_count > 1 else ''}  \u00b7  {size_str}"
        )
        meta_lbl.setStyleSheet("font-size: 11px; color: #6B7280;")
        content.addWidget(meta_lbl)
        content.addSpacing(8)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(255,255,255,0.06);")
        content.addWidget(div)
        content.addSpacing(1)

        sorted_entries = sorted(entries, key=lambda e: e.episode_num)
        for i, entry in enumerate(sorted_entries):
            r = _DownloadRow(entry)
            r.play_clicked.connect(self.play_clicked.emit)
            r.delete_clicked.connect(self.delete_clicked.emit)
            content.addWidget(r)
            if i >= _MAX_VISIBLE_EPS:
                r.setVisible(False)
                self._extra_rows.append(r)

        if self._extra_rows:
            n = len(self._extra_rows)
            self._expand_btn = QPushButton(f"\u25be  {n} epis\u00f3dio{'s' if n > 1 else ''} a mais")
            self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._expand_btn.setStyleSheet(
                "QPushButton { color: #6B7280; background: transparent; border: none;"
                " font-size: 11px; text-align: left; padding: 4px 4px 0 4px; }"
                "QPushButton:hover { color: #A7ACB5; }"
            )
            self._expand_btn.clicked.connect(self._toggle_expand)
            content.addWidget(self._expand_btn)

        outer.addLayout(content, 1)

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        for r in self._extra_rows:
            r.setVisible(self._expanded)
        n = len(self._extra_rows)
        if self._expanded:
            self._expand_btn.setText("\u25b4  Recolher")
        else:
            self._expand_btn.setText(f"\u25be  {n} epis\u00f3dio{'s' if n > 1 else ''} a mais")

    def set_cover(self, path: str) -> None:
        self._apply_cover(path)

    def _apply_cover(self, path: str) -> None:
        pm = QPixmap(path)
        if pm.isNull():
            return
        w, h = _COVER_W, _COVER_H
        scaled = pm.scaled(
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
        clip.addRoundedRect(0, 0, w, h, 6, 6)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self._cover_lbl.setPixmap(rounded)
        self._cover_lbl.setStyleSheet("")


# ── Manga download rows ──────────────────────────────────────────────


class _MangaChapterRow(QFrame):
    delete_clicked = Signal(object)
    open_clicked   = Signal(object)

    def __init__(self, entry: MangaDownloadEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self.setObjectName("DownloadRow")
        self.setStyleSheet(
            "QFrame#DownloadRow { background: transparent; border-radius: 4px; }"
            "QFrame#DownloadRow:hover { background: rgba(255,255,255,0.04); }"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(10)

        ch_lbl = QLabel(entry.chapter_label)
        ch_lbl.setStyleSheet("font-size: 12px; color: #C9CBD0;")
        row.addWidget(ch_lbl, 1)

        if entry.page_count:
            pg_lbl = QLabel(f"{entry.page_count}p")
            pg_lbl.setStyleSheet("font-size: 11px; color: #6B7280;")
            row.addWidget(pg_lbl)

        size_lbl = QLabel(entry.size_str)
        size_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        size_lbl.setStyleSheet("font-size: 11px; color: #6B7280; min-width: 52px;")
        row.addWidget(size_lbl)

        cbz_badge = QLabel("CBZ")
        cbz_badge.setStyleSheet(
            "background: rgba(100,160,255,0.12); color: #7EB3FF;"
            " border: 1px solid rgba(100,160,255,0.25); border-radius: 3px;"
            " padding: 1px 5px; font-size: 9px; font-weight: 700;"
        )
        row.addWidget(cbz_badge)

        read_btn = QPushButton("Ler")
        read_btn.setFixedHeight(26)
        read_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        read_btn.setStyleSheet(
            "QPushButton { color: #7EB3FF; background: rgba(100,160,255,0.10);"
            " border: 1px solid rgba(100,160,255,0.25); border-radius: 4px;"
            " font-size: 11px; padding: 0 10px; }"
            "QPushButton:hover { background: rgba(100,160,255,0.22); border-color: rgba(100,160,255,0.5); }"
        )
        read_btn.clicked.connect(lambda checked=False, e=entry: self.open_clicked.emit(e))
        row.addWidget(read_btn)

        del_btn = QPushButton("Remover")
        del_btn.setFixedHeight(26)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            "QPushButton { color: #B06060; background: rgba(180,60,60,0.08);"
            " border: 1px solid rgba(180,60,60,0.22); border-radius: 4px;"
            " font-size: 11px; padding: 0 10px; }"
            "QPushButton:hover { color: #E57373; border-color: rgba(229,115,115,0.5);"
            " background: rgba(229,115,115,0.15); }"
        )
        del_btn.clicked.connect(lambda checked=False, e=entry: self.delete_clicked.emit(e))
        row.addWidget(del_btn)


class _MangaGroupCard(QFrame):
    delete_clicked = Signal(object)
    open_clicked   = Signal(object)

    def __init__(
        self,
        manga_title: str,
        entries: list,
        cover_path: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GlassPanel")
        self._manga_title = manga_title
        self._extra_rows: list[_MangaChapterRow] = []
        self._expanded = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 10)
        outer.setSpacing(14)

        self._cover_lbl = QLabel()
        self._cover_lbl.setFixedSize(_COVER_W, _COVER_H)
        self._cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if cover_path:
            self._apply_cover(cover_path)
        else:
            self._cover_lbl.setPixmap(generate_dynamic_cover(manga_title, _COVER_W, _COVER_H, radius=6))
        outer.addWidget(self._cover_lbl, 0, Qt.AlignmentFlag.AlignTop)

        content = QVBoxLayout()
        content.setContentsMargins(0, 1, 0, 0)
        content.setSpacing(0)

        title_lbl = QLabel(manga_title)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #F2F3F5;")
        title_lbl.setWordWrap(True)
        content.addWidget(title_lbl)
        content.addSpacing(2)

        ch_count = len(entries)
        total_mb = sum(e.file_size for e in entries) / (1024 * 1024)
        size_str = f"{total_mb / 1024:.1f} GB" if total_mb >= 1024 else f"{total_mb:.0f} MB"
        meta_lbl = QLabel(
            f"{ch_count}\u00a0cap\u00edtulo{'s' if ch_count > 1 else ''}  \u00b7  {size_str}"
        )
        meta_lbl.setStyleSheet("font-size: 11px; color: #6B7280;")
        content.addWidget(meta_lbl)
        content.addSpacing(8)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(255,255,255,0.06);")
        content.addWidget(div)
        content.addSpacing(1)

        for i, entry in enumerate(entries):
            r = _MangaChapterRow(entry)
            r.delete_clicked.connect(self.delete_clicked.emit)
            r.open_clicked.connect(self.open_clicked.emit)
            content.addWidget(r)
            if i >= _MAX_VISIBLE_EPS:
                r.setVisible(False)
                self._extra_rows.append(r)

        if self._extra_rows:
            n = len(self._extra_rows)
            self._expand_btn = QPushButton(f"\u25be  {n} cap\u00edtulo{'s' if n > 1 else ''} a mais")
            self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._expand_btn.setStyleSheet(
                "QPushButton { color: #6B7280; background: transparent; border: none;"
                " font-size: 11px; text-align: left; padding: 4px 4px 0 4px; }"
                "QPushButton:hover { color: #A7ACB5; }"
            )
            self._expand_btn.clicked.connect(self._toggle_expand)
            content.addWidget(self._expand_btn)

        outer.addLayout(content, 1)

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        for r in self._extra_rows:
            r.setVisible(self._expanded)
        n = len(self._extra_rows)
        if self._expanded:
            self._expand_btn.setText("\u25b4  Recolher")
        else:
            self._expand_btn.setText(f"\u25be  {n} cap\u00edtulo{'s' if n > 1 else ''} a mais")

    def set_cover(self, path: str) -> None:
        self._apply_cover(path)

    def _apply_cover(self, path: str) -> None:
        pm = QPixmap(path)
        if pm.isNull():
            return
        w, h = _COVER_W, _COVER_H
        scaled = pm.scaled(
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
        clip.addRoundedRect(0, 0, w, h, 6, 6)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self._cover_lbl.setPixmap(rounded)
        self._cover_lbl.setStyleSheet("")


# ── Tab button helper ──────────────────────────────────────────────────

_TAB_ACTIVE = (
    "QPushButton { color: #F2F3F5; background: rgba(255,255,255,0.08);"
    " border: none; border-bottom: 2px solid #D44242; border-radius: 0;"
    " font-size: 13px; font-weight: 600; padding: 0 20px; }"
)
_TAB_IDLE = (
    "QPushButton { color: #6B7280; background: transparent;"
    " border: none; border-bottom: 2px solid transparent; border-radius: 0;"
    " font-size: 13px; padding: 0 20px; }"
    "QPushButton:hover { color: #A7ACB5; }"
)


def _make_scroll_panel() -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    body = QWidget()
    body.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(body)
    layout.setContentsMargins(28, 12, 28, 28)
    layout.setSpacing(10)
    scroll.setWidget(body)
    return scroll, body, layout


class DownloadsView(QWidget):
    """Offline library — Anime and Manga tabs."""

    play_clicked         = Signal(object)
    delete_clicked       = Signal(object)
    open_folder_clicked  = Signal()
    manga_delete_clicked = Signal(object)
    manga_open_clicked   = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Fixed header ──────────────────────────────────────────
        header_widget = QWidget()
        header_widget.setStyleSheet("background: transparent;")
        hv = QVBoxLayout(header_widget)
        hv.setContentsMargins(28, 20, 28, 0)
        hv.setSpacing(0)

        title_row = QHBoxLayout()
        title_lbl = QLabel("Downloads")
        title_lbl.setObjectName("SectionTitleLarge")
        title_row.addWidget(title_lbl)
        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet("font-size: 12px; color: #6B7280; padding-top: 5px;")
        title_row.addWidget(self._stats_lbl)
        title_row.addStretch()
        self._open_btn = QPushButton("  Abrir Pasta")
        self._open_btn.setIcon(QIcon(icon_folder(13, "#A7ACB5")))
        self._open_btn.setFixedHeight(30)
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.setStyleSheet(
            "QPushButton { color: #A7ACB5; background: rgba(255,255,255,0.05);"
            " border: 1px solid rgba(255,255,255,0.09); border-radius: 6px;"
            " font-size: 12px; padding: 0 12px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.09); color: #F2F3F5; }"
        )
        self._open_btn.clicked.connect(self.open_folder_clicked.emit)
        title_row.addWidget(self._open_btn)
        hv.addLayout(title_row)
        hv.addSpacing(14)

        # Tab bar
        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(0)
        self._tab_anime = QPushButton("Anime")
        self._tab_anime.setFixedHeight(36)
        self._tab_anime.setCursor(Qt.CursorShape.PointingHandCursor)

        # Manga tab wrapper with "Em Breve" badge
        manga_tab_wrapper = QWidget()
        manga_tab_wrapper.setStyleSheet("background: transparent;")
        manga_tab_h = QHBoxLayout(manga_tab_wrapper)
        manga_tab_h.setContentsMargins(0, 0, 0, 0)
        manga_tab_h.setSpacing(4)
        self._tab_manga = QPushButton("Manga")
        self._tab_manga.setFixedHeight(36)
        self._tab_manga.setCursor(Qt.CursorShape.ForbiddenCursor)
        self._tab_manga.setEnabled(False)
        manga_soon_badge = QLabel("Em Breve")
        manga_soon_badge.setStyleSheet(
            "background: rgba(212,66,66,0.15); color: #D44242;"
            " border: 1px solid rgba(212,66,66,0.35); border-radius: 8px;"
            " font-size: 9px; font-weight: 700; padding: 1px 6px;"
        )
        manga_soon_badge.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        manga_soon_badge.setFixedHeight(16)
        manga_tab_h.addWidget(self._tab_manga)
        manga_tab_h.addWidget(manga_soon_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        tab_row.addWidget(self._tab_anime)
        tab_row.addWidget(manga_tab_wrapper)
        tab_row.addStretch()
        hv.addLayout(tab_row)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(255,255,255,0.06); margin: 0;")
        hv.addWidget(div)

        root.addWidget(header_widget)

        # ── Scrollable panels ────────────────────────────────────
        self._anime_scroll, _, self._anime_layout = _make_scroll_panel()
        self._manga_scroll, _, self._manga_layout = _make_scroll_panel()

        root.addWidget(self._anime_scroll, 1)
        root.addWidget(self._manga_scroll, 1)

        # ── Empty states ─────────────────────────────────────────
        self._anime_empty = self._make_empty("Nenhum download encontrado",
                                              "Baixe epis\u00f3dios na tela de detalhes\npara assistir offline")
        self._manga_empty = self._make_empty("Nenhum mangá baixado",
                                              "Baixe capítulos na tela de detalhes do mangá\npara ler offline (.cbz)")
        self._anime_layout.addWidget(self._anime_empty)
        self._manga_layout.addWidget(self._manga_empty)

        self._anime_cards: dict[str, _AnimeGroupCard] = {}
        self._manga_cards: dict[str, _MangaGroupCard] = {}

        self._tab_anime.clicked.connect(lambda: self._switch_tab("anime"))
        # Manga tab is disabled (Em Breve) — no click connection
        self._switch_tab("anime")

    # ── Tab switching ─────────────────────────────────────────────

    def _switch_tab(self, tab: str) -> None:
        self._active_tab = tab
        anime_on = (tab == "anime")
        self._anime_scroll.setVisible(anime_on)
        self._manga_scroll.setVisible(not anime_on)
        self._tab_anime.setStyleSheet(_TAB_ACTIVE if anime_on else _TAB_IDLE)
        self._tab_manga.setStyleSheet(
            "QPushButton { color: #3A3F52; background: transparent;"
            " border: none; border-bottom: 2px solid transparent; border-radius: 0;"
            " font-size: 13px; padding: 0 20px; }"
        )
        self._stats_lbl.setText(self._anime_stats if anime_on else self._manga_stats)
        self._open_btn.setVisible(anime_on)

    # ── Anime tab ────────────────────────────────────────────────

    _anime_stats: str = ""
    _manga_stats: str = ""

    def set_downloads(self, groups: dict, cover_cache: dict | None = None) -> None:
        for card in self._anime_cards.values():
            card.setParent(None)
            card.deleteLater()
        self._anime_cards.clear()
        while self._anime_layout.count() > 0:
            item = self._anime_layout.takeAt(0)
            w = item.widget()
            if w and w is not self._anime_empty:
                w.setParent(None)
                w.deleteLater()

        if not groups:
            self._anime_stats = ""
            self._anime_layout.addWidget(self._anime_empty)
            self._anime_empty.show()
            if getattr(self, "_active_tab", "anime") == "anime":
                self._stats_lbl.setText("")
            return

        self._anime_empty.hide()
        total_eps = sum(len(eps) for eps in groups.values())
        total_mb = sum(e.file_size for eps in groups.values() for e in eps) / (1024 * 1024)
        size_disp = f"{total_mb / 1024:.1f} GB" if total_mb >= 1024 else f"{total_mb:.0f} MB"
        count = len(groups)
        self._anime_stats = (
            f"{count}\u00a0anime{'s' if count > 1 else ''}  \u00b7  "
            f"{total_eps}\u00a0ep{'s' if total_eps > 1 else ''}  \u00b7  {size_disp}"
        )
        if getattr(self, "_active_tab", "anime") == "anime":
            self._stats_lbl.setText(self._anime_stats)

        for anime, entries in sorted(groups.items(), key=lambda x: x[0].lower()):
            cover = (cover_cache or {}).get(anime)
            card = _AnimeGroupCard(anime, entries, cover)
            card.play_clicked.connect(self.play_clicked.emit)
            card.delete_clicked.connect(self.delete_clicked.emit)
            self._anime_cards[anime] = card
            self._anime_layout.addWidget(card)
        self._anime_layout.addStretch()

    def update_cover(self, anime: str, cover_path: str) -> None:
        if anime in self._anime_cards:
            self._anime_cards[anime].set_cover(cover_path)

    # ── Manga tab ────────────────────────────────────────────────

    def set_manga_downloads(self, groups: dict, cover_cache: dict | None = None) -> None:
        for card in self._manga_cards.values():
            card.setParent(None)
            card.deleteLater()
        self._manga_cards.clear()
        while self._manga_layout.count() > 0:
            item = self._manga_layout.takeAt(0)
            w = item.widget()
            if w and w is not self._manga_empty:
                w.setParent(None)
                w.deleteLater()

        if not groups:
            self._manga_stats = ""
            self._manga_layout.addWidget(self._manga_empty)
            self._manga_empty.show()
            if getattr(self, "_active_tab", "anime") == "manga":
                self._stats_lbl.setText("")
            return

        self._manga_empty.hide()
        total_ch = sum(len(chs) for chs in groups.values())
        total_mb = sum(e.file_size for chs in groups.values() for e in chs) / (1024 * 1024)
        size_disp = f"{total_mb / 1024:.1f} GB" if total_mb >= 1024 else f"{total_mb:.0f} MB"
        count = len(groups)
        self._manga_stats = (
            f"{count}\u00a0manga{'s' if count > 1 else ''}  \u00b7  "
            f"{total_ch}\u00a0cap\u00edtulo{'s' if total_ch > 1 else ''}  \u00b7  {size_disp}"
        )
        if getattr(self, "_active_tab", "anime") == "manga":
            self._stats_lbl.setText(self._manga_stats)

        for manga_title, entries in sorted(groups.items(), key=lambda x: x[0].lower()):
            cover = (cover_cache or {}).get(manga_title)
            card = _MangaGroupCard(manga_title, entries, cover)
            card.delete_clicked.connect(self.manga_delete_clicked.emit)
            card.open_clicked.connect(self.manga_open_clicked.emit)
            self._manga_cards[manga_title] = card
            self._manga_layout.addWidget(card)
        self._manga_layout.addStretch()

    def update_manga_cover(self, manga_title: str, path: str) -> None:
        if manga_title in self._manga_cards:
            self._manga_cards[manga_title].set_cover(path)

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _make_empty(title: str, subtitle: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 60, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        lay.setSpacing(10)
        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setPixmap(icon_folder(48, "#2E3040"))
        lay.addWidget(icon_lbl)
        et = QLabel(title)
        et.setAlignment(Qt.AlignmentFlag.AlignCenter)
        et.setStyleSheet("font-size: 15px; font-weight: 600; color: #3E4255;")
        lay.addWidget(et)
        es = QLabel(subtitle)
        es.setAlignment(Qt.AlignmentFlag.AlignCenter)
        es.setStyleSheet("font-size: 12px; color: #2E3040; line-height: 1.6;")
        lay.addWidget(es)
        return w
