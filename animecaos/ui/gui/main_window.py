from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from typing import Any, Callable

from PySide6.QtCore import Qt, QThreadPool, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from animecaos.services.anime_service import AnimeService
from animecaos.services.history_service import HistoryEntry, HistoryService
from animecaos.services.anilist_service import AniListService
from animecaos.services.updater_service import UpdaterService

from .animated_stack import AnimatedStackedWidget
from .download_overlay import DownloadOverlay
from .icons import icon_search, icon_terminal
from .mini_player import MiniPlayer
from .play_overlay import PlayOverlay
from .sidebar import SidebarNav
from .views import AnimeDetailView, HomeView, SearchView
from .workers import FunctionWorker, DownloadWorker, UpdaterCheckWorker


# ═══════════════════════════════════════════════════════════════════
#  UPDATE DIALOG
# ═══════════════════════════════════════════════════════════════════

class UpdateDialog(QDialog):
    def __init__(self, parent: QWidget, latest_version: str, release_notes: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Atualizacao Disponivel")
        self.setFixedSize(500, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setObjectName("UpdateDialog")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        try:
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.abspath(".")
        icon_path = os.path.join(base_path, "public", "icon.png")

        icon_label = QLabel()
        pixmap = QPixmap(icon_path).scaled(
            48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        icon_label.setPixmap(pixmap)
        header_layout.addWidget(icon_label)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title = QLabel("Nova versao disponivel!")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #F2F3F5;")
        version_badge = QLabel(f"v{latest_version}")
        version_badge.setStyleSheet("""
            background-color: rgba(212, 66, 66, 0.2); color: #D44242;
            border: 1px solid rgba(212, 66, 66, 0.4); border-radius: 4px;
            padding: 2px 8px; font-size: 11px; font-weight: 700;
        """)
        badge_container = QHBoxLayout()
        badge_container.addWidget(version_badge)
        badge_container.addStretch()
        title_layout.addWidget(title)
        title_layout.addLayout(badge_container)
        header_layout.addLayout(title_layout)
        layout.addLayout(header_layout)

        notes_title = QLabel("Notas da Versao:")
        notes_title.setObjectName("MutedText")
        notes_title.setStyleSheet("font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;")
        layout.addWidget(notes_title)

        self.notes_browser = QTextBrowser()
        self.notes_browser.setHtml(self._format_notes(release_notes))
        self.notes_browser.setOpenExternalLinks(True)
        self.notes_browser.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px; padding: 12px; color: #E6E7EA; line-height: 1.5;
        """)
        layout.addWidget(self.notes_browser, 1)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        self.btn_ignore = QPushButton("Lembrar depois")
        self.btn_ignore.setFixedHeight(38)
        self.btn_ignore.clicked.connect(self.reject)
        self.btn_update = QPushButton("Atualizar Agora")
        self.btn_update.setObjectName("PrimaryButton")
        self.btn_update.setFixedHeight(38)
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.clicked.connect(self.accept)
        actions_layout.addWidget(self.btn_ignore, 1)
        actions_layout.addWidget(self.btn_update, 2)
        layout.addLayout(actions_layout)

    def _format_notes(self, notes: str) -> str:
        html = notes
        html = re.sub(r'^### (.*)$', r'<h3 style="color: #F2F3F5; margin-top: 10px; margin-bottom: 5px;">\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*)$', r'<h2 style="color: #F2F3F5; margin-top: 12px; margin-bottom: 6px;">\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.*)$', r'<h1 style="color: #F2F3F5; margin-top: 14px; margin-bottom: 8px;">\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.*?)\*\*', r'<b style="color: #ffffff;">\1</b>', html)
        html = re.sub(r'^- (.*)$', r'<li style="margin-left: 10px; margin-bottom: 3px;">\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'<img .*?src="(.*?)".*?>', r'<br/><a href="\1" style="color: #D44242; text-decoration: none;">[Ver Screenshot]</a><br/>', html)
        html = html.replace('\n', '<br/>')
        return f'<div style="font-family: Segoe UI, sans-serif; font-size: 13px;">{html}</div>'


# ═══════════════════════════════════════════════════════════════════
#  LOG VIEW
# ═══════════════════════════════════════════════════════════════════

class LogView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Log de Eventos")
        title.setObjectName("SectionTitleLarge")
        layout.addWidget(title)

        subtitle = QLabel("Registro de atividades da aplicacao")
        subtitle.setObjectName("MutedText")
        layout.addWidget(subtitle)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(400)
        layout.addWidget(self.log_output, 1)

        url_row = QHBoxLayout()
        url_label = QLabel("Ultima URL:")
        url_label.setObjectName("MutedText")
        url_row.addWidget(url_label)
        self.url_output = QLineEdit()
        self.url_output.setReadOnly(True)
        url_row.addWidget(self.url_output, 1)
        layout.addLayout(url_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(10)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)


# ═══════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════

# View indices
_VIEW_HOME = 0
_VIEW_SEARCH = 1
_VIEW_DETAIL = 2
_VIEW_LOG = 3


class MainWindow(QMainWindow):
    update_progress_signal = Signal(int)
    update_status_signal = Signal(str)
    update_finished_signal = Signal()

    def __init__(
        self,
        anime_service: AnimeService,
        history_service: HistoryService,
        anilist_service: AniListService,
    ) -> None:
        super().__init__()
        self._anime_service = anime_service
        self._history_service = history_service
        self._anilist_service = anilist_service
        self._thread_pool = QThreadPool.globalInstance()
        self._active_workers: set[FunctionWorker] = set()
        self._metadata_workers: set[FunctionWorker] = set()
        self._busy = False
        self._current_anime: str | None = None
        self._episodes_anime: str | None = None
        self._current_episode_index = -1
        self._episode_titles: list[str] = []
        self._cover_cache: dict[str, str] = {}
        self._updater_service = UpdaterService()
        self._last_search_query: str = ""
        self._nav_history: list[int] = []
        self._nav_forward: list[int] = []

        self.setWindowTitle(f"AnimeCaos v{self._updater_service.current_version}")

        try:
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.abspath(".")
        icon_path = os.path.join(base_path, "public", "icon.png")
        self.setWindowIcon(QIcon(icon_path))

        self.resize(1320, 820)
        self.setMinimumSize(1024, 640)

        self._build_ui()
        self._bind_events()
        self._bind_shortcuts()
        self._reload_history()
        self._check_for_updates()

    # ── UI BUILDING ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("RootContainer")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = self._build_header()
        root_layout.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._sidebar = SidebarNav()
        body.addWidget(self._sidebar)

        self._stack = AnimatedStackedWidget()
        self._home_view = HomeView()
        self._search_view = SearchView()
        self._detail_view = AnimeDetailView()
        self._log_view = LogView()

        self._stack.addWidget(self._home_view)     # 0
        self._stack.addWidget(self._search_view)   # 1
        self._stack.addWidget(self._detail_view)   # 2
        self._stack.addWidget(self._log_view)      # 3

        body.addWidget(self._stack, 1)
        root_layout.addLayout(body, 1)

        self._mini_player = MiniPlayer()
        root_layout.addWidget(self._mini_player)

        status_bar = QWidget()
        status_bar.setFixedHeight(28)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(16, 0, 16, 0)
        self._status_label = QLabel("Pronto.")
        self._status_label.setObjectName("MutedText")
        status_layout.addWidget(self._status_label)
        root_layout.addWidget(status_bar)

        # Overlays (render on top of everything)
        self._play_overlay = PlayOverlay(root)
        self._download_overlay = DownloadOverlay(root)
        self._download_overlay.cancel_requested.connect(self._on_download_cancel)
        self._active_download_worker: DownloadWorker | None = None

        self.update_progress_signal.connect(self._log_view.progress_bar.setValue)
        self.update_status_signal.connect(self._status_label.setText)
        self.update_finished_signal.connect(self.close)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("GlassPanel")
        header.setStyleSheet(
            "QFrame#GlassPanel { border-radius: 0px; border-left: none; border-right: none; border-top: none; }"
        )
        header.setFixedHeight(60)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Branding
        branding = QHBoxLayout()
        branding.setSpacing(8)
        try:
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.abspath(".")
        icon_path = os.path.join(base_path, "public", "icon.png")

        from PySide6.QtGui import QPainter, QPainterPath

        logo = QLabel()
        raw = QPixmap(icon_path).scaled(
            28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        logo_px = QPixmap(raw.size())
        logo_px.fill(Qt.GlobalColor.transparent)
        painter = QPainter(logo_px)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, raw.width(), raw.height(), 6, 6)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, raw)
        painter.end()
        logo.setPixmap(logo_px)
        logo.setCursor(Qt.CursorShape.PointingHandCursor)
        logo.mousePressEvent = lambda e: self._navigate_home()
        branding.addWidget(logo)

        app_title = QLabel('anime<span style="color: #D44242;">caos</span>')
        app_title.setObjectName("AppTitle")
        app_title.setCursor(Qt.CursorShape.PointingHandCursor)
        app_title.mousePressEvent = lambda e: self._navigate_home()
        branding.addWidget(app_title)
        layout.addLayout(branding)

        # Breadcrumb
        self._breadcrumb = QLabel("")
        self._breadcrumb.setObjectName("Breadcrumb")
        layout.addWidget(self._breadcrumb)

        layout.addStretch()

        # Search with icon
        search_container = QHBoxLayout()
        search_container.setSpacing(0)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Pesquisar anime...  (Ctrl+F)")
        self._search_input.setMinimumWidth(300)
        self._search_input.setMaximumWidth(500)
        layout.addWidget(self._search_input)

        self._search_btn = QPushButton()
        self._search_btn.setObjectName("PrimaryButton")
        self._search_btn.setIcon(QIcon(icon_search(16, "#F2F3F5")))
        self._search_btn.setIconSize(QSize(16, 16))
        self._search_btn.setText(" Buscar")
        self._search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._search_btn)

        return header

    # ── EVENT BINDING ────────────────────────────────────────────

    def _bind_events(self) -> None:
        self._search_input.returnPressed.connect(self._on_search_clicked)
        self._search_btn.clicked.connect(self._on_search_clicked)

        self._sidebar.nav_changed.connect(self._on_nav_changed)

        # Home view
        self._home_view.history_clicked.connect(self._on_history_card_clicked)

        # Search view
        self._search_view.anime_clicked.connect(self._on_anime_card_clicked)

        # Detail view
        self._detail_view.back_clicked.connect(self._navigate_back)
        self._detail_view.play_clicked.connect(self._on_episode_play_clicked)
        self._detail_view.download_clicked.connect(self._on_episode_download_clicked)

        # Mini player
        self._mini_player.prev_clicked.connect(self._on_previous_clicked)
        self._mini_player.next_clicked.connect(self._on_next_clicked)
        self._mini_player.bar_clicked.connect(self._navigate_to_current_anime)

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+F"), self, self._focus_search)
        QShortcut(QKeySequence("Escape"), self, self._on_escape)
        QShortcut(QKeySequence("Alt+Left"), self, self._navigate_back)
        QShortcut(QKeySequence("Ctrl+Right"), self, self._on_next_clicked)
        QShortcut(QKeySequence("Ctrl+Left"), self, self._on_previous_clicked)

    # ── NAVIGATION ───────────────────────────────────────────────

    def _navigate_home(self) -> None:
        self._push_nav(_VIEW_HOME)
        self._stack.slide_to(_VIEW_HOME)
        self._sidebar.set_active("home")
        self._breadcrumb.setText("")
        self._prev_view = _VIEW_HOME

    def _navigate_to_search(self) -> None:
        self._push_nav(_VIEW_SEARCH)
        self._stack.slide_to(_VIEW_SEARCH)
        self._sidebar.set_active("search")
        self._breadcrumb.setText("  >  Busca")
        self._prev_view = _VIEW_HOME

    def _navigate_to_detail(self, anime_name: str) -> None:
        self._push_nav(_VIEW_DETAIL)
        self._prev_view = self._stack.currentIndex()
        self._detail_view.set_anime(anime_name)
        self._stack.slide_to(_VIEW_DETAIL)
        self._breadcrumb.setText(f"  >  {anime_name}")
        self._fetch_metadata(anime_name)
        self._auto_load_episodes(anime_name)

    def _navigate_to_current_anime(self) -> None:
        if self._current_anime:
            self._stack.slide_to(_VIEW_DETAIL)
            self._breadcrumb.setText(f"  >  {self._current_anime}")

    def _navigate_back(self) -> None:
        """Go back to previous view using navigation history."""
        if self._nav_history:
            current = self._stack.currentIndex()
            target = self._nav_history.pop()
            self._nav_forward.append(current)
            self._stack.slide_to(target)
            self._update_breadcrumb_for(target)
        else:
            current = self._stack.currentIndex()
            if current != _VIEW_HOME:
                self._nav_forward.append(current)
                self._stack.slide_to(_VIEW_HOME)
                self._update_breadcrumb_for(_VIEW_HOME)

    _prev_view: int = _VIEW_HOME

    def _push_nav(self, target: int) -> None:
        """Push current view to history before navigating."""
        current = self._stack.currentIndex()
        if current != target:
            self._nav_history.append(current)
            self._nav_forward.clear()

    def _navigate_forward(self) -> None:
        """Go forward in navigation history."""
        if not self._nav_forward:
            return
        target = self._nav_forward.pop()
        self._nav_history.append(self._stack.currentIndex())
        self._stack.slide_to(target)
        self._update_breadcrumb_for(target)

    def _update_breadcrumb_for(self, view_idx: int) -> None:
        if view_idx == _VIEW_HOME:
            self._sidebar.set_active("home")
            self._breadcrumb.setText("")
        elif view_idx == _VIEW_SEARCH:
            self._sidebar.set_active("search")
            self._breadcrumb.setText("  >  Busca")
        elif view_idx == _VIEW_DETAIL:
            name = self._detail_view.anime_name
            self._breadcrumb.setText(f"  >  {name}" if name else "")
        elif view_idx == _VIEW_LOG:
            self._breadcrumb.setText("  >  Log de Eventos")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.BackButton:
            self._navigate_back()
        elif event.button() == Qt.MouseButton.ForwardButton:
            self._navigate_forward()
        else:
            super().mousePressEvent(event)

    def _on_nav_changed(self, key: str) -> None:
        if key == "home":
            self._navigate_home()
        elif key == "search":
            self._navigate_to_search()
            self._focus_search()
        elif key == "log":
            self._stack.slide_to(_VIEW_LOG)
            self._breadcrumb.setText("  >  Log de Eventos")

    def _on_escape(self) -> None:
        current = self._stack.currentIndex()
        if current != _VIEW_HOME:
            self._navigate_back()

    def _focus_search(self) -> None:
        self._search_input.setFocus()
        self._search_input.selectAll()

    # ── SEARCH ───────────────────────────────────────────────────

    def _on_search_clicked(self) -> None:
        query = self._search_input.text().strip()
        if not query:
            self._set_status("Digite um termo para buscar.")
            return

        self._last_search_query = query

        # Navigate to search page immediately with loading state
        self._search_view.show_searching(query)
        self._navigate_to_search()

        self._append_log(f"Busca iniciada: \"{query}\"")
        self._set_status(f"Buscando '{query}'...")
        self._run_task(
            status_message=f"Buscando '{query}'...",
            task=lambda: self._anime_service.search_animes(query),
            on_success=self._on_search_finished,
        )

    def _on_search_finished(self, anime_titles: object) -> None:
        if not isinstance(anime_titles, list):
            self._set_status("Resposta invalida da busca.")
            self._search_view.set_results([], self._last_search_query)
            return

        titles = [str(t) for t in anime_titles]

        if not titles:
            self._set_status("Nenhum anime encontrado.")
            self._append_log(f"Busca por \"{self._last_search_query}\" sem resultados.")
            self._search_view.set_results([], self._last_search_query)
            return

        cards = [{"title": t, "cover_path": self._cover_cache.get(t)} for t in titles]
        self._search_view.set_results(cards, self._last_search_query)

        self._set_status(f"{len(titles)} animes encontrados.")
        self._append_log(f"Busca por \"{self._last_search_query}\" concluida — {len(titles)} resultado(s) encontrado(s).")

        for t in titles:
            if t not in self._cover_cache:
                self._fetch_card_metadata(t)

    # ── CARD CLICKS ──────────────────────────────────────────────

    def _on_anime_card_clicked(self, data: dict) -> None:
        anime = data.get("title", "")
        if anime:
            self._current_anime = anime
            self._navigate_to_detail(anime)

    def _on_history_card_clicked(self, data: dict) -> None:
        entry = data.get("entry")
        if isinstance(entry, HistoryEntry):
            self._current_anime = entry.anime
            # Navigate to detail WITHOUT auto-loading episodes
            # (resume_from_history loads them its own way)
            self._detail_view.set_anime(entry.anime)
            self._push_nav(_VIEW_DETAIL)
            self._prev_view = self._stack.currentIndex()
            self._stack.slide_to(_VIEW_DETAIL)
            self._breadcrumb.setText(f"  >  {entry.anime}")
            self._fetch_metadata(entry.anime)
            self._resume_from_history(entry)

    # ── EPISODES ─────────────────────────────────────────────────

    def _auto_load_episodes(self, anime: str) -> None:
        if anime == self._episodes_anime and self._episode_titles:
            self._detail_view.set_episodes(self._episode_titles, self._current_episode_index)
            return

        self._run_task(
            status_message=f"Carregando episodios de '{anime}'...",
            task=lambda: (anime, self._anime_service.fetch_episode_titles(anime)),
            on_success=self._on_episodes_finished,
        )

    def _on_episodes_finished(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            self._set_status("Falha ao receber episodios.")
            return
        anime, episode_titles = payload
        if not isinstance(anime, str) or not isinstance(episode_titles, list):
            self._set_status("Dados de episodios invalidos.")
            return

        self._episodes_anime = anime
        self._episode_titles = [str(t) for t in episode_titles]

        if self._detail_view.anime_name == anime:
            self._detail_view.set_episodes(self._episode_titles, self._current_episode_index)

        if not self._episode_titles:
            self._set_status("Nenhum episodio encontrado.")
            self._append_log(f"Nenhum episodio encontrado para \"{anime}\".")
            return

        self._set_status(f"{len(self._episode_titles)} episodios carregados.")
        self._append_log(f"Episodios de \"{anime}\" carregados — {len(self._episode_titles)} episodio(s).")

    def _on_episode_play_clicked(self, index: int) -> None:
        anime = self._current_anime or self._detail_view.anime_name
        if not anime:
            return
        self._current_episode_index = index

        self._append_log(f"Resolvendo player: \"{anime}\" Ep {index + 1}...")

        # Show overlay popup
        self._play_overlay.show_loading(anime, index)

        self._run_task(
            status_message=f"Reproduzindo '{anime}' episodio {index + 1}...",
            task=lambda: self._play_episode(anime, index),
            on_success=self._on_play_finished,
        )

    def _play_episode(self, anime: str, episode_index: int) -> dict[str, object]:
        player_url = self._anime_service.resolve_player_url(anime, episode_index)
        # Dismiss overlay from worker thread before blocking on player
        from PySide6.QtCore import QMetaObject, Qt as QtConst, Q_ARG
        QMetaObject.invokeMethod(
            self._play_overlay, "dismiss", QtConst.ConnectionType.QueuedConnection
        )
        playback_result = self._anime_service.play_url(player_url)
        return {
            "anime": anime,
            "episode_index": episode_index,
            "player_url": player_url,
            "episode_sources": self._anime_service.get_episode_sources(anime),
            "eof": playback_result.get("eof", False),
        }

    def _on_play_finished(self, payload: object) -> None:
        self._play_overlay.dismiss()

        if not isinstance(payload, dict):
            self._set_status("Resposta invalida apos reproducao.")
            return

        anime = payload.get("anime", "")
        episode_index = payload.get("episode_index", -1)
        player_url = payload.get("player_url", "")
        episode_sources = payload.get("episode_sources", [])

        if not isinstance(anime, str) or not isinstance(episode_index, int):
            return
        if not isinstance(player_url, str) or not anime or episode_index < 0:
            return
        if not isinstance(episode_sources, list):
            return

        self._current_anime = anime
        self._episodes_anime = anime
        self._current_episode_index = episode_index

        self._log_view.url_output.setText(player_url)

        cover = self._cover_cache.get(anime)
        ep_count = len(self._episode_titles) if self._episode_titles else episode_index + 1
        self._mini_player.show_playback(anime, episode_index, ep_count, cover)

        self._detail_view.highlight_episode(episode_index)
        self._detail_view.scroll_to_episode(episode_index)

        try:
            self._history_service.save_entry(anime, episode_index, episode_sources)
        except Exception as exc:
            self._append_log(f"Historico nao salvo: {exc}")
        else:
            self._reload_history(silent=True)

        self._set_status(f"Episodio {episode_index + 1} finalizado.")
        self._append_log(f"Reproducao finalizada: \"{anime}\" Ep {episode_index + 1}.")

        if payload.get("eof") and self._mini_player.is_autoplay():
            if episode_index + 1 < len(self._episode_titles):
                self._append_log(f"Auto-play: avancando para Ep {episode_index + 2}...")
                self._on_next_clicked()

    def _on_previous_clicked(self) -> None:
        if self._current_episode_index <= 0:
            self._set_status("Nao existe episodio anterior.")
            return
        self._on_episode_play_clicked(self._current_episode_index - 1)

    def _on_next_clicked(self) -> None:
        target = self._current_episode_index + 1
        if target < len(self._episode_titles):
            self._on_episode_play_clicked(target)

    # ── DOWNLOAD ─────────────────────────────────────────────────

    def _on_episode_download_clicked(self, index: int) -> None:
        anime = self._current_anime or self._detail_view.anime_name
        if not anime:
            return

        if self._busy:
            self._set_status("Aguarde a tarefa atual finalizar.")
            return

        # Show download overlay immediately
        self._download_overlay.show_resolving(anime, index)

        self._run_task(
            status_message=f"Resolvendo URL para baixar '{anime}' episodio {index + 1}...",
            task=lambda: (anime, index, self._anime_service.resolve_player_url(anime, index)),
            on_success=self._start_download_worker,
        )

    def _start_download_worker(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 3:
            self._set_status("Falha ao resolver url de download.")
            self._download_overlay.show_error("Falha ao resolver URL do episodio.")
            return
        anime, episode_index, player_url = payload
        safe_anime = "".join(c for c in anime if c.isalnum() or c in " -_").strip()
        out_name = f"{safe_anime} - EP{episode_index + 1}.%(ext)s"
        download_dir = os.path.join(os.path.expanduser("~"), "Downloads", "AnimeCaos")
        os.makedirs(download_dir, exist_ok=True)
        out_template = os.path.join(download_dir, out_name)

        self._download_overlay.set_downloading()
        self._current_download_dir = download_dir

        worker = DownloadWorker(player_url, out_template)
        self._active_download_worker = worker
        worker.signals.progress.connect(self._on_download_progress)
        worker.signals.succeeded.connect(self._on_download_success)
        worker.signals.failed.connect(self._on_download_failed)
        self._append_log(f"Download iniciado: \"{anime}\" Ep {episode_index + 1} -> {download_dir}")
        self._thread_pool.start(worker)

    def _on_download_progress(self, line: str) -> None:
        self._download_overlay.update_progress(line)
        if "[download]" in line or "100%" in line:
            self._set_status(f"Download: {line[:50].strip()}")

    def _on_download_success(self, path: str) -> None:
        self._active_download_worker = None
        download_dir = getattr(self, "_current_download_dir", "")
        self._download_overlay.show_done(download_dir)
        self._append_log(f"Download concluido — salvo em: {download_dir}")
        self._set_status("Download finalizado com sucesso!")

    def _on_download_failed(self, error: str) -> None:
        self._active_download_worker = None
        self._download_overlay.show_error(error)
        self._append_log(f"Download falhou: {error}")
        self._set_status("Erro no download.")

    def _on_download_cancel(self) -> None:
        if self._active_download_worker:
            self._active_download_worker.cancel()
            self._active_download_worker = None
            self._append_log("Download cancelado.")
            self._set_status("Download cancelado.")

    # ── HISTORY ──────────────────────────────────────────────────

    def _reload_history(self, silent: bool = False) -> None:
        try:
            entries = self._history_service.load_entries()
        except Exception as exc:
            self._append_log(f"Falha ao carregar historico: {exc}")
            return

        cards = []
        for entry in entries:
            cards.append({
                "title": entry.anime,
                "badge": f"Ep. {entry.episode_index + 1}",
                "cover_path": self._cover_cache.get(entry.anime),
                "entry": entry,
            })
        self._home_view.set_history_cards(cards)

        for entry in entries:
            if entry.anime not in self._cover_cache:
                self._fetch_card_metadata(entry.anime)

        if not silent and entries:
            self._set_status(f"Historico carregado: {len(entries)} item(ns).")

    def _resume_from_history(self, entry: HistoryEntry) -> None:
        self._run_task(
            status_message=f"Preparando historico de '{entry.anime}'...",
            task=lambda: self._resume_history_entry(entry),
            on_success=self._on_resume_history_finished,
        )

    def _resume_history_entry(self, entry: HistoryEntry) -> dict[str, object]:
        episode_count = self._anime_service.load_history_sources(entry.anime, entry.episode_sources)
        if episode_count <= 0:
            raise ValueError("Historico sem episodios validos.")
        episode_titles = self._anime_service.synthetic_episode_titles(entry.anime)
        return {"entry": entry, "episode_titles": episode_titles}

    def _on_resume_history_finished(self, payload: object) -> None:
        if not isinstance(payload, dict):
            self._set_status("Falha ao preparar historico.")
            return
        entry = payload.get("entry")
        episode_titles = payload.get("episode_titles")
        if not isinstance(entry, HistoryEntry) or not isinstance(episode_titles, list):
            return

        self._current_anime = entry.anime
        self._episodes_anime = entry.anime
        self._episode_titles = [str(t) for t in episode_titles]
        safe_index = min(entry.episode_index, len(self._episode_titles) - 1)
        self._current_episode_index = safe_index

        self._detail_view.set_anime(entry.anime)
        self._detail_view.set_episodes(self._episode_titles, safe_index)
        self._detail_view.scroll_to_episode(safe_index)
        self._fetch_metadata(entry.anime)

        self._set_status("Historico aplicado. Clique para continuar.")
        self._append_log(f"Historico restaurado: \"{entry.anime}\" Ep {safe_index + 1} — {len(self._episode_titles)} episodio(s) disponiveis.")

    # ── METADATA ─────────────────────────────────────────────────

    def _fetch_metadata(self, anime: str) -> None:
        cached_cover = self._cover_cache.get(anime)
        if cached_cover:
            self._detail_view.set_metadata(None, cached_cover)

        worker = FunctionWorker(lambda: (anime, self._anilist_service.fetch_anime_info(anime)))
        self._metadata_workers.add(worker)
        worker.signals.succeeded.connect(self._on_metadata_fetched)
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _on_metadata_fetched(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        anime, info = payload
        if not isinstance(info, dict):
            return

        desc = info.get("description")
        cover = info.get("cover_path")

        if cover and os.path.exists(str(cover)):
            self._cover_cache[anime] = str(cover)

        if self._detail_view.anime_name == anime:
            self._detail_view.set_metadata(desc, str(cover) if cover else None)

    def _fetch_card_metadata(self, anime: str) -> None:
        if anime in self._cover_cache:
            return
        worker = FunctionWorker(lambda a=anime: (a, self._anilist_service.fetch_anime_info(a)))
        self._metadata_workers.add(worker)
        worker.signals.succeeded.connect(self._on_card_metadata_fetched)
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _on_card_metadata_fetched(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        anime, info = payload
        if not isinstance(info, dict):
            return
        cover = info.get("cover_path")
        if cover and os.path.exists(str(cover)):
            self._cover_cache[anime] = str(cover)
            self._home_view.update_card_cover(anime, str(cover))
            self._search_view.update_card_cover(anime, str(cover))

    # ── TASK RUNNER ──────────────────────────────────────────────

    def _run_task(
        self,
        status_message: str,
        task: Callable[[], object],
        on_success: Callable[[object], None],
    ) -> None:
        if self._busy:
            self._set_status("Aguarde a tarefa atual finalizar.")
            return
        self._set_busy(True, status_message)
        worker = FunctionWorker(task)
        self._active_workers.add(worker)
        worker.signals.succeeded.connect(on_success)
        worker.signals.failed.connect(self._on_task_failed)
        worker.signals.finished.connect(lambda current=worker: self._on_task_finished(current))
        self._thread_pool.start(worker)

    def _on_task_failed(self, error_text: str) -> None:
        self._play_overlay.dismiss()
        self._download_overlay.dismiss()
        self._append_log(f"Erro: {error_text.splitlines()[0] if error_text else 'Erro desconhecido'}")
        self._set_status("Falha na operacao.")
        summary = error_text.splitlines()[0] if error_text else "Erro inesperado."
        QMessageBox.critical(self, "Erro", summary)

    def _on_task_finished(self, worker: FunctionWorker) -> None:
        self._active_workers.discard(worker)
        self._set_busy(False)

    def _set_busy(self, busy: bool, status_message: str = "") -> None:
        self._busy = busy
        self._log_view.progress_bar.setVisible(busy)
        if busy:
            self._log_view.progress_bar.setRange(0, 0)
            self._set_status(status_message)
        else:
            self._log_view.progress_bar.setRange(0, 1)
            self._log_view.progress_bar.setValue(0)

    def _set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def _append_log(self, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self._log_view.log_output.appendPlainText(f"[{stamp}] {text}")

    # ── UPDATES ──────────────────────────────────────────────────

    def _check_for_updates(self) -> None:
        worker = UpdaterCheckWorker(self._updater_service)
        worker.signals.succeeded.connect(self._on_update_found)
        self._thread_pool.start(worker)

    def _on_update_found(self, has_update: bool) -> None:
        if not has_update:
            return
        dialog = UpdateDialog(
            self, self._updater_service.latest_version, self._updater_service.release_notes
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._start_update_download()

    def _start_update_download(self) -> None:
        self._set_busy(True, f"Baixando atualizacao (v{self._updater_service.latest_version})...")
        self._log_view.progress_bar.setRange(0, 100)

        import threading

        def update_task():
            def progress_callback(val):
                if isinstance(val, int):
                    if val >= 0:
                        self.update_progress_signal.emit(val)
                elif isinstance(val, str):
                    self.update_status_signal.emit(f"Atualizacao: {val}...")

            success = self._updater_service.perform_update(callback_progress=progress_callback)
            if success:
                self.update_status_signal.emit("Atualizacao pronta! Reiniciando...")
                from PySide6.QtWidgets import QApplication
                self.update_finished_signal.connect(QApplication.quit)
                self.update_finished_signal.emit()
            else:
                self._set_busy(False)
                self.update_status_signal.emit("Falha ao baixar atualizacao.")

        threading.Thread(target=update_task, daemon=True).start()
