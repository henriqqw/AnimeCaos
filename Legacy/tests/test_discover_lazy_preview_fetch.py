"""
TDD: loading the home discover sections (trending + seasonal, up to ~50
cards) used to eagerly fire one fetch_anime_info() call per card just to
get a synopsis for the hover preview — enough of a burst to trip AniList's
per-IP rate limit for real users (this app runs on each user's own
machine) and even 429 an unrelated call sharing that budget (login). The
synopsis must only be fetched lazily, one card at a time, as the user
actually hovers it — never eagerly for the whole screen.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def window(main_window_factory, monkeypatch):
    win = main_window_factory()
    monkeypatch.setattr(win._anilist_service, "fetch_anime_info", lambda anime: {})
    return win


def test_loading_discover_cards_does_not_eagerly_fetch_metadata(window):
    trending = [{"title": "One Piece", "cover_path": None, "score": 87, "episodes": 1172}]
    seasonal = [{"title": "Naruto", "cover_path": None, "score": 80, "episodes": 220}]

    window._on_discover_loaded({"trending": trending, "seasonal": seasonal, "spotlights": []})

    assert window._metadata_fetch_started == set()


def test_a_card_reporting_preview_requested_triggers_the_fetch(window):
    window._on_card_preview_requested({"title": "One Piece"})
    assert "One Piece" in window._metadata_fetch_started


def test_hovering_a_discover_card_end_to_end_triggers_exactly_one_fetch(window):
    trending = [{"title": "One Piece", "cover_path": None, "score": 87, "episodes": 1172}]
    window._on_discover_loaded({"trending": trending, "seasonal": [], "spotlights": []})

    card = window._home_view.trending_section._cards[0]
    card.preview_requested.emit(card.data)

    assert "One Piece" in window._metadata_fetch_started
