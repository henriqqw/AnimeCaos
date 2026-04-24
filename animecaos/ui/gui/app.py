from __future__ import annotations

import logging
import re
import sys
import threading

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication

from animecaos.services.anime_service import AnimeService
from animecaos.services.history_service import HistoryService
from animecaos.services.anilist_service import AniListService
from animecaos.services.anilist_auth_service import AniListAuthService
from animecaos.services.config_service import ConfigService
from .main_window import MainWindow
from .splash import SplashScreen
from .theme import build_stylesheet

if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("animecaos.desktop.app")
    except Exception:
        pass


class _Loader(QObject):
    """Runs AniList + spotlight loading in a background thread, emits progress signals."""
    status_changed = Signal(str)
    progress_changed = Signal(float)
    load_finished = Signal(object)  # emits dict with preloaded data

    def __init__(self, anilist_service: AniListService, anime_service: AnimeService) -> None:
        super().__init__()
        self._anilist = anilist_service
        self._anime = anime_service

    def start(self) -> None:
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self) -> None:
        try:
            # Step 1: ensure scraper plugins loaded
            self.status_changed.emit("Inicializando plugins...")
            self.progress_changed.emit(0.05)
            self._anime.ensure_plugins_loaded()

            # Step 2: fetch trending
            self.status_changed.emit("Conectando ao AniList...")
            self.progress_changed.emit(0.15)
            trending = self._anilist.fetch_trending(per_page=25)
            self.status_changed.emit(f"Em Alta: {len(trending)} animes carregados")
            self.progress_changed.emit(0.40)

            # Step 3: fetch seasonal
            self.status_changed.emit("Carregando temporada atual...")
            seasonal = self._anilist.fetch_seasonal(per_page=25)
            self.status_changed.emit(f"Temporada: {len(seasonal)} animes carregados")
            self.progress_changed.emit(0.60)

            # Step 4: find spotlight candidate (check up to 6 trending)
            self.status_changed.emit("Selecionando destaque da temporada...")
            spotlight = None
            for i, candidate in enumerate(trending[:6]):
                title = candidate.get("title", "")
                base = re.split(r":\s+", title, maxsplit=1)[0].strip()
                if base == base.upper() and len(base) > 1:
                    base = base.title()
                self.status_changed.emit(f"Verificando: {title[:40]}...")
                try:
                    found = bool(base and len(base) >= 3 and self._anime.search_animes(base))
                    if not found:
                        variants = self._anilist.get_title_variants(title)
                        for v in variants:
                            if v and self._anime.search_animes(v):
                                found = True
                                break
                except Exception:
                    found = False
                if found:
                    self.status_changed.emit(f"Destaque: {title[:40]}")
                    self.progress_changed.emit(0.75)
                    spotlight = self._anilist.fetch_spotlight_extras(candidate)
                    spotlight["_rank"] = i + 1
                    break
                self.progress_changed.emit(0.60 + (i + 1) * 0.02)

            # Step 5: wrap up
            self.status_changed.emit("Preparando interface...")
            self.progress_changed.emit(0.95)

            self.load_finished.emit({
                "trending": trending,
                "seasonal": seasonal,
                "spotlight": spotlight,
            })
        except Exception as exc:
            # Even on error, proceed so the user can still use the app
            self.status_changed.emit("Pronto!")
            self.load_finished.emit({
                "trending": [],
                "seasonal": [],
                "spotlight": None,
                "_error": str(exc),
            })


def run_gui(debug: bool = False) -> int:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())

    # Build services
    anime_service = AnimeService(debug=debug)
    history_service = HistoryService()
    anilist_service = AniListService()
    config_service = ConfigService()
    anilist_auth_service = AniListAuthService(config_service)

    splash = SplashScreen()
    splash.start()

    loader = _Loader(anilist_service, anime_service)
    loader.status_changed.connect(splash.set_status)
    loader.progress_changed.connect(splash.set_progress)

    window_ref: list[MainWindow] = []

    def _on_loaded(data: object) -> None:
        splash.set_status("Pronto!")
        splash.set_progress(1.0)
        # Small delay so user sees 100% before fade
        QTimer.singleShot(300, lambda: _show_main(data))

    def _show_main(data: object) -> None:
        w = MainWindow(
            anime_service=anime_service,
            history_service=history_service,
            anilist_service=anilist_service,
            config_service=config_service,
            anilist_auth_service=anilist_auth_service,
            preloaded_discover=data if isinstance(data, dict) else None,
        )
        window_ref.append(w)
        splash.finished.connect(w.show)
        splash.finish()

    loader.load_finished.connect(_on_loaded)
    loader.start()

    result = app.exec()
    from animecaos.plugins.utils import shutdown_driver_pool
    shutdown_driver_pool()
    return result
