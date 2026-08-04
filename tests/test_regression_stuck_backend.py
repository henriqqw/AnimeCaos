"""
Fase 6 (TDD): end-to-end regression test reproducing the exact production
symptom — reported live in the terminal as:

    urllib3.connectionpool: Retrying ... after connection broken by
    ReadTimeoutError(... animesonlinecc.to ... Read timed out ...)

and visually as a play/download overlay stuck on "Aguarde, carregando
stream..." that never goes away, even across navigation, with the app unable
to play or download anything afterwards without a full restart.

Unlike the other test files (which use FakeAnimeService and unit-test one
layer at a time), this test wires the REAL AnimeService — with its real
_rep_lock — into a real MainWindow, and simulates another in-flight
operation (standing in for a hung Selenium page load against the target
site) already holding that lock when the user clicks Play. It asserts the
whole stack recovers on its own, with no restart required.
"""
from __future__ import annotations

import threading
import time

import pytest

from animecaos.core.repository import rep
from animecaos.services.anime_service import AnimeService


@pytest.fixture
def real_anime_service(monkeypatch):
    svc = AnimeService(debug=True, rep_lock_timeout=0.5)
    svc._plugins_loaded = True
    monkeypatch.setattr(rep, "anime_episodes_urls", {"One Piece": [(["https://x/1"], "animesonlinecc")]})
    monkeypatch.setattr(rep, "search_player", lambda anime, ep: "https://example.com/video.mp4")
    # play_url() would otherwise try to launch a real media player process.
    monkeypatch.setattr(
        "animecaos.services.anime_service.play_video",
        lambda url, debug=False: {"eof": False},
    )
    return svc


def test_app_recovers_after_a_stuck_backend_call_without_restart(
    main_window_factory, real_anime_service, qtbot, monkeypatch
):
    from animecaos.ui.gui import main_window as main_window_module

    # _on_task_failed() shows a real modal QMessageBox on error — stub it so
    # the test doesn't block on a dialog nobody can click.
    monkeypatch.setattr(main_window_module.QMessageBox, "critical", lambda *a, **k: None)

    window = main_window_factory(anime_service=real_anime_service)
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"

    # Simulate the exact production symptom: some other in-flight operation
    # (e.g. a hung Selenium page load against animesonlinecc.to) is already
    # holding AnimeService's shared rep lock when the user clicks Play.
    stuck_release = threading.Event()

    def _hold_lock():
        with real_anime_service._rep_lock:
            stuck_release.wait(timeout=5)

    holder = threading.Thread(target=_hold_lock, daemon=True)
    holder.start()
    while not real_anime_service._rep_lock.locked():
        time.sleep(0.005)

    try:
        started = time.monotonic()
        window._on_episode_play_clicked(0)

        def _first_attempt_done():
            assert window._busy is False
            # dismiss() fades out over ~200ms — give it time to actually hide.
            assert window._play_overlay.isVisible() is False

        qtbot.waitUntil(_first_attempt_done, timeout=3000)
        elapsed = time.monotonic() - started

        assert elapsed < 2.0, (
            f"first play attempt took {elapsed:.2f}s to fail — it must fail fast "
            "(bounded by rep_lock_timeout), not hang the whole app"
        )
    finally:
        stuck_release.set()
        holder.join(timeout=2)

    # THE regression this whole plan exists to fix: after the stuck operation
    # clears, Play must work again immediately — no restart, no leftover lock
    # or busy state from the failed attempt.
    window._on_episode_play_clicked(0)

    def _second_attempt_done():
        assert window._busy is False
        assert window._mini_player.isVisible() is True

    qtbot.waitUntil(_second_attempt_done, timeout=3000)
    assert window._play_overlay.isVisible() is False
    assert window._current_episode_index == 0
