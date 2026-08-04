"""
TDD: autoplay must behave like professional streaming apps — advance to the
next episode ONLY when the current one actually reaches its end, never just
because it was open for a while and then closed manually. Before this fix,
play_video() conflated "watched >=30s" with "reached natural EOF" under one
flag, so quitting mid-episode after 30s could incorrectly trigger autoplay.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def window(main_window_factory):
    return main_window_factory()


def _prep(window, fake_anime_service, episode_titles=("Ep1", "Ep2", "Ep3")):
    window._detail_view.set_anime("Some Anime")
    window._current_anime = "Some Anime"
    window._episodes_anime = "Some Anime"
    window._episode_titles = list(episode_titles)


def test_autoplay_advances_on_natural_eof(window, fake_anime_service, qtbot):
    # Only 2 episodes, so a single eof=True keeps the chain to exactly one
    # hop (ep0 -> ep1) instead of racing through the whole season, which
    # would make the intermediate index=1 state impossible to observe.
    _prep(window, fake_anime_service, episode_titles=("Ep1", "Ep2"))
    fake_anime_service.play_result = {"eof": True, "watched": True}
    assert window._mini_player.is_autoplay() is True

    window._on_episode_play_clicked(0)

    def _advanced_to_ep2():
        assert window._busy is False
        assert window._current_episode_index == 1

    qtbot.waitUntil(_advanced_to_ep2, timeout=3000)


def test_autoplay_does_not_advance_on_manual_quit_after_30s(window, fake_anime_service, qtbot):
    _prep(window, fake_anime_service)
    # Watched long enough for AniList sync, but the user closed the player
    # manually rather than letting it finish — must NOT autoplay.
    fake_anime_service.play_result = {"eof": False, "watched": True}
    assert window._mini_player.is_autoplay() is True

    window._on_episode_play_clicked(0)

    def _first_play_done():
        assert window._busy is False
        assert window._current_episode_index == 0

    qtbot.waitUntil(_first_play_done, timeout=3000)
    qtbot.wait(200)  # give any (incorrect) autoplay timer a chance to fire
    assert window._current_episode_index == 0


def test_autoplay_does_not_advance_when_toggle_is_off(window, fake_anime_service, qtbot):
    _prep(window, fake_anime_service)
    fake_anime_service.play_result = {"eof": True, "watched": True}
    window._mini_player.autoplay_checkbox.setChecked(False)
    assert window._mini_player.is_autoplay() is False

    window._on_episode_play_clicked(0)

    def _first_play_done():
        assert window._busy is False
        assert window._current_episode_index == 0

    qtbot.waitUntil(_first_play_done, timeout=3000)
    qtbot.wait(200)
    assert window._current_episode_index == 0


def test_autoplay_stops_after_the_last_episode(window, fake_anime_service, qtbot):
    _prep(window, fake_anime_service, episode_titles=("Ep1",))
    fake_anime_service.play_result = {"eof": True, "watched": True}

    window._on_episode_play_clicked(0)

    def _first_play_done():
        assert window._busy is False
        assert window._current_episode_index == 0

    qtbot.waitUntil(_first_play_done, timeout=3000)
    qtbot.wait(200)
    assert window._current_episode_index == 0
