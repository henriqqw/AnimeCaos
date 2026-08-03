from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication

from animecaos.services.anime_service import AnimeService
from animecaos.services.history_service import HistoryService
from animecaos.services.anilist_service import AniListService
from animecaos.services.anilist_auth_service import AniListAuthService
from animecaos.services.config_service import ConfigService
from animecaos.ui.gui.main_window import MainWindow
from animecaos.ui.gui.views.splash_view import SplashScreen
from animecaos.ui.gui.workers.loader_worker import LoaderWorker
from animecaos.ui.gui.theme import build_stylesheet

if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("animecaos.desktop.app")
    except Exception:
        pass


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

    loader = LoaderWorker(anilist_service, anime_service)
    loader.status_changed.connect(splash.set_status)
    loader.progress_changed.connect(splash.set_progress)

    window_ref: list[MainWindow] = []

    def _on_loaded(data: object) -> None:
        splash.set_status("Pronto!")
        splash.set_progress(1.0)
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

        def _show_and_raise() -> None:
            w.setWindowState(Qt.WindowState.WindowActive)
            w.showNormal()
            w.raise_()
            w.activateWindow()
            if sys.platform == "win32":
                try:
                    import ctypes
                    hwnd = int(w.winId())
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass

        # Exibe a janela principal e garante foco em primeiro plano no Windows
        _show_and_raise()
        splash.finished.connect(splash.close)
        splash.finish()

    loader.load_finished.connect(_on_loaded)
    loader.start()

    result = app.exec()
    from animecaos.plugins.driver_pool import shutdown_driver_pool
    shutdown_driver_pool()
    return result
