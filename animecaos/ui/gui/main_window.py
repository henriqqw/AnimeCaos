from __future__ import annotations

import os
import re
import sys
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from animecaos.services.discord_service import DiscordService
from animecaos.services.downloads_service import DownloadEntry, DownloadsService
from animecaos.services.history_service import HistoryEntry, HistoryService
from animecaos.services.anilist_service import AniListService, AniListStatus
from animecaos.services.anilist_auth_service import AniListAuthService
from animecaos.services.config_service import ConfigService
from animecaos.services.updater_service import UpdaterService
from animecaos.services.manga_service import MangaService
from animecaos.services.manga_history_service import MangaHistoryEntry, MangaHistoryService
from animecaos.services.manga_download_service import MangaDownloadService

from .animated_stack import AnimatedStackedWidget
from .download_overlay import DownloadOverlay
from .icons import icon_search, icon_terminal
from .mini_player import MiniPlayer
from .play_overlay import PlayOverlay
from .sidebar import SidebarNav
from .views import AccountView, AnimeDetailView, AnimatedButton, DownloadsView, HomeView, SearchView
from .manga_views import MangaHomeView, MangaDetailView, MangaReaderView
from .workers import FunctionWorker, DownloadWorker, MangaDownloadWorker, UpdaterCheckWorker


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
_VIEW_ACCOUNT = 4
_VIEW_DOWNLOADS = 5
_VIEW_MANGA_HOME = 6
_VIEW_MANGA_DETAIL = 7
_VIEW_MANGA_READER = 8


class MainWindow(QMainWindow):
    update_progress_signal = Signal(int)
    update_status_signal = Signal(str)
    update_finished_signal = Signal()
    _discover_card_unavailable = Signal(str, str)  # (section, title)
    _discover_filter_done = Signal()

    def __init__(
        self,
        anime_service: AnimeService,
        history_service: HistoryService,
        anilist_service: AniListService,
        config_service: ConfigService | None = None,
        anilist_auth_service: AniListAuthService | None = None,
        preloaded_discover: dict | None = None,
    ) -> None:
        super().__init__()
        self._anime_service = anime_service
        self._history_service = history_service
        self._anilist_service = anilist_service
        self._downloads_service = DownloadsService()
        self._config_service = config_service or ConfigService()
        self._anilist_auth_service = anilist_auth_service or AniListAuthService(self._config_service)
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
        self._manga_service = MangaService()
        self._manga_history_service = MangaHistoryService()
        self._manga_download_service = MangaDownloadService()
        self._current_manga: dict | None = None
        self._manga_chapters: list[dict] = []
        self._current_manga_chapter_index: int = -1
        self._manga_cover_cache: dict[str, str] = {}  # manga_id -> local path
        self._active_manga_dl: dict[str, MangaDownloadWorker] = {}  # chapter_id -> worker

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
        self._reload_manga_history()
        self._check_for_updates()
        self._restore_anilist_state()
        self._preloaded_discover = preloaded_discover
        self._load_discover_sections()

        # Refresh AniList stats on startup + auto-sync every 5 minutes.
        if self._anilist_auth_service.is_authenticated():
            self._refresh_account_stats()
        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(5 * 60 * 1000)
        self._stats_timer.timeout.connect(self._refresh_account_stats)
        self._stats_timer.start()

        # Discord Rich Presence
        self._discord = DiscordService(self._config_service)
        self._discord.connect()
        self._update_discord_ui()

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
        sidebar_wrapper = QWidget()
        sidebar_wrapper.setFixedWidth(72)
        sidebar_wrapper.setStyleSheet("background: transparent;")
        sw_layout = QVBoxLayout(sidebar_wrapper)
        sw_layout.setContentsMargins(8, 10, 4, 10)
        sw_layout.setSpacing(0)
        sw_layout.addWidget(self._sidebar)
        body.addWidget(sidebar_wrapper)

        self._stack = AnimatedStackedWidget()
        self._home_view = HomeView()
        self._search_view = SearchView()
        self._detail_view = AnimeDetailView()
        self._log_view = LogView()
        self._account_view = AccountView()
        self._downloads_view = DownloadsView()

        self._manga_home_view = MangaHomeView()
        self._manga_detail_view = MangaDetailView()
        self._manga_reader_view = MangaReaderView()

        self._stack.addWidget(self._home_view)          # 0
        self._stack.addWidget(self._search_view)        # 1
        self._stack.addWidget(self._detail_view)        # 2
        self._stack.addWidget(self._log_view)           # 3
        self._stack.addWidget(self._account_view)       # 4
        self._stack.addWidget(self._downloads_view)     # 5
        self._stack.addWidget(self._manga_home_view)    # 6
        self._stack.addWidget(self._manga_detail_view)  # 7
        self._stack.addWidget(self._manga_reader_view)  # 8

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

        app_title = QLabel('Anime<span style="color: #D44242;">Caos</span>')
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

        self._search_btn = AnimatedButton()
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

        # Account view
        self._account_view.connect_clicked.connect(self._on_anilist_login)
        self._account_view.disconnect_clicked.connect(self._on_anilist_logout)
        self._account_view.refresh_clicked.connect(self._refresh_account_stats)
        self._account_view.discord_toggled.connect(self._on_discord_toggled)

        # Mini player
        self._mini_player.close_clicked.connect(self._on_mini_player_closed)

        # Discovery sections
        self._home_view.discover_clicked.connect(self._on_discover_card_clicked)
        self._home_view.anilist_page_requested.connect(self._on_open_anilist_page)
        self._discover_card_unavailable.connect(self._on_discover_card_unavailable)
        self._discover_filter_done.connect(lambda: self._home_view.trim_discover_sections(10))

        # Downloads view
        self._downloads_view.play_clicked.connect(self._on_download_episode_play)
        self._downloads_view.delete_clicked.connect(self._on_download_episode_delete)
        self._downloads_view.open_folder_clicked.connect(self._on_downloads_open_folder)

        # Manga views
        self._manga_home_view.search_requested.connect(self._on_manga_search)
        self._manga_home_view.manga_clicked.connect(self._on_manga_card_clicked)
        self._manga_home_view.history_clicked.connect(self._on_manga_history_clicked)
        self._manga_detail_view.back_clicked.connect(self._navigate_to_manga_home)
        self._manga_detail_view.chapter_clicked.connect(self._on_manga_chapter_clicked)
        self._manga_detail_view.download_chapter_clicked.connect(self._on_manga_detail_dl_chapter)
        self._manga_detail_view.download_all_clicked.connect(self._on_manga_detail_dl_all)
        self._manga_detail_view.download_selected_clicked.connect(self._on_manga_detail_dl_selected)
        self._reader_from_downloads: bool = False
        self._manga_reader_view.back_clicked.connect(self._on_manga_reader_back)
        self._manga_reader_view.chapter_requested.connect(self._on_manga_chapter_requested)
        self._manga_reader_view.progress_changed.connect(self._on_manga_progress_changed)
        self._manga_reader_view.download_chapter_clicked.connect(self._on_manga_reader_dl_chapter)
        self._downloads_view.manga_delete_clicked.connect(self._on_manga_download_delete)
        self._downloads_view.manga_open_clicked.connect(self._on_manga_download_open)

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
        elif view_idx == _VIEW_ACCOUNT:
            self._sidebar.set_active("account")
            self._breadcrumb.setText("  >  Conta")
        elif view_idx == _VIEW_DOWNLOADS:
            self._sidebar.set_active("downloads")
            self._breadcrumb.setText("  >  Downloads")
        elif view_idx == _VIEW_MANGA_HOME:
            self._sidebar.set_active("manga")
            self._breadcrumb.setText("  >  Manga")
        elif view_idx == _VIEW_MANGA_DETAIL:
            self._sidebar.set_active("manga")
            name = (self._current_manga or {}).get("title", "")
            self._breadcrumb.setText(f"  >  Manga  >  {name}" if name else "  >  Manga")
        elif view_idx == _VIEW_MANGA_READER:
            self._sidebar.set_active("manga")
            self._breadcrumb.setText("  >  Manga  >  Leitor")

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
        elif key == "downloads":
            self._navigate_to_downloads()
        elif key == "manga":
            self._navigate_to_manga_home()
        elif key == "log":
            self._stack.slide_to(_VIEW_LOG)
            self._breadcrumb.setText("  >  Log de Eventos")
        elif key == "account":
            self._navigate_to_account()

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
            task=lambda: self._search_with_translation(query),
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

        self._fetch_covers_for_results(titles, self._last_search_query)

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
        self._discord.set_loading(anime, index + 1)

        self._run_task(
            status_message=f"Reproduzindo '{anime}' episodio {index + 1}...",
            task=lambda: self._play_episode(anime, index),
            on_success=self._on_play_finished,
        )

    def _play_episode(self, anime: str, episode_index: int) -> dict[str, object]:
        player_url = self._anime_service.resolve_player_url(anime, episode_index)

        # Pre-warm next episode URL cache while this episode plays.
        # Runs as a daemon thread so it doesn't block MPV opening.
        # By the time the user finishes the episode, the URL is cached → autoplay is instant.
        def _prefetch_next():
            try:
                self._anime_service.resolve_player_url(anime, episode_index + 1)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).debug("Prefetch ep %d falhou: %s", episode_index + 1, exc)
        threading.Thread(target=_prefetch_next, daemon=True).start()

        # Dismiss overlay from worker thread before blocking on player
        from PySide6.QtCore import QMetaObject, Qt as QtConst
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
        self._discord.update(anime, episode_index + 1, ep_count)

        self._detail_view.highlight_episode(episode_index)
        self._detail_view.scroll_to_episode(episode_index)

        try:
            self._history_service.save_entry(anime, episode_index, episode_sources)
        except Exception as exc:
            self._append_log(f"Historico nao salvo: {exc}")
        else:
            self._reload_history(silent=True)

        # Only sync to AniList when the episode played to natural EOF.
        # Quit mid-episode → eof=False → no spurious progress update.
        if self._anilist_auth_service.is_authenticated() and payload.get("eof"):
            media_id = self._anilist_service.get_media_id(anime)
            ep = episode_index + 1
            total = len(self._episode_titles)
            if media_id:
                sync_worker = FunctionWorker(
                    lambda mid=media_id, e=ep, t=total:
                        self._anilist_auth_service.update_progress(mid, e, t)
                )
                sync_worker.signals.succeeded.connect(self._on_anilist_synced)
                self._thread_pool.start(sync_worker)
            else:
                # media_id not in cache yet — resolve via AniList then sync
                self._fetch_and_sync_anilist(anime, ep, total)

        self._set_status(f"Episodio {episode_index + 1} finalizado.")
        self._append_log(f"Reproducao finalizada: \"{anime}\" Ep {episode_index + 1}.")

        if payload.get("eof") and self._mini_player.is_autoplay():
            next_idx = episode_index + 1
            if next_idx < len(self._episode_titles):
                self._append_log(f"Auto-play: avancando para Ep {next_idx + 1}...")
                # Defer past the _busy reset (finished signal fires after succeeded).
                QTimer.singleShot(0, lambda idx=next_idx: self._on_episode_play_clicked(idx))

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

    def _reload_manga_history(self) -> None:
        try:
            entries = self._manga_history_service.load_entries()
        except Exception:
            return
        self._manga_home_view.set_history(entries)
        for entry in entries:
            if entry.cover_path and os.path.exists(entry.cover_path):
                self._manga_cover_cache[entry.manga_id] = entry.cover_path

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

    # ── DOWNLOADS LIBRARY ────────────────────────────────────────

    def _navigate_to_downloads(self) -> None:
        self._push_nav(_VIEW_DOWNLOADS)
        self._stack.slide_to(_VIEW_DOWNLOADS)
        self._sidebar.set_active("downloads")
        self._breadcrumb.setText("  >  Downloads")
        self._refresh_downloads_view()

    def _refresh_downloads_view(self) -> None:
        groups = self._downloads_service.group_by_anime()
        self._downloads_view.set_downloads(groups, self._cover_cache)
        for anime in groups:
            if anime not in self._cover_cache:
                self._fetch_card_metadata(anime)
        manga_groups = self._manga_download_service.group_by_manga()
        self._downloads_view.set_manga_downloads(manga_groups, self._manga_cover_cache)
        for manga_title in manga_groups:
            for path in self._manga_cover_cache.values():
                self._downloads_view.update_manga_cover(manga_title, path)

    def _on_download_episode_play(self, entry: object) -> None:
        if not isinstance(entry, DownloadEntry):
            return
        self._current_anime = entry.anime
        self._current_episode_index = entry.episode_num - 1
        self._play_overlay.show_loading(entry.anime, entry.episode_num - 1)
        self._run_task(
            status_message=f"Reproduzindo '{entry.anime}' Ep {entry.episode_num} (offline)...",
            task=lambda e=entry: self._play_local_file(e),
            on_success=self._on_local_play_finished,
        )

    def _play_local_file(self, entry: DownloadEntry) -> dict:
        from animecaos.player.video_player import play_video as _pv
        from PySide6.QtCore import QMetaObject, Qt as QtConst
        QMetaObject.invokeMethod(
            self._play_overlay, "dismiss", QtConst.ConnectionType.QueuedConnection
        )
        result = _pv(entry.file_path)
        return {"entry": entry, **result}

    def _on_local_play_finished(self, payload: object) -> None:
        self._play_overlay.dismiss()
        if not isinstance(payload, dict):
            return
        entry = payload.get("entry")
        if not isinstance(entry, DownloadEntry):
            return
        cover = self._cover_cache.get(entry.anime)
        self._mini_player.show_playback(entry.anime, entry.episode_num - 1, entry.episode_num, cover)
        self._discord.update(entry.anime, entry.episode_num, entry.episode_num)
        self._set_status(f"Ep {entry.episode_num} finalizado.")
        self._append_log(f"Reproducao offline: '{entry.anime}' Ep {entry.episode_num}.")

    def _on_download_episode_delete(self, entry: object) -> None:
        if not isinstance(entry, DownloadEntry):
            return
        self._downloads_service.delete(entry)
        self._append_log(f"Download removido: '{entry.anime}' Ep {entry.episode_num}.")
        self._refresh_downloads_view()

    def _on_downloads_open_folder(self) -> None:
        path = self._downloads_service.get_dir()
        path.mkdir(parents=True, exist_ok=True)
        import subprocess as _sp
        try:
            if os.name == "nt":
                _sp.Popen(["explorer", str(path)])
            else:
                _sp.Popen(["xdg-open", str(path)])
        except Exception:
            pass

    # ── DISCOVERY SECTIONS ───────────────────────────────────────

    def _load_discover_sections(self) -> None:
        if self._preloaded_discover is not None:
            # Data already loaded during splash — apply directly on next event loop tick
            data = self._preloaded_discover
            self._preloaded_discover = None
            QTimer.singleShot(0, lambda: self._on_discover_loaded(data))
            # Still run background availability filter
            trending = data.get("trending") or []
            seasonal = data.get("seasonal") or []
            spotlight_title = (data.get("spotlight") or {}).get("title", "")
            QTimer.singleShot(50, lambda: self._start_discover_availability_check(trending, seasonal, spotlight_title))
            return
        worker = FunctionWorker(self._fetch_discover_data)
        self._metadata_workers.add(worker)
        worker.signals.succeeded.connect(self._on_discover_loaded)
        worker.signals.failed.connect(lambda _: None)
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _fetch_discover_data(self) -> dict:
        trending = self._anilist_service.fetch_trending(per_page=25)
        seasonal = self._anilist_service.fetch_seasonal(per_page=25)
        spotlight = None
        spotlight_rank = 1
        for i, candidate in enumerate(trending[:8]):
            if self._spotlight_candidate_available(candidate):
                spotlight = self._anilist_service.fetch_spotlight_extras(candidate)
                spotlight_rank = i + 1
                break
        if spotlight is not None:
            spotlight["_rank"] = spotlight_rank
        return {
            "trending": trending,
            "seasonal": seasonal,
            "spotlight": spotlight,
        }

    def _spotlight_candidate_available(self, card: dict) -> bool:
        """Quick check: does the scraper return any results for this anime?"""
        title = card.get("title", "")
        if not title:
            return False
        base = title.split(":")[0].strip()
        if base == base.upper() and len(base) > 1:
            base = base.title()
        if self._anime_service.search_animes(base):
            return True
        variants = self._anilist_service.get_title_variants(title)
        for variant in variants:
            if not variant:
                continue
            if self._anime_service.search_animes(variant):
                return True
            short = variant.split()[0].strip(" -") if variant.split() else ""
            if short and len(short) >= 3 and self._anime_service.search_animes(short):
                return True
        return False

    def _on_discover_loaded(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        trending = payload.get("trending") or []
        seasonal = payload.get("seasonal") or []
        spotlight = payload.get("spotlight")
        self._home_view.set_trending_cards(trending)
        self._home_view.set_seasonal_cards(seasonal)
        if spotlight:
            rank = spotlight.get("_rank", 1)
            self._home_view.set_spotlight(spotlight, rank=rank)
            banner_path = spotlight.get("banner_path")
            if banner_path and os.path.exists(str(banner_path)):
                self._home_view.set_spotlight_banner(str(banner_path))
        status = self._anilist_service.api_status
        if self._anilist_service.is_offline:
            desc = status.ui_description()
            retry = self._anilist_service.retry_after
            if retry is not None:
                desc = f"Aguarde ~{retry}s antes de tentar novamente. " + desc
            self._home_view.show_anilist_offline_banner(status.ui_title(), desc)
        else:
            self._home_view.hide_anilist_offline_banner()
        # Populate cover_cache from already-downloaded covers — no extra AniList calls.
        for card in trending + seasonal:
            title = card.get("title", "")
            cover_path = card.get("cover_path")
            if title and cover_path and os.path.exists(str(cover_path)):
                self._cover_cache[title] = str(cover_path)

        # Background availability filter — remove cards the scraper can't find.
        # Runs after display so UI appears immediately; unavailable cards vanish quietly.
        spotlight_title = (spotlight or {}).get("title", "")
        self._start_discover_availability_check(trending, seasonal, spotlight_title)

    def _start_discover_availability_check(
        self,
        trending: list[dict],
        seasonal: list[dict],
        spotlight_title: str,
    ) -> None:
        """Spawn a background thread that checks each discover card and removes unavailable ones."""
        tagged = [("trending", c) for c in trending] + [("seasonal", c) for c in seasonal]
        if not tagged:
            return

        def run() -> None:
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = {
                    pool.submit(self._card_is_available, card): (section, card.get("title", ""))
                    for section, card in tagged
                    if card.get("title") and card.get("title") != spotlight_title
                }
                for future in as_completed(futures):
                    section, title = futures[future]
                    try:
                        available = future.result()
                    except Exception:
                        available = True  # keep on error
                    if not available and title:
                        self._discover_card_unavailable.emit(section, title)
            self._discover_filter_done.emit()

        t = threading.Thread(target=run, daemon=True)
        t.start()

    def _card_is_available(self, card: dict) -> bool:
        """Strict availability check for discover cards — no AniList variant fallback.
        Uses only title-derived queries so JoJo variants don't match unrelated JoJo seasons.
        """
        title = card.get("title", "")
        if not title:
            return False

        # Split on ": " (colon+space) to drop subtitle — "Steel Ball Run: JoJo's..." → "Steel Ball Run"
        # Does NOT split "Re:ZERO" (no space after colon) so those titles stay intact.
        query = re.split(r":\s+", title, maxsplit=1)[0].strip()
        if query == query.upper() and len(query) > 1:
            query = query.title()

        if len(query) >= 3 and self._anime_service.search_animes(query):
            return True

        # Secondary: first 3 words of the full title (helps long titles like "Re:ZERO -Starting Life...")
        words = title.split()
        if len(words) > 3:
            short = " ".join(words[:3])
            if short.lower() != query.lower() and self._anime_service.search_animes(short):
                return True

        return False

    def _on_discover_card_unavailable(self, section: str, title: str) -> None:
        if section == "trending":
            self._home_view.remove_trending_card(title)
        elif section == "seasonal":
            self._home_view.remove_seasonal_card(title)

    def _on_open_anilist_page(self, anilist_id: int) -> None:
        webbrowser.open(f"https://anilist.co/anime/{anilist_id}")

    def _on_discover_card_clicked(self, data: dict) -> None:
        title = data.get("title", "")
        if not title:
            return
        query = title.split(":")[0].strip()
        if query == query.upper() and len(query) > 1:
            query = query.title()

        # The discover card already has a real AniList cover — carry it forward
        anilist_cover: str | None = data.get("cover_path") or None

        self._last_search_query = query
        self._search_input.setText(query)
        self._search_view.show_searching(query)
        self._navigate_to_search()
        self._append_log(f"Discover: buscando '{query}'...")
        self._set_status(f"Buscando '{query}'...")

        worker = FunctionWorker(lambda q=query: self._search_with_translation(q))
        self._metadata_workers.add(worker)
        worker.signals.succeeded.connect(
            lambda results, t=title, q=query, c=anilist_cover:
                self._on_discover_search_done(results, t, q, c)
        )
        worker.signals.failed.connect(
            lambda _e, q=query: (
                self._search_view.set_results([], q),
                self._set_status(f"Erro ao buscar '{q}'."),
            )
        )
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _on_discover_search_done(
        self,
        results: object,
        original_title: str,
        query: str,
        anilist_cover: str | None = None,
    ) -> None:
        if not isinstance(results, list):
            results = []
        titles = [str(r) for r in results]
        cards = [{"title": t, "cover_path": self._cover_cache.get(t)} for t in titles]
        self._search_view.set_results(cards, query)

        if not titles:
            self._set_status(f"'{query}' nao encontrado nas fontes.")
            self._append_log(f"Discover: '{original_title}' sem resultados.")
            return

        self._set_status(f"{len(titles)} resultado(s) para '{query}'.")

        # Apply AniList cover (already downloaded) to all results that lack one
        if anilist_cover and os.path.exists(anilist_cover):
            for t in titles:
                if t not in self._cover_cache:
                    self._cover_cache[t] = anilist_cover
                    self._search_view.update_card_cover(t, anilist_cover)
        else:
            # Fallback: fetch covers per title AND via original query
            self._fetch_covers_for_results(titles, query)

        self._append_log(f"Discover: {len(titles)} resultado(s) para '{original_title}'.")

    def _search_with_translation(self, query: str) -> list[str]:
        """Search scrapers with progressive fallback:
        1. Original query
        2. Compact-query expansions (space at word boundaries)
        3. AniList title variants (romaji / english) + short first token
        """
        results = self._anime_service.search_animes(query)
        if results:
            return results

        # ── Step 2: compact query expansions ──────────────────────────
        # "rezero" → try "re zero" (pos 2), "rez ero" (pos 3), "reze ro" (pos 4)
        # "re zero" slugifies to "re-zero" which most sites have indexed.
        if " " not in query and "-" not in query and len(query) > 4:
            tried: set[str] = {query.lower()}
            for pos in (2, 3, 4):
                if pos >= len(query) - 1:
                    break
                expanded = query[:pos] + " " + query[pos:]
                if expanded.lower() not in tried:
                    tried.add(expanded.lower())
                    self._append_log(f"Busca: tentando expansao '{expanded}'...")
                    results = self._anime_service.search_animes(expanded)
                    if results:
                        return results

        # ── Step 3: AniList title variant fallback ────────────────────
        variants = self._anilist_service.get_title_variants(query)
        seen: set[str] = {query.lower()}
        candidates: list[str] = []

        for v in variants:
            if not v:
                continue
            if v.lower() not in seen:
                candidates.append(v)
                seen.add(v.lower())
            # Short: first space-token — "Re:Zero kara..." → "Re:Zero"
            words = v.split()
            short = words[0].strip(" -") if words else ""
            if short and short.lower() not in seen and len(short) >= 3:
                candidates.append(short)
                seen.add(short.lower())

        for candidate in candidates:
            self._append_log(f"Busca: '{query}' sem resultados — tentando '{candidate}'...")
            results = self._anime_service.search_animes(candidate)
            if results:
                return results

        return []

    @staticmethod
    def _normalize_title(text: str) -> str:
        """Normalize for fuzzy comparison: lowercase, strip accents, collapse punctuation."""
        import unicodedata
        # Remove accents (é→e, ã→a, ü→u, etc.)
        nfkd = unicodedata.normalize("NFKD", text)
        ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
        # Lowercase
        s = ascii_text.lower()
        # Apostrophes / curly quotes → remove (Hell's → hells, don't → dont)
        s = re.sub(r"['\u2019\u2018`]", "", s)
        # Dashes, underscores → space (Re-Zero → re zero)
        s = re.sub(r"[-_]", " ", s)
        # Remove remaining non-alphanumeric (except spaces)
        s = re.sub(r"[^\w\s]", "", s)
        # Collapse whitespace
        return " ".join(s.split())

    def _fuzzy_best_match(self, query: str, candidates: list[str]) -> str:
        if len(candidates) == 1:
            return candidates[0]
        try:
            from fuzzywuzzy import fuzz
            q = self._normalize_title(query)
            return max(candidates, key=lambda c: fuzz.partial_ratio(q, self._normalize_title(c)))
        except Exception:
            return candidates[0]

    def _fuzzy_score(self, query: str, candidate: str) -> int:
        try:
            from fuzzywuzzy import fuzz
            return fuzz.partial_ratio(self._normalize_title(query), self._normalize_title(candidate))
        except Exception:
            return 0

    # ── ANILIST ACCOUNT ──────────────────────────────────────────

    def _navigate_to_account(self) -> None:
        self._push_nav(_VIEW_ACCOUNT)
        self._stack.slide_to(_VIEW_ACCOUNT)
        self._sidebar.set_active("account")
        self._breadcrumb.setText("  >  Conta")
        # Show cached values immediately, then refresh live from AniList.
        user = self._anilist_auth_service.get_user()
        self._account_view.set_authenticated(user)
        if user and user.get("avatar_url"):
            self._fetch_avatar()
        if self._anilist_auth_service.is_authenticated():
            self._refresh_account_stats()
        self._update_discord_ui()

    def _restore_anilist_state(self) -> None:
        if self._anilist_auth_service.is_authenticated():
            self._sidebar.set_account_connected(True)

    def _on_anilist_login(self) -> None:
        self._account_view.set_connecting(True)
        worker = FunctionWorker(self._anilist_auth_service.login)
        worker.signals.succeeded.connect(self._on_login_result)
        worker.signals.failed.connect(lambda _: self._on_login_result(False))
        self._thread_pool.start(worker)

    def _on_login_result(self, success: object) -> None:
        self._account_view.set_connecting(False)
        if success:
            user = self._anilist_auth_service.get_user()
            self._account_view.set_authenticated(user)
            self._sidebar.set_account_connected(True)
            if user and user.get("avatar_url"):
                self._fetch_avatar()
            self._append_log(f"AniList: conectado como {(user or {}).get('username', '')}.")
        else:
            self._append_log("AniList: login cancelado ou falhou.")

    def _on_anilist_logout(self) -> None:
        self._anilist_auth_service.logout()
        self._account_view.set_authenticated(None)
        self._sidebar.set_account_connected(False)
        self._append_log("AniList: desconectado.")

    # ── DISCORD ──────────────────────────────────────────────────

    def _on_mini_player_closed(self) -> None:
        self._discord.clear()

    def _on_discord_toggled(self, enabled: bool) -> None:
        self._config_service.set("discord_rp_enabled", enabled)
        if enabled:
            self._discord.reconnect()
        else:
            self._discord.disconnect()
        QTimer.singleShot(1500, self._update_discord_ui)

    def _update_discord_ui(self) -> None:
        self._account_view.set_discord_state(
            enabled=bool(self._config_service.get("discord_rp_enabled")),
            connected=self._discord.is_connected(),
        )

    def closeEvent(self, event) -> None:
        self._discord.disconnect()
        super().closeEvent(event)

    def _fetch_and_sync_anilist(self, anime: str, episode: int, total: int) -> None:
        """Resolve media_id on-demand (if not yet cached) then sync progress."""
        def task(a=anime, e=episode, t=total):
            self._anilist_service.fetch_anime_info(a)
            mid = self._anilist_service.get_media_id(a)
            if not mid:
                return False
            return self._anilist_auth_service.update_progress(mid, e, t)
        worker = FunctionWorker(task)
        worker.signals.succeeded.connect(self._on_anilist_synced)
        self._metadata_workers.add(worker)
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _on_anilist_synced(self, success: object) -> None:
        if not success:
            self._append_log("AniList: falha ao sincronizar progresso — verifique conexao/token.")
            return
        self._append_log("AniList: progresso sincronizado.")
        # Delay 3 s before re-fetching stats: AniList aggregates episodesWatched
        # asynchronously on their server — querying immediately returns stale data.
        QTimer.singleShot(3000, self._refresh_account_stats)

    def _refresh_account_stats(self) -> None:
        if not self._anilist_auth_service.is_authenticated():
            return
        worker = FunctionWorker(self._anilist_auth_service.refresh_user_stats)
        self._metadata_workers.add(worker)
        worker.signals.succeeded.connect(self._on_anilist_stats_refreshed)
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _on_anilist_stats_refreshed(self, result: object) -> None:
        if result is False:
            self._append_log("AniList: falha ao buscar stats — verifique conexao/token.")
        user = self._anilist_auth_service.get_user()
        if user and result is not False:
            self._append_log(
                f"AniList stats: {user.get('anime_count', 0)} animes, "
                f"{user.get('episodes_watched', 0)} eps, "
                f"{(user.get('minutes_watched') or 0) // 60}h"
            )
        self._account_view.set_authenticated(user)

    def _fetch_avatar(self) -> None:
        worker = FunctionWorker(self._anilist_auth_service.fetch_avatar_bytes)
        worker.signals.succeeded.connect(self._on_avatar_fetched)
        self._thread_pool.start(worker)

    def _on_avatar_fetched(self, data: object) -> None:
        if not isinstance(data, bytes) or not data:
            return
        from PySide6.QtGui import QPixmap as _QPixmap
        pm = _QPixmap()
        pm.loadFromData(data)
        if not pm.isNull():
            self._account_view.set_avatar_pixmap(pm)

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

    @staticmethod
    def _clean_anilist_key(title: str) -> str:
        """Derive the AniList search key from a scraper title (mirrors fetch_anime_info logic)."""
        clean = title.replace("(Dublado)", "").replace("(Legendado)", "").strip()
        if " - " in clean:
            clean = clean.split(" - ")[0].strip()
        return clean.lower()

    def _fetch_covers_for_results(self, titles: list[str], search_query: str) -> None:
        """Group titles by cleaned AniList key → one fetch per group (avoids rate-limiting).
        Cover is applied to all titles in the group simultaneously.
        """
        missing = [t for t in titles if t not in self._cover_cache]
        if not missing:
            return

        groups: dict[str, list[str]] = {}
        for t in missing:
            key = self._clean_anilist_key(t)
            groups.setdefault(key, []).append(t)

        for clean_key, group_titles in groups.items():
            self._fetch_cover_for_group(clean_key, group_titles)

        # Extra: user query as fallback — in case scraper titles don't match any group key
        if search_query and self._clean_anilist_key(search_query) not in groups:
            def _qfetch(q: str = search_query, ts: list = list(missing)) -> tuple:
                info = self._anilist_service.fetch_anime_info(q)
                return info, q, ts
            qworker = FunctionWorker(_qfetch)
            self._metadata_workers.add(qworker)
            qworker.signals.succeeded.connect(self._on_query_cover_fetched)
            qworker.signals.finished.connect(lambda w=qworker: self._metadata_workers.discard(w))
            self._thread_pool.start(qworker)

    def _fetch_cover_for_group(self, clean_key: str, group_titles: list[str]) -> None:
        def task(k: str = clean_key, ts: list = list(group_titles)) -> tuple:
            info = self._anilist_service.fetch_anime_info(k)
            return info, ts
        worker = FunctionWorker(task)
        self._metadata_workers.add(worker)
        worker.signals.succeeded.connect(self._on_group_cover_fetched)
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _on_group_cover_fetched(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        info, group_titles = payload
        if not isinstance(info, dict) or not isinstance(group_titles, list):
            return
        cover = info.get("cover_path")
        if not cover or not os.path.exists(str(cover)):
            return
        for t in group_titles:
            if t not in self._cover_cache:
                self._cover_cache[t] = str(cover)
                self._home_view.update_card_cover(t, str(cover))
                self._home_view.update_discover_cover(t, str(cover))
                self._search_view.update_card_cover(t, str(cover))

    def _on_query_cover_fetched(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 3:
            return
        info, query, titles = payload
        if not isinstance(info, dict) or not isinstance(titles, list):
            return
        cover = info.get("cover_path")
        if not cover or not os.path.exists(str(cover)):
            return
        # Apply to ALL titles that still have no cover (query-level fallback)
        for t in [str(t) for t in titles]:
            if t not in self._cover_cache:
                self._cover_cache[t] = str(cover)
                self._home_view.update_card_cover(t, str(cover))
                self._home_view.update_discover_cover(t, str(cover))
                self._search_view.update_card_cover(t, str(cover))

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
            self._home_view.update_discover_cover(anime, str(cover))
            self._search_view.update_card_cover(anime, str(cover))
            self._downloads_view.update_cover(anime, str(cover))

    # ── MANGA ────────────────────────────────────────────────────

    def _navigate_to_manga_home(self) -> None:
        self._push_nav(_VIEW_MANGA_HOME)
        self._stack.slide_to(_VIEW_MANGA_HOME)
        self._sidebar.set_active("manga")
        self._breadcrumb.setText("  >  Manga")
        self._manga_home_view.set_history(self._manga_history_service.load_entries())

    def _on_manga_reader_back(self) -> None:
        if self._reader_from_downloads:
            self._reader_from_downloads = False
            self._push_nav(_VIEW_DOWNLOADS)
            self._stack.slide_to(_VIEW_DOWNLOADS)
            self._breadcrumb.setText("  >  Downloads")
        else:
            self._navigate_to_manga_detail_current()

    def _navigate_to_manga_detail_current(self) -> None:
        manga = self._current_manga
        if manga:
            self._push_nav(_VIEW_MANGA_DETAIL)
            self._stack.slide_to(_VIEW_MANGA_DETAIL)
            self._breadcrumb.setText(f"  >  Manga  >  {manga.get('title', '')}")

    def _on_manga_search(self, query: str) -> None:
        self._manga_home_view.show_searching(query)
        self._append_log(f"Manga: buscando \"{query}\"...")
        worker = FunctionWorker(lambda q=query: self._manga_service.search_manga(q))
        self._metadata_workers.add(worker)
        worker.signals.succeeded.connect(
            lambda results, q=query: self._on_manga_search_done(results, q)
        )
        worker.signals.failed.connect(
            lambda e, q=query: (
                self._manga_home_view.set_results([], q),
                self._append_log(f"Manga: erro na busca — {e}"),
            )
        )
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _on_manga_search_done(self, results: object, query: str) -> None:
        if not isinstance(results, list):
            results = []
        self._manga_home_view.set_results(results, query)
        self._append_log(f"Manga: {len(results)} resultado(s) para \"{query}\".")
        for m in results:
            mid = m.get("id", "")
            cover_url = m.get("cover_url", "")
            if mid and cover_url and mid not in self._manga_cover_cache:
                self._fetch_manga_cover(mid, cover_url)
            if mid:
                self._verify_manga_chapters(mid)

    def _verify_manga_chapters(self, manga_id: str) -> None:
        def task(mid=manga_id):
            return mid, self._manga_service.has_chapters(mid)

        worker = FunctionWorker(task)
        self._metadata_workers.add(worker)
        worker.signals.succeeded.connect(self._on_manga_chapters_verified)
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _on_manga_chapters_verified(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        mid, has_chapters = payload
        if not has_chapters:
            self._manga_home_view.mark_unavailable(mid)
            self._append_log(f"Manga: {mid} marcado como indisponível (sem capítulos hospedados).")

    def _on_manga_card_clicked(self, manga: dict) -> None:
        self._current_manga = manga
        self._manga_chapters = []
        self._current_manga_chapter_index = -1

        self._push_nav(_VIEW_MANGA_DETAIL)
        self._manga_detail_view.set_manga(manga)
        self._stack.slide_to(_VIEW_MANGA_DETAIL)
        self._breadcrumb.setText(f"  >  Manga  >  {manga.get('title', '')}")

        mid = manga.get("id", "")
        cover_url = manga.get("cover_url", "")
        if mid and mid in self._manga_cover_cache:
            self._manga_detail_view.set_cover(self._manga_cover_cache[mid])
        elif mid and cover_url:
            self._fetch_manga_cover(mid, cover_url, detail_view=True)

        if mid:
            worker = FunctionWorker(lambda: (mid, self._manga_service.fetch_chapters(mid)))
            self._metadata_workers.add(worker)
            worker.signals.succeeded.connect(self._on_manga_chapters_loaded)
            worker.signals.failed.connect(
                lambda e: self._append_log(f"Manga: erro ao carregar capítulos — {e}")
            )
            worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
            self._thread_pool.start(worker)

    def _on_manga_chapters_loaded(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        mid, chapters = payload
        if not isinstance(chapters, list):
            return
        if self._current_manga and self._current_manga.get("id") == mid:
            self._manga_chapters = chapters
            self._manga_detail_view.set_chapters(chapters)
            self._append_log(
                f"Manga: {len(chapters)} capítulo(s) carregado(s) para \"{self._current_manga.get('title', '')}\"."
            )
            # Mark already-downloaded chapters
            title = self._current_manga.get("title", "")
            if title and chapters:
                downloaded = {
                    ch.get("label", "")
                    for ch in chapters
                    if self._manga_download_service.is_downloaded(title, ch.get("label", ""))
                }
                if downloaded:
                    self._manga_detail_view.mark_downloaded_chapters(downloaded)

    def _on_manga_chapter_clicked(self, index: int) -> None:
        if not self._current_manga or not self._manga_chapters:
            return
        if not (0 <= index < len(self._manga_chapters)):
            return
        self._current_manga_chapter_index = index
        self._manga_detail_view.highlight_chapter(index)

        chapter = self._manga_chapters[index]
        mid = self._current_manga.get("id", "")
        cover_path = self._manga_cover_cache.get(mid)

        self._reader_from_downloads = False
        self._push_nav(_VIEW_MANGA_READER)
        self._stack.slide_to(_VIEW_MANGA_READER)
        self._breadcrumb.setText("  >  Manga  >  Leitor")

        self._manga_reader_view.load_chapter(
            manga_service=self._manga_service,
            manga_id=mid,
            manga_title=self._current_manga.get("title", ""),
            chapter=chapter,
            chapter_index=index,
            chapter_count=len(self._manga_chapters),
            resume_page=0,
            cover_path=cover_path,
        )
        self._append_log(
            f"Manga: abrindo \"{self._current_manga.get('title', '')}\" — {chapter.get('label', '')}."
        )

    def _on_manga_chapter_requested(self, index: int) -> None:
        self._on_manga_chapter_clicked(index)

    def _on_manga_progress_changed(self, chapter_id: str, page: int) -> None:
        if not self._current_manga or not self._manga_chapters:
            return
        idx = self._current_manga_chapter_index
        chapter_label = ""
        if 0 <= idx < len(self._manga_chapters):
            chapter_label = self._manga_chapters[idx].get("label", "")
        mid = self._current_manga.get("id", "")
        title = self._current_manga.get("title", "")
        cover = self._manga_cover_cache.get(mid)
        try:
            self._manga_history_service.save_entry(
                manga_id=mid,
                manga_title=title,
                chapter_id=chapter_id,
                chapter_label=chapter_label,
                page=page,
                cover_path=cover,
            )
        except Exception as exc:
            self._append_log(f"Manga: falha ao salvar progresso — {exc}")

    def _on_manga_history_clicked(self, entry: object) -> None:
        if not isinstance(entry, MangaHistoryEntry):
            return
        self._append_log(f"Manga: retomando \"{entry.manga_title}\" — {entry.chapter_label}.")
        # Open detail view without a pre-loaded manga dict, then load chapters
        placeholder = {
            "id": entry.manga_id,
            "title": entry.manga_title,
            "description": "",
            "cover_url": None,
            "status": "",
        }
        if entry.cover_path:
            self._manga_cover_cache[entry.manga_id] = entry.cover_path
        self._on_manga_card_clicked(placeholder)

    def _fetch_manga_cover(self, manga_id: str, cover_url: str, detail_view: bool = False) -> None:
        def task(mid=manga_id, url=cover_url):
            return mid, self._manga_service.download_cover(mid, url)

        worker = FunctionWorker(task)
        self._metadata_workers.add(worker)
        worker.signals.succeeded.connect(
            lambda p, dv=detail_view: self._on_manga_cover_fetched(p, dv)
        )
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _on_manga_cover_fetched(self, payload: object, detail_view: bool) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        mid, path = payload
        if not path or not os.path.exists(str(path)):
            return
        self._manga_cover_cache[mid] = str(path)
        self._manga_home_view.update_card_cover(mid, str(path))
        if detail_view and self._current_manga and self._current_manga.get("id") == mid:
            self._manga_detail_view.set_cover(str(path))

    # ── MANGA DOWNLOADS ──────────────────────────────────────────

    def _on_manga_detail_dl_chapter(self, index: int) -> None:
        if not self._current_manga or not (0 <= index < len(self._manga_chapters)):
            return
        chapter = self._manga_chapters[index]
        self._queue_manga_chapter_download(chapter, index)

    def _on_manga_detail_dl_all(self) -> None:
        if not self._current_manga or not self._manga_chapters:
            return
        for i, chapter in enumerate(self._manga_chapters):
            self._queue_manga_chapter_download(chapter, i)

    def _on_manga_detail_dl_selected(self, indices: list) -> None:
        for idx in indices:
            if self._current_manga and 0 <= idx < len(self._manga_chapters):
                self._queue_manga_chapter_download(self._manga_chapters[idx], idx)

    def _on_manga_reader_dl_chapter(self) -> None:
        idx = self._current_manga_chapter_index
        if not self._current_manga or not (0 <= idx < len(self._manga_chapters)):
            return
        chapter = self._manga_chapters[idx]
        chapter_id = chapter.get("id", "")
        title = self._current_manga.get("title", "")
        label = chapter.get("label", "")
        if self._manga_download_service.is_downloaded(title, label):
            self._manga_reader_view.set_reader_download_state("done")
            return
        if chapter_id in self._active_manga_dl:
            return
        # Need page URLs first
        worker = FunctionWorker(self._manga_service.fetch_chapter_pages, chapter_id)
        self._metadata_workers.add(worker)
        worker.signals.succeeded.connect(
            lambda urls, ch=chapter, i=idx: self._start_manga_download_from_urls(urls, ch, i, from_reader=True)
        )
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _queue_manga_chapter_download(self, chapter: dict, detail_index: int) -> None:
        chapter_id = chapter.get("id", "")
        title = self._current_manga.get("title", "") if self._current_manga else ""
        label = chapter.get("label", "")
        if not chapter_id or not title:
            return
        if self._manga_download_service.is_downloaded(title, label):
            self._manga_detail_view.set_chapter_state(detail_index, "done")
            return
        if chapter_id in self._active_manga_dl:
            return
        self._manga_detail_view.set_chapter_state(detail_index, "downloading", 0, chapter.get("pages", 0) or 1)
        worker = FunctionWorker(self._manga_service.fetch_chapter_pages, chapter_id)
        self._metadata_workers.add(worker)
        worker.signals.succeeded.connect(
            lambda urls, ch=chapter, i=detail_index: self._start_manga_download_from_urls(urls, ch, i)
        )
        worker.signals.failed.connect(
            lambda e, i=detail_index: self._manga_detail_view.set_chapter_state(i, "idle")
        )
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _start_manga_download_from_urls(
        self, urls: object, chapter: dict, detail_index: int, from_reader: bool = False
    ) -> None:
        if not isinstance(urls, list) or not urls:
            if not from_reader:
                self._manga_detail_view.set_chapter_state(detail_index, "idle")
            return
        title = self._current_manga.get("title", "") if self._current_manga else ""
        label = chapter.get("label", "")
        chapter_id = chapter.get("id", "")
        if not title or not chapter_id:
            return

        if from_reader:
            self._manga_reader_view.set_reader_download_state("downloading", 0, len(urls))
        else:
            self._manga_detail_view.set_chapter_state(detail_index, "downloading", 0, len(urls))

        worker = MangaDownloadWorker(
            self._manga_service,
            self._manga_download_service,
            title,
            label,
            urls,
        )
        self._active_manga_dl[chapter_id] = worker

        def _on_progress(done: int, total: int) -> None:
            if from_reader:
                self._manga_reader_view.set_reader_download_state("downloading", done, total)
            else:
                self._manga_detail_view.set_chapter_state(detail_index, "downloading", done, total)

        def _on_success(path: str) -> None:
            self._active_manga_dl.pop(chapter_id, None)
            if from_reader:
                self._manga_reader_view.set_reader_download_state("done")
            else:
                self._manga_detail_view.set_chapter_state(detail_index, "done")
            self._append_log(f"Manga: capítulo baixado — {label}")
            self._refresh_downloads_view()

        def _on_fail(err: str) -> None:
            self._active_manga_dl.pop(chapter_id, None)
            if from_reader:
                self._manga_reader_view.set_reader_download_state("idle")
            else:
                self._manga_detail_view.set_chapter_state(detail_index, "idle")
            self._append_log(f"Manga: falha no download — {label}: {err}")

        worker.signals.progress.connect(_on_progress)
        worker.signals.succeeded.connect(_on_success)
        worker.signals.failed.connect(_on_fail)
        self._thread_pool.start(worker)

    def _on_manga_download_delete(self, entry: object) -> None:
        from animecaos.services.manga_download_service import MangaDownloadEntry
        if not isinstance(entry, MangaDownloadEntry):
            return
        self._manga_download_service.delete(entry)
        self._append_log(f"Manga: download removido — {entry.chapter_label}")
        self._refresh_downloads_view()

    def _on_manga_download_open(self, entry: object) -> None:
        from animecaos.services.manga_download_service import MangaDownloadEntry
        if not isinstance(entry, MangaDownloadEntry):
            return
        self._reader_from_downloads = True
        self._append_log(f"Manga: abrindo local — {entry.manga_title} / {entry.chapter_label}")
        self._set_status(f"Abrindo {entry.chapter_label}…")

        def _load(e=entry):
            return self._manga_download_service.read_pages(e.file_path), e

        worker = FunctionWorker(_load)
        self._metadata_workers.add(worker)
        worker.signals.succeeded.connect(self._on_manga_local_pages_loaded)
        worker.signals.failed.connect(lambda _: self._set_status("Erro ao abrir capítulo."))
        worker.signals.finished.connect(lambda w=worker: self._metadata_workers.discard(w))
        self._thread_pool.start(worker)

    def _on_manga_local_pages_loaded(self, payload: object) -> None:
        if not isinstance(payload, tuple):
            return
        pages, entry = payload
        self._push_nav(_VIEW_MANGA_READER)
        self._stack.slide_to(_VIEW_MANGA_READER)
        self._breadcrumb.setText(f"  >  Downloads  >  {entry.manga_title}")
        self._manga_reader_view.load_local_chapter(
            pages=pages,
            chapter_label=entry.chapter_label,
            manga_title=entry.manga_title,
        )
        self._set_status(f"Lendo {entry.chapter_label} — {len(pages)} páginas")

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
