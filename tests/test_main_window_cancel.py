"""
Fase 3 (TDD): clicking "Cancelar" (play or download, while resolving the
player URL) must reset the UI immediately AND make sure the orphaned
background task's eventual result (success or failure, arriving after the
user already cancelled) is ignored — it must not silently reopen an overlay,
re-populate the mini player, or start a download the user already backed out
of. Today _on_download_cancel() only flips _busy/_download_cancelled and
_on_play_cancel doesn't even exist (PlayOverlay had no cancel button) — the
background FunctionWorker keeps running and its result is applied blindly
whenever it eventually arrives.
"""
from __future__ import annotations

import threading

import pytest


@pytest.fixture
def window(main_window_factory):
    return main_window_factory()


def test_cancel_during_play_resolve_resets_busy_immediately(window, fake_anime_service, qtbot):
    release = threading.Event()
    fake_anime_service.resolve_delay_event = release
    try:
        window._detail_view.set_anime("Some Anime")
        window._current_anime = "Some Anime"

        window._on_episode_play_clicked(0)
        assert window._busy is True
        assert window._play_overlay.isVisible()

        window._on_play_cancel()

        assert window._busy is False
        assert window._play_overlay.isVisible() is False
    finally:
        release.set()  # let the orphaned background thread finish so it doesn't leak


def test_late_result_after_play_cancel_does_not_reopen_overlay_or_start_mini_player(
    window, fake_anime_service, qtbot
):
    release = threading.Event()
    fake_anime_service.resolve_delay_event = release
    try:
        window._detail_view.set_anime("Some Anime")
        window._current_anime = "Some Anime"

        window._on_episode_play_clicked(0)
        window._on_play_cancel()

        assert window._mini_player.isVisible() is False

        # The orphaned worker thread now "finishes" resolving — simulate the late arrival.
        release.set()

        def _worker_gone():
            assert len(window._active_workers) == 0

        qtbot.waitUntil(_worker_gone, timeout=3000)

        # A stale success must not reopen the play overlay or populate the mini player.
        assert window._play_overlay.isVisible() is False
        assert window._mini_player.isVisible() is False
    finally:
        release.set()


def test_cancel_during_download_resolve_resets_busy_immediately(window, fake_anime_service, qtbot):
    release = threading.Event()
    fake_anime_service.resolve_delay_event = release
    try:
        window._detail_view.set_anime("Some Anime")
        window._current_anime = "Some Anime"

        window._on_episode_download_clicked(0)
        assert window._busy is True
        assert window._download_overlay.isVisible()

        window._on_download_cancel()

        assert window._busy is False
        assert window._download_overlay.isVisible() is False
        assert window._active_download_worker is None
    finally:
        release.set()
