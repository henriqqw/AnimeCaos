from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


@pytest.fixture(scope="session")
def qapp_instance():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


class FakeAnimeService:
    """Stand-in for AnimeService — no network, no locks, fully scriptable."""

    def __init__(self) -> None:
        self.search_calls: list[str] = []
        self.resolve_calls: list[tuple[str, int]] = []
        self.search_result: list[str] = []
        self.search_exception: Exception | None = None
        self.resolve_result: str = "https://example.com/video.mp4"
        self.resolve_exception: Exception | None = None
        self.resolve_delay_event = None  # optional threading.Event to block resolve_player_url
        self.play_result: dict[str, bool] = {"eof": False, "watched": False}
        self.episode_sources_result: list[tuple[list[str], str]] = []

    def search_animes(self, query: str) -> list[str]:
        self.search_calls.append(query)
        if self.search_exception is not None:
            raise self.search_exception
        return self.search_result

    def resolve_player_url(self, anime: str, episode_index: int) -> str:
        self.resolve_calls.append((anime, episode_index))
        if self.resolve_delay_event is not None:
            # Bounded even if a test forgets to .set() it — a test bug should
            # fail fast, not leak a thread that blocks forever on the shared
            # global QThreadPool for the rest of the test run.
            self.resolve_delay_event.wait(timeout=5)
        if self.resolve_exception is not None:
            raise self.resolve_exception
        return self.resolve_result

    def fetch_episode_titles(self, anime: str) -> list[str]:
        return []

    def get_episode_sources(self, anime: str) -> list[tuple[list[str], str]]:
        return self.episode_sources_result

    def play_url(self, url: str) -> dict[str, bool]:
        return self.play_result


class FakeHistoryService:
    def load_entries(self):
        return []


@pytest.fixture
def fake_anime_service() -> FakeAnimeService:
    return FakeAnimeService()


@pytest.fixture
def main_window_factory(qapp_instance, monkeypatch, fake_anime_service, tmp_path):
    """Builds a real MainWindow with network/IPC side effects neutralized.

    Startup routines that are unrelated to the logic under test (update
    checks, Discord RPC) are stubbed so construction is fast, deterministic,
    and offline. AniListService/AniListAuthService are used for real since
    their constructors only touch a local cache dir/config file — no network
    — which avoids having to hand-maintain a fake covering their full
    attribute surface. preloaded_discover={} skips their one network-calling
    method (fetch_trending/fetch_seasonal) entirely. Everything relevant to
    the bugs under test (search, play, download, cancel, overlays) runs the
    real production code against the scriptable fake_anime_service.
    """
    from animecaos.services.anilist_service import AniListService
    from animecaos.services.anilist_auth_service import AniListAuthService
    from animecaos.services.config_service import ConfigService
    from animecaos.ui.gui import main_window as main_window_module

    monkeypatch.setattr(main_window_module.MainWindow, "_check_for_updates", lambda self: None)
    monkeypatch.setattr(main_window_module.DiscordService, "connect", lambda self: None)

    config_service = ConfigService(app_name=f"animecaos-test-{tmp_path.name}")

    created: list = []

    def _build(anime_service=None):
        window = main_window_module.MainWindow(
            anime_service=anime_service or fake_anime_service,
            history_service=FakeHistoryService(),
            anilist_service=AniListService(app_name=f"animecaos-test-{tmp_path.name}"),
            config_service=config_service,
            anilist_auth_service=AniListAuthService(config_service),
            preloaded_discover={},
        )
        created.append(window)
        window.show()
        return window

    yield _build

    for window in created:
        window.close()
        window.deleteLater()
