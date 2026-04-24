"""Manga reader views: home/search, detail, and vertical-scroll chapter reader."""
from __future__ import annotations

import re
from typing import Optional

from PySide6.QtCore import Qt, QSize, QTimer, QThreadPool, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .icons import icon_arrow_left, icon_download, icon_search
from .views import AnimatedButton
from .workers import FunctionWorker


# ═══════════════════════════════════════════════════════════════════
#  MANGA HOME / SEARCH VIEW
# ═══════════════════════════════════════════════════════════════════

class MangaCard(QFrame):
    clicked = Signal(dict)

    _STATUS_MAP = {
        "ongoing": "Em lançamento",
        "completed": "Completo",
        "hiatus": "Em hiato",
        "cancelled": "Cancelado",
    }

    def __init__(self, manga: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manga = manga
        self._available = manga.get("has_ptbr", True)
        self.setObjectName("GlassPanel")
        self.setFixedHeight(82)

        if self._available:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setGraphicsEffect(self._make_dim_effect())

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(12)

        self._cover = QLabel()
        self._cover.setFixedSize(46, 64)
        self._cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover.setStyleSheet("background: rgba(255,255,255,0.08); border-radius: 4px;")
        row.addWidget(self._cover)

        info = QVBoxLayout()
        info.setSpacing(3)

        t = QLabel(manga.get("title", ""))
        t.setObjectName("CardTitle")
        t.setWordWrap(True)
        info.addWidget(t)

        sub_row = QHBoxLayout()
        sub_row.setSpacing(8)

        status = manga.get("status", "")
        if status:
            s = QLabel(self._STATUS_MAP.get(status, status.capitalize()))
            s.setObjectName("MutedText")
            sub_row.addWidget(s)

        if not self._available:
            badge = QLabel("Sem PT-BR")
            badge.setStyleSheet(
                "background: rgba(180,60,60,0.25); color: #c87070;"
                "border: 1px solid rgba(180,60,60,0.4); border-radius: 4px;"
                "padding: 1px 6px; font-size: 11px; font-weight: 600;"
            )
            sub_row.addWidget(badge)

        sub_row.addStretch()
        info.addLayout(sub_row)
        info.addStretch()
        row.addLayout(info, 1)

    @staticmethod
    def _make_dim_effect():
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        eff = QGraphicsOpacityEffect()
        eff.setOpacity(0.38)
        return eff

    def set_cover(self, path: str) -> None:
        pm = QPixmap(path)
        if not pm.isNull():
            self._cover.setPixmap(
                pm.scaled(46, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )

    def set_unavailable(self) -> None:
        """Mark this card as unavailable (no hosted chapters). Call from main thread only."""
        if not self._available:
            return
        self._available = False
        self.setCursor(Qt.CursorShape.ForbiddenCursor)
        self.setGraphicsEffect(self._make_dim_effect())
        # Add "Sem capítulos" badge next to any existing sub-row labels
        badge = QLabel("Sem capítulos")
        badge.setStyleSheet(
            "background: rgba(180,60,60,0.25); color: #c87070;"
            "border: 1px solid rgba(180,60,60,0.4); border-radius: 4px;"
            "padding: 1px 6px; font-size: 11px; font-weight: 600;"
        )
        # Find the sub_row (second layout item inside info VBoxLayout)
        info_layout = self.layout().itemAt(1).layout()
        if info_layout and info_layout.count() > 1:
            sub_row_item = info_layout.itemAt(1)
            if sub_row_item and sub_row_item.layout():
                sub_row_item.layout().insertWidget(0, badge)

    def mousePressEvent(self, event) -> None:
        if self._available:
            self.clicked.emit(self._manga)
        super().mousePressEvent(event)


class MangaHomeView(QWidget):
    search_requested = Signal(str)
    manga_clicked = Signal(dict)
    history_clicked = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        title = QLabel("Manga")
        title.setObjectName("SectionTitleLarge")
        outer.addWidget(title)

        sub = QLabel("Leia mangás com tradução em português via MangaDex")
        sub.setObjectName("MutedText")
        outer.addWidget(sub)

        # Search row
        row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Pesquisar mangá...")
        self._input.setMinimumWidth(300)
        row.addWidget(self._input, 1)

        self._btn = AnimatedButton()
        self._btn.setObjectName("PrimaryButton")
        self._btn.setIcon(QIcon(icon_search(16, "#F2F3F5")))
        self._btn.setIconSize(QSize(16, 16))
        self._btn.setText(" Buscar")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self._btn)
        outer.addLayout(row)

        self._input.returnPressed.connect(self._on_search)
        self._btn.clicked.connect(self._on_search)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self._cv = QVBoxLayout(content)
        self._cv.setContentsMargins(0, 0, 0, 0)
        self._cv.setSpacing(6)

        # History section
        self._hist_title = QLabel("Continuar Lendo")
        self._hist_title.setObjectName("SectionTitle")
        self._hist_title.hide()
        self._cv.addWidget(self._hist_title)

        self._hist_area = QWidget()
        self._hist_v = QVBoxLayout(self._hist_area)
        self._hist_v.setContentsMargins(0, 0, 0, 0)
        self._hist_v.setSpacing(6)
        self._cv.addWidget(self._hist_area)

        # Results section
        self._res_title = QLabel("")
        self._res_title.setObjectName("SectionTitle")
        self._res_title.hide()
        self._cv.addWidget(self._res_title)

        self._res_area = QWidget()
        self._res_v = QVBoxLayout(self._res_area)
        self._res_v.setContentsMargins(0, 0, 0, 0)
        self._res_v.setSpacing(6)
        self._cv.addWidget(self._res_area)

        self._empty = QLabel("Nenhum resultado encontrado.")
        self._empty.setObjectName("MutedText")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.hide()
        self._cv.addWidget(self._empty)

        self._cv.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self._cards: dict[str, MangaCard] = {}

    def _on_search(self) -> None:
        q = self._input.text().strip()
        if q:
            self.search_requested.emit(q)

    def show_searching(self, query: str) -> None:
        self._clear_results()
        self._res_title.setText(f'Buscando "{query}"...')
        self._res_title.show()
        self._empty.hide()

    def set_results(self, mangas: list[dict], query: str) -> None:
        self._clear_results()
        if not mangas:
            self._res_title.setText(f'Sem resultados para "{query}".')
            self._res_title.show()
            self._empty.show()
            return
        self._res_title.setText(f'{len(mangas)} resultado(s) para "{query}"')
        self._res_title.show()
        for m in mangas:
            card = MangaCard(m)
            card.clicked.connect(self.manga_clicked)
            self._res_v.addWidget(card)
            self._cards[m["id"]] = card

    def set_history(self, entries: list) -> None:
        self._clear_layout(self._hist_v)
        if not entries:
            self._hist_title.hide()
            return
        self._hist_title.show()
        for entry in entries:
            self._hist_v.addWidget(self._make_history_row(entry))

    def update_card_cover(self, manga_id: str, path: str) -> None:
        if manga_id in self._cards:
            self._cards[manga_id].set_cover(path)

    def mark_unavailable(self, manga_id: str) -> None:
        if manga_id in self._cards:
            self._cards[manga_id].set_unavailable()

    def _make_history_row(self, entry) -> QFrame:
        frame = QFrame()
        frame.setObjectName("GlassPanel")
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        frame.setFixedHeight(72)

        row = QHBoxLayout(frame)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(12)

        cover = QLabel()
        cover.setFixedSize(44, 58)
        cover.setStyleSheet("background: rgba(255,255,255,0.08); border-radius: 4px;")
        if entry.cover_path:
            pm = QPixmap(entry.cover_path)
            if not pm.isNull():
                cover.setPixmap(
                    pm.scaled(44, 58, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
        row.addWidget(cover)

        info = QVBoxLayout()
        info.setSpacing(2)
        t = QLabel(entry.manga_title)
        t.setObjectName("CardTitle")
        info.addWidget(t)
        s = QLabel(entry.chapter_label)
        s.setObjectName("MutedText")
        info.addWidget(s)
        info.addStretch()
        row.addLayout(info, 1)

        frame.mousePressEvent = lambda e, en=entry: self.history_clicked.emit(en)
        return frame

    def _clear_results(self) -> None:
        self._clear_layout(self._res_v)
        self._cards.clear()
        self._res_title.hide()
        self._empty.hide()

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


# ═══════════════════════════════════════════════════════════════════
#  MANGA DETAIL VIEW
# ═══════════════════════════════════════════════════════════════════

_DL_IDLE = "idle"
_DL_DOWNLOADING = "downloading"
_DL_DONE = "done"


class ChapterRow(QFrame):
    clicked = Signal()
    download_clicked = Signal()

    def __init__(self, chapter: dict, is_current: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EpisodeRow")
        if is_current:
            self.setProperty("highlighted", "true")

        self._dl_state = _DL_IDLE
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(12, 8, 12, 8)
        self._row.setSpacing(10)

        self._checkbox = QCheckBox()
        self._checkbox.setFixedSize(18, 18)
        self._checkbox.hide()
        self._row.addWidget(self._checkbox)

        label = QLabel(chapter.get("label", ""))
        label.setObjectName("CardTitle")
        self._row.addWidget(label, 1)

        pages = chapter.get("pages", 0)
        if pages:
            pl = QLabel(f"{pages}p")
            pl.setObjectName("MutedText")
            self._row.addWidget(pl)

        self._read_btn = AnimatedButton("Ler")
        self._read_btn.setObjectName("PrimaryButton")
        self._read_btn.setFixedSize(58, 28)
        self._read_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._read_btn.clicked.connect(self.clicked)
        self._row.addWidget(self._read_btn)

        self._dl_btn = QPushButton()
        self._dl_btn.setIcon(QIcon(icon_download(13, "#A7ACB5")))
        self._dl_btn.setIconSize(QSize(13, 13))
        self._dl_btn.setFixedSize(28, 28)
        self._dl_btn.setToolTip("Baixar capítulo")
        self._dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dl_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid rgba(255,255,255,0.08);"
            " border-radius: 5px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.06); border-color: rgba(255,255,255,0.18); }"
        )
        self._dl_btn.clicked.connect(self.download_clicked)
        self._row.addWidget(self._dl_btn)

        self._dl_lbl = QLabel()
        self._dl_lbl.setObjectName("MutedText")
        self._dl_lbl.setStyleSheet("font-size: 10px;")
        self._dl_lbl.hide()
        self._row.addWidget(self._dl_lbl)

    def set_download_state(self, state: str, done: int = 0, total: int = 0) -> None:
        self._dl_state = state
        if state == _DL_DONE:
            self._dl_btn.setIcon(QIcon())
            self._dl_btn.setText("OK")
            self._dl_btn.setStyleSheet(
                "QPushButton { background: rgba(80,200,120,0.12); border: 1px solid rgba(80,200,120,0.3);"
                " border-radius: 5px; color: #50C878; font-size: 12px; font-weight: 700; }"
            )
            self._dl_btn.setEnabled(False)
            self._dl_lbl.hide()
        elif state == _DL_DOWNLOADING:
            self._dl_btn.hide()
            self._dl_lbl.setText(f"{done}/{total}p")
            self._dl_lbl.show()
        else:
            self._dl_btn.show()
            self._dl_lbl.hide()

    def set_select_mode(self, on: bool) -> None:
        self._checkbox.setChecked(False)
        self._checkbox.setVisible(on)
        self._dl_btn.setVisible(not on)

    def is_checked(self) -> bool:
        return self._checkbox.isChecked()

    def highlight(self, on: bool) -> None:
        self.setProperty("highlighted", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class MangaDetailView(QWidget):
    back_clicked = Signal()
    chapter_clicked = Signal(int)
    download_chapter_clicked = Signal(int)
    download_all_clicked = Signal()
    download_selected_clicked = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._chapters: list[dict] = []
        self._rows: list[ChapterRow] = []
        self._current_idx = -1
        self._select_mode = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header bar
        hdr = QFrame()
        hdr.setObjectName("GlassPanel")
        hdr.setStyleSheet(
            "QFrame#GlassPanel { border-radius: 0; border-left: none; border-right: none; border-top: none; }"
        )
        hdr.setFixedHeight(52)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(8, 0, 16, 0)

        back = AnimatedButton()
        back.setIcon(QIcon(icon_arrow_left(20, "#A7ACB5")))
        back.setFixedSize(36, 36)
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(self.back_clicked)
        hl.addWidget(back)

        self._hdr_title = QLabel("")
        self._hdr_title.setObjectName("SectionTitle")
        hl.addWidget(self._hdr_title)
        hl.addStretch()
        outer.addWidget(hdr)

        # Body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 20, 24, 20)
        bl.setSpacing(16)

        # Metadata
        meta = QHBoxLayout()
        meta.setSpacing(20)

        self._cover_lbl = QLabel()
        self._cover_lbl.setFixedSize(120, 170)
        self._cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_lbl.setStyleSheet(
            "background: rgba(255,255,255,0.06); border-radius: 8px;"
            "border: 1px solid rgba(255,255,255,0.1);"
        )
        meta.addWidget(self._cover_lbl, 0, Qt.AlignmentFlag.AlignTop)

        minfo = QVBoxLayout()
        minfo.setSpacing(6)
        self._title_lbl = QLabel("")
        self._title_lbl.setObjectName("SectionTitleLarge")
        self._title_lbl.setWordWrap(True)
        minfo.addWidget(self._title_lbl)
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("MutedText")
        minfo.addWidget(self._status_lbl)
        self._desc_lbl = QLabel("")
        self._desc_lbl.setObjectName("BodyText")
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setMaximumHeight(110)
        minfo.addWidget(self._desc_lbl)
        minfo.addStretch()
        meta.addLayout(minfo, 1)
        bl.addLayout(meta)

        # Chapter list header
        ch_hdr_row = QHBoxLayout()
        ch_hdr = QLabel("Capítulos")
        ch_hdr.setObjectName("SectionTitle")
        ch_hdr_row.addWidget(ch_hdr)
        ch_hdr_row.addStretch()

        self._dl_all_btn = QPushButton("Baixar todos")
        self._dl_all_btn.setFixedHeight(26)
        self._dl_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dl_all_btn.setStyleSheet(
            "QPushButton { color: #A7ACB5; background: rgba(255,255,255,0.05);"
            " border: 1px solid rgba(255,255,255,0.09); border-radius: 5px;"
            " font-size: 11px; padding: 0 10px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.09); color: #F2F3F5; }"
        )
        self._dl_all_btn.clicked.connect(self.download_all_clicked)
        self._dl_all_btn.hide()
        ch_hdr_row.addWidget(self._dl_all_btn)

        self._select_btn = QPushButton("Selecionar")
        self._select_btn.setFixedHeight(26)
        self._select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._select_btn.setStyleSheet(
            "QPushButton { color: #A7ACB5; background: rgba(255,255,255,0.05);"
            " border: 1px solid rgba(255,255,255,0.09); border-radius: 5px;"
            " font-size: 11px; padding: 0 10px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.09); color: #F2F3F5; }"
        )
        self._select_btn.clicked.connect(self._toggle_select_mode)
        self._select_btn.hide()
        ch_hdr_row.addWidget(self._select_btn)

        bl.addLayout(ch_hdr_row)

        self._loading_lbl = QLabel("Carregando capítulos...")
        self._loading_lbl.setObjectName("MutedText")
        bl.addWidget(self._loading_lbl)

        self._ch_area = QWidget()
        self._ch_v = QVBoxLayout(self._ch_area)
        self._ch_v.setContentsMargins(0, 0, 0, 0)
        self._ch_v.setSpacing(4)
        bl.addWidget(self._ch_area)
        bl.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # Action bar for select mode (overlaid at bottom)
        self._action_bar = QFrame(self)
        self._action_bar.setObjectName("GlassPanel")
        self._action_bar.setFixedHeight(54)
        self._action_bar.hide()
        ab = QHBoxLayout(self._action_bar)
        ab.setContentsMargins(16, 0, 16, 0)
        ab.setSpacing(12)
        self._sel_count_lbl = QLabel("0 selecionados")
        self._sel_count_lbl.setObjectName("MutedText")
        ab.addWidget(self._sel_count_lbl)
        ab.addStretch()
        dl_sel_btn = QPushButton("Baixar selecionados")
        dl_sel_btn.setObjectName("PrimaryButton")
        dl_sel_btn.setFixedHeight(32)
        dl_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dl_sel_btn.clicked.connect(self._emit_download_selected)
        ab.addWidget(dl_sel_btn)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            "QPushButton { color: #A7ACB5; background: rgba(255,255,255,0.05);"
            " border: 1px solid rgba(255,255,255,0.09); border-radius: 5px; padding: 0 12px; }"
            "QPushButton:hover { color: #F2F3F5; }"
        )
        cancel_btn.clicked.connect(self._exit_select_mode)
        ab.addWidget(cancel_btn)

    _STATUS_MAP = {
        "ongoing": "Em lançamento",
        "completed": "Completo",
        "hiatus": "Em hiato",
        "cancelled": "Cancelado",
    }

    def set_manga(self, manga: dict) -> None:
        self._manga = manga
        self._hdr_title.setText(manga.get("title", ""))
        self._title_lbl.setText(manga.get("title", ""))
        status = manga.get("status", "")
        self._status_lbl.setText(self._STATUS_MAP.get(status, status.capitalize()))
        desc = re.sub(r"<[^>]+>", "", manga.get("description", ""))
        self._desc_lbl.setText(desc[:420] + "…" if len(desc) > 420 else desc)
        self._cover_lbl.clear()
        self._loading_lbl.setText("Carregando capítulos...")
        self._loading_lbl.show()
        self._dl_all_btn.hide()
        self._select_btn.hide()
        self._action_bar.hide()
        self._select_mode = False
        self._clear_chapters()

    def set_cover(self, path: str) -> None:
        pm = QPixmap(path)
        if not pm.isNull():
            self._cover_lbl.setPixmap(
                pm.scaled(120, 170, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )

    def set_chapters(self, chapters: list[dict]) -> None:
        self._chapters = chapters
        self._rows = []
        self._loading_lbl.hide()
        self._clear_chapters()
        if not chapters:
            self._loading_lbl.setText("Nenhum capítulo disponível no MangaDex para este mangá.")
            self._loading_lbl.show()
            self._dl_all_btn.hide()
            self._select_btn.hide()
            return
        self._dl_all_btn.show()
        self._select_btn.show()
        for i, ch in enumerate(chapters):
            row = ChapterRow(ch, is_current=(i == self._current_idx))
            row.clicked.connect(lambda checked=False, idx=i: self.chapter_clicked.emit(idx))
            row.download_clicked.connect(lambda checked=False, idx=i: self.download_chapter_clicked.emit(idx))
            row._checkbox.stateChanged.connect(self._update_select_count)
            self._ch_v.addWidget(row)
            self._rows.append(row)

    def mark_downloaded_chapters(self, downloaded_labels: set) -> None:
        """Mark rows whose chapter label is in the downloaded set as done."""
        for i, row in enumerate(self._rows):
            label = self._chapters[i].get("label", "") if i < len(self._chapters) else ""
            if label in downloaded_labels:
                row.set_download_state(_DL_DONE)

    def set_chapter_state(self, index: int, state: str, done: int = 0, total: int = 0) -> None:
        if 0 <= index < len(self._rows):
            self._rows[index].set_download_state(state, done, total)

    def highlight_chapter(self, index: int) -> None:
        for i, row in enumerate(self._rows):
            row.highlight(i == index)
        self._current_idx = index

    def _toggle_select_mode(self) -> None:
        self._select_mode = not self._select_mode
        for row in self._rows:
            row.set_select_mode(self._select_mode)
        if self._select_mode:
            self._select_btn.setText("Cancelar")
            self._action_bar.show()
            self._action_bar.raise_()
            self._reposition_action_bar()
        else:
            self._exit_select_mode()

    def _exit_select_mode(self) -> None:
        self._select_mode = False
        self._select_btn.setText("Selecionar")
        for row in self._rows:
            row.set_select_mode(False)
        self._action_bar.hide()

    def _update_select_count(self) -> None:
        n = sum(1 for r in self._rows if r.is_checked())
        self._sel_count_lbl.setText(f"{n} selecionado{'s' if n != 1 else ''}")

    def _emit_download_selected(self) -> None:
        indices = [i for i, r in enumerate(self._rows) if r.is_checked()]
        if indices:
            self.download_selected_clicked.emit(indices)
        self._exit_select_mode()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_action_bar()

    def _reposition_action_bar(self) -> None:
        if self._action_bar.isVisible():
            w = self.width()
            h = self._action_bar.height()
            self._action_bar.setGeometry(0, self.height() - h, w, h)

    def _clear_chapters(self) -> None:
        while self._ch_v.count():
            item = self._ch_v.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows = []


# ═══════════════════════════════════════════════════════════════════
#  MANGA READER VIEW
# ═══════════════════════════════════════════════════════════════════

_PARALLEL = 4


class PageWidget(QFrame):
    """Single manga page; shows a placeholder until the image loads."""

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index
        self._original_pm: Optional[QPixmap] = None

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 1, 0, 1)
        v.setSpacing(0)

        self._placeholder = QLabel(f"Carregando pág. {index + 1}…")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setFixedHeight(260)
        self._placeholder.setObjectName("MutedText")
        v.addWidget(self._placeholder)

        self._img = QLabel()
        self._img.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._img.hide()
        v.addWidget(self._img)

    def set_image(self, data: bytes, view_width: int) -> None:
        pm = QPixmap()
        if not data or not pm.loadFromData(data) or pm.isNull():
            self._placeholder.setText(f"Erro — pág. {self._index + 1}")
            return
        self._original_pm = pm
        self._apply_width(view_width)
        self._placeholder.hide()
        self._img.show()

    def resize_to_width(self, width: int) -> None:
        self._apply_width(width)

    def _apply_width(self, width: int) -> None:
        if self._original_pm is None or width <= 0:
            return
        w = min(width, self._original_pm.width())
        scaled = self._original_pm.scaledToWidth(w, Qt.TransformationMode.SmoothTransformation)
        self._img.setPixmap(scaled)
        self._img.setFixedHeight(scaled.height())
        self.setFixedHeight(scaled.height() + 2)


class MangaReaderView(QWidget):
    back_clicked = Signal()
    chapter_requested = Signal(int)
    progress_changed = Signal(str, int)  # chapter_id, page_index
    download_chapter_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manga_service = None
        self._thread_pool = QThreadPool.globalInstance()
        self._page_urls: list[str] = []
        self._page_widgets: list[PageWidget] = []
        self._next_load = 0
        self._active_loads = 0
        self._chapter_id = ""
        self._chapter_index = 0
        self._chapter_count = 0
        self._manga_id = ""
        self._manga_title = ""
        self._current_cover_path: Optional[str] = None
        # Keep strong references to workers to prevent GC before signals fire
        self._active_workers: set[FunctionWorker] = set()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────
        bar = QFrame()
        bar.setObjectName("GlassPanel")
        bar.setStyleSheet(
            "QFrame#GlassPanel { border-radius: 0; border-left: none; border-right: none; border-top: none; }"
        )
        bar.setFixedHeight(50)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 0, 12, 0)
        bl.setSpacing(6)

        back_btn = AnimatedButton()
        back_btn.setIcon(QIcon(icon_arrow_left(20, "#A7ACB5")))
        back_btn.setFixedSize(36, 36)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.back_clicked)
        bl.addWidget(back_btn)

        self._ch_lbl = QLabel("")
        self._ch_lbl.setObjectName("CardTitle")
        bl.addWidget(self._ch_lbl)
        bl.addStretch()

        self._pg_lbl = QLabel("")
        self._pg_lbl.setObjectName("MutedText")
        bl.addWidget(self._pg_lbl)

        self._prev_btn = QPushButton("◀ Anterior")
        self._prev_btn.setFixedHeight(30)
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_btn.clicked.connect(lambda: self._go_chapter(-1))
        bl.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Próximo ▶")
        self._next_btn.setObjectName("PrimaryButton")
        self._next_btn.setFixedHeight(30)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.clicked.connect(lambda: self._go_chapter(1))
        bl.addWidget(self._next_btn)

        self._reader_dl_btn = QPushButton()
        self._reader_dl_btn.setIcon(QIcon(icon_download(13, "#A7ACB5")))
        self._reader_dl_btn.setIconSize(QSize(13, 13))
        self._reader_dl_btn.setFixedSize(30, 30)
        self._reader_dl_btn.setToolTip("Baixar capítulo atual")
        self._reader_dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reader_dl_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid rgba(255,255,255,0.1);"
            " border-radius: 5px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.07); }"
        )
        self._reader_dl_btn.clicked.connect(self.download_chapter_clicked)
        bl.addWidget(self._reader_dl_btn)

        outer.addWidget(bar)

        # ── Scroll area ──────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container.setStyleSheet("background: #111113;")
        self._pl = QVBoxLayout(self._container)
        self._pl.setContentsMargins(0, 0, 0, 0)
        self._pl.setSpacing(0)

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll, 1)

        # Debounced progress save on scroll
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self._emit_progress)
        self._scroll.verticalScrollBar().valueChanged.connect(lambda: self._save_timer.start())

        # Debounced reflow on resize
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)
        self._resize_timer.timeout.connect(self._reflow)

    def set_reader_download_state(self, state: str, done: int = 0, total: int = 0) -> None:
        if state == _DL_DONE:
            self._reader_dl_btn.setIcon(QIcon())
            self._reader_dl_btn.setText("OK")
            self._reader_dl_btn.setStyleSheet(
                "QPushButton { background: rgba(80,200,120,0.12); border: 1px solid rgba(80,200,120,0.3);"
                " border-radius: 5px; color: #50C878; font-size: 12px; font-weight: 700; }"
            )
            self._reader_dl_btn.setEnabled(False)
        elif state == _DL_DOWNLOADING:
            self._reader_dl_btn.setEnabled(False)
            self._reader_dl_btn.setIcon(QIcon())
            self._reader_dl_btn.setText(f"{done}/{total}")
            self._reader_dl_btn.setStyleSheet(
                "QPushButton { background: transparent; border: 1px solid rgba(255,255,255,0.1);"
                " border-radius: 5px; color: #A7ACB5; font-size: 9px; }"
            )
        else:
            self._reader_dl_btn.setEnabled(True)
            self._reader_dl_btn.setText("")
            self._reader_dl_btn.setIcon(QIcon(icon_download(13, "#A7ACB5")))
            self._reader_dl_btn.setStyleSheet(
                "QPushButton { background: transparent; border: 1px solid rgba(255,255,255,0.1);"
                " border-radius: 5px; }"
                "QPushButton:hover { background: rgba(255,255,255,0.07); }"
            )

    # ── Public API ───────────────────────────────────────────────

    def load_local_chapter(
        self,
        pages: list[bytes],
        chapter_label: str,
        manga_title: str,
    ) -> None:
        """Load a chapter from local CBZ bytes — no network required."""
        self._manga_service = None
        self._manga_id = ""
        self._manga_title = manga_title
        self._chapter_id = chapter_label
        self._chapter_index = 0
        self._chapter_count = 1

        self._ch_lbl.setText(chapter_label)
        self._pg_lbl.setText("Carregando…")

        # Hide online-only controls
        self._prev_btn.setVisible(False)
        self._next_btn.setVisible(False)
        self._reader_dl_btn.setVisible(False)

        self._page_urls = []
        self._page_widgets = []
        self._next_load = 0
        self._active_loads = 0
        self._active_workers.clear()
        self._scroll.verticalScrollBar().setValue(0)
        self._clear_pages()

        if not pages:
            self._pg_lbl.setText("Nenhuma página encontrada.")
            return

        vw = self._vp_width()
        for i, data in enumerate(pages):
            pw = PageWidget(i)
            self._pl.addWidget(pw)
            self._page_widgets.append(pw)
            pw.set_image(data, vw)

        total = len(pages)
        self._pg_lbl.setText(f"{total} páginas")

    def load_chapter(
        self,
        manga_service,
        manga_id: str,
        manga_title: str,
        chapter: dict,
        chapter_index: int,
        chapter_count: int,
        resume_page: int = 0,
        cover_path: Optional[str] = None,
    ) -> None:
        self._manga_service = manga_service
        self._manga_id = manga_id
        self._manga_title = manga_title
        self._chapter_id = chapter["id"]
        self._chapter_index = chapter_index
        self._chapter_count = chapter_count
        self._current_cover_path = cover_path

        # Restore controls that load_local_chapter may have hidden
        self._prev_btn.setVisible(True)
        self._next_btn.setVisible(True)
        self._reader_dl_btn.setVisible(True)

        self._ch_lbl.setText(chapter.get("label", ""))
        self._pg_lbl.setText("Carregando…")
        self.set_reader_download_state(_DL_IDLE)
        self._reader_dl_btn.setEnabled(True)
        self._prev_btn.setEnabled(chapter_index > 0)
        self._next_btn.setEnabled(chapter_index < chapter_count - 1)

        self._page_urls = []
        self._page_widgets = []
        self._next_load = 0
        self._active_loads = 0
        self._active_workers.clear()
        self._scroll.verticalScrollBar().setValue(0)
        self._clear_pages()

        cid = chapter["id"]
        worker = FunctionWorker(manga_service.fetch_chapter_pages, cid)
        self._active_workers.add(worker)
        worker.signals.succeeded.connect(lambda urls: self._on_urls(urls, resume_page))
        worker.signals.failed.connect(lambda e: self._pg_lbl.setText(f"Erro: {e}"))
        worker.signals.finished.connect(lambda w=worker: self._active_workers.discard(w))
        self._thread_pool.start(worker)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_timer.start()

    # ── Internal ─────────────────────────────────────────────────

    def _on_urls(self, urls: list, resume_page: int) -> None:
        if not urls:
            self._pg_lbl.setText("Sem páginas disponíveis.")
            return
        self._page_urls = urls
        for i in range(len(urls)):
            pw = PageWidget(i)
            self._pl.addWidget(pw)
            self._page_widgets.append(pw)
        self._update_pg_label()
        self._start_pipeline()
        if resume_page > 0:
            QTimer.singleShot(300, lambda p=resume_page: self._scroll_to(p))

    def _start_pipeline(self) -> None:
        while self._next_load < len(self._page_urls) and self._active_loads < _PARALLEL:
            idx = self._next_load
            self._next_load += 1
            self._active_loads += 1
            self._load_page(idx)

    def _load_page(self, idx: int) -> None:
        url = self._page_urls[idx]
        ms = self._manga_service

        def _download(i=idx, u=url):
            return i, ms.download_page(u)

        worker = FunctionWorker(_download)
        self._active_workers.add(worker)
        worker.signals.succeeded.connect(self._on_page)
        worker.signals.finished.connect(self._on_page_done)
        worker.signals.finished.connect(lambda w=worker: self._active_workers.discard(w))
        self._thread_pool.start(worker)

    def _on_page(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        idx, data = payload
        if data and 0 <= idx < len(self._page_widgets):
            self._page_widgets[idx].set_image(data, self._vp_width())
        self._update_pg_label()

    def _on_page_done(self) -> None:
        self._active_loads = max(0, self._active_loads - 1)
        self._start_pipeline()

    def _update_pg_label(self) -> None:
        total = len(self._page_urls)
        loaded = sum(1 for pw in self._page_widgets if pw._original_pm is not None)
        if loaded == total and total > 0:
            self._pg_lbl.setText(f"{total} páginas")
        else:
            self._pg_lbl.setText(f"{loaded}/{total} carregadas")

    def _reflow(self) -> None:
        vw = self._vp_width()
        for pw in self._page_widgets:
            pw.resize_to_width(vw)

    def _vp_width(self) -> int:
        return max(200, self._scroll.viewport().width())

    def _scroll_to(self, page: int) -> None:
        if 0 <= page < len(self._page_widgets):
            self._scroll.ensureWidgetVisible(self._page_widgets[page], 0, 0)

    def _current_page(self) -> int:
        if not self._page_widgets:
            return 0
        sy = self._scroll.verticalScrollBar().value()
        for i, pw in enumerate(self._page_widgets):
            if pw.y() + pw.height() >= sy:
                return i
        return len(self._page_widgets) - 1

    def _emit_progress(self) -> None:
        if self._chapter_id:
            self.progress_changed.emit(self._chapter_id, self._current_page())

    def _go_chapter(self, delta: int) -> None:
        new_idx = self._chapter_index + delta
        if 0 <= new_idx < self._chapter_count:
            self.chapter_requested.emit(new_idx)

    def _clear_pages(self) -> None:
        while self._pl.count():
            item = self._pl.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
