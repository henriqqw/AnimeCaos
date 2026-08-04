"""
TDD: the hero carousel needs up to 5 spotlight candidates, not just 1.
MainWindow._collect_spotlights() scans the top of `trending`, keeps the
first N the scraper actually has, fetches each one's extras (banner/
description) in parallel, and returns them still ordered by their original
trending rank (not network-completion order, which would be nondeterministic).
"""
from __future__ import annotations

import pytest


@pytest.fixture
def window(main_window_factory):
    return main_window_factory()


def _trending(n: int) -> list[dict]:
    return [{"title": f"Anime {i}"} for i in range(n)]


def test_collects_up_to_five_available_candidates_in_trending_order(
    window, fake_anime_service, monkeypatch
):
    fake_anime_service.search_result = ["match"]  # every candidate "available"
    monkeypatch.setattr(
        window._anilist_service,
        "fetch_spotlight_extras",
        lambda card: {**card, "banner_path": f"/b/{card['title']}.jpg"},
    )

    spotlights = window._collect_spotlights(_trending(8))

    assert len(spotlights) == 5
    assert [s["title"] for s in spotlights] == [f"Anime {i}" for i in range(5)]
    assert [s["_rank"] for s in spotlights] == [1, 2, 3, 4, 5]
    assert all(s["banner_path"] for s in spotlights)


def test_skips_unavailable_candidates_but_keeps_trending_order(
    window, fake_anime_service, monkeypatch
):
    available_titles = {"Anime 1", "Anime 3", "Anime 4"}

    def fake_search(query):
        return ["match"] if query in available_titles else []

    fake_anime_service.search_animes = fake_search
    monkeypatch.setattr(window._anilist_service, "fetch_spotlight_extras", lambda card: dict(card))
    # Unavailable candidates fall back to AniList title-variant lookup before
    # giving up — stub it so the test doesn't make a real network call.
    monkeypatch.setattr(window._anilist_service, "get_title_variants", lambda title: [])

    spotlights = window._collect_spotlights(_trending(5))

    assert [s["title"] for s in spotlights] == ["Anime 1", "Anime 3", "Anime 4"]
    assert [s["_rank"] for s in spotlights] == [2, 4, 5]


def test_no_available_candidates_returns_empty_list(window, fake_anime_service, monkeypatch):
    fake_anime_service.search_result = []
    monkeypatch.setattr(window._anilist_service, "fetch_spotlight_extras", lambda card: dict(card))
    monkeypatch.setattr(window._anilist_service, "get_title_variants", lambda title: [])

    spotlights = window._collect_spotlights(_trending(5))

    assert spotlights == []


def test_a_candidate_whose_extras_fetch_fails_is_dropped_not_crashed(
    window, fake_anime_service, monkeypatch
):
    fake_anime_service.search_result = ["match"]

    def flaky_extras(card):
        if card["title"] == "Anime 1":
            raise RuntimeError("AniList timeout")
        return dict(card)

    monkeypatch.setattr(window._anilist_service, "fetch_spotlight_extras", flaky_extras)

    spotlights = window._collect_spotlights(_trending(3))

    assert [s["title"] for s in spotlights] == ["Anime 0", "Anime 2"]
