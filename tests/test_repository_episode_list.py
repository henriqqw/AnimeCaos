"""
TDD: an anime whose title matches across two scraper sources — e.g. AnimeFire
lists "One Piece" continuously from episode 1 to 1172, while AnimesOnlineCC
only has a partial/season-split catalog under the same normalized title
("One Piece" season 1 = 43 episodes) — was showing far too few episodes.

Repository.get_episode_list() picked the SHORTEST episode list among all
sources that registered one for that anime key. The comment said this was to
dodge a source padding a couple of bonus OVAs onto the end of an otherwise
correct list, but the heuristic silently threw away hundreds of real
episodes whenever a second source's catalog for "the same" title was much
smaller (different season-splitting, a stale/partial scrape, etc). Losing a
handful of possible OVA rows is a far smaller problem than losing 1129 real
episodes, so the fix must prefer the longest list instead — every episode a
source actually has must be listed.
"""
from __future__ import annotations

import pytest

from animecaos.core.repository import rep


@pytest.fixture(autouse=True)
def _clean_repository():
    rep.reset_runtime_data()
    yield
    rep.reset_runtime_data()


def test_get_episode_list_prefers_the_longest_list_across_sources():
    rep.add_episode_list(
        "One Piece",
        [f"Ep {i}" for i in range(1, 44)],
        [f"u{i}" for i in range(1, 44)],
        "animesonlinecc",
    )
    rep.add_episode_list(
        "One Piece",
        [f"Ep {i}" for i in range(1, 1173)],
        [f"u{i}" for i in range(1, 1173)],
        "animefire",
    )

    result = rep.get_episode_list("One Piece")

    assert len(result) == 1172
    assert result[-1] == "Ep 1172"


def test_get_episode_list_prefers_the_longest_regardless_of_registration_order():
    rep.add_episode_list(
        "Naruto",
        [f"Ep {i}" for i in range(1, 501)],
        [f"u{i}" for i in range(1, 501)],
        "animefire",
    )
    rep.add_episode_list(
        "Naruto",
        [f"Ep {i}" for i in range(1, 21)],
        [f"u{i}" for i in range(1, 21)],
        "animesonlinecc",
    )

    result = rep.get_episode_list("Naruto")

    assert len(result) == 500


def test_get_episode_list_returns_empty_for_unknown_anime():
    assert rep.get_episode_list("Anime Inexistente") == []


def test_get_episode_list_ignores_empty_lists_from_a_failed_source():
    rep.anime_episodes_titles["Bleach"].append([])
    rep.add_episode_list(
        "Bleach",
        [f"Ep {i}" for i in range(1, 11)],
        [f"u{i}" for i in range(1, 11)],
        "animefire",
    )

    result = rep.get_episode_list("Bleach")

    assert len(result) == 10
