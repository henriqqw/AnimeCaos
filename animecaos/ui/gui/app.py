from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from animecaos.services.anime_service import AnimeService
from animecaos.services.history_service import HistoryService
from animecaos.services.anilist_service import AniListService
from animecaos.services.anilist_auth_service import AniListAuthService
from animecaos.services.config_service import ConfigService
from .main_window import MainWindow
from .splash import SplashScreen
from .theme import build_stylesheet

# Correcao para o icone da barra de tarefas no Windows
if sys.platform == "win32":
    import ctypes
    try:
        myappid = "animecaos.desktop.app"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
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

    splash = SplashScreen()
    splash.start()

    # Build services while splash is showing
    anime_service = AnimeService(debug=debug)
    history_service = HistoryService()
    anilist_service = AniListService()
    config_service = ConfigService()
    anilist_auth_service = AniListAuthService(config_service)

    window: MainWindow | None = None

    def _show_main() -> None:
        nonlocal window
        window = MainWindow(
            anime_service=anime_service,
            history_service=history_service,
            anilist_service=anilist_service,
            config_service=config_service,
            anilist_auth_service=anilist_auth_service,
        )
        window.show()

    splash.finished.connect(_show_main)

    # Let the splash animate for a minimum time, then fade out
    QTimer.singleShot(2500, splash.finish)

    result = app.exec()
    from animecaos.plugins.utils import shutdown_driver_pool
    shutdown_driver_pool()
    return result
