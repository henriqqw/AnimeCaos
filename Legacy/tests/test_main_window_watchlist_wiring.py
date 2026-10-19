"""
TDD: wiring for the new "Minha Lista" page. WatchlistService already existed
(persistence-only, title strings) but was never connected to the UI. This
covers: opening the detail page reflects whether the anime is already saved,
toggling the list button there persists through WatchlistService, the list
page renders from WatchlistService on navigation, and removing a card there
also persists and refreshes the grid.

fetch_anime_info is stubbed on every test (as test_spotlight_collection.py
already does elsewhere) so navigating never fires a real AniList network
call from the background metadata-fetch workers.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def window(main_window_factory, monkeypatch):
    win = main_window_factory()
    monkeypatch.setattr(win._anilist_service, "fetch_anime_info", lambda anime: {})
    return win


def test_opening_detail_view_reflects_existing_watchlist_state(window):
    window._watchlist_service.add_anime("One Piece")

    window._navigate_to_detail("One Piece")

    assert window._detail_view.in_list is True


def test_opening_detail_view_for_anime_not_in_list_shows_add_state(window):
    window._navigate_to_detail("Not Saved Anime")
    assert window._detail_view.in_list is False


def test_toggling_add_in_detail_view_persists_to_watchlist_service(window):
    window._navigate_to_detail("One Piece")
    assert window._detail_view.in_list is False

    window._on_detail_list_toggle_clicked()

    assert window._detail_view.in_list is True
    assert window._watchlist_service.is_favorited("One Piece") is True


def test_toggling_remove_in_detail_view_persists_to_watchlist_service(window):
    window._watchlist_service.add_anime("One Piece")
    window._navigate_to_detail("One Piece")
    assert window._detail_view.in_list is True

    window._on_detail_list_toggle_clicked()

    assert window._detail_view.in_list is False
    assert window._watchlist_service.is_favorited("One Piece") is False


def test_navigating_to_list_shows_watchlist_entries(window):
    window._watchlist_service.add_anime("One Piece")
    window._watchlist_service.add_anime("Naruto")
    window._cover_cache["One Piece"] = "irrelevant.jpg"
    window._cover_cache["Naruto"] = "irrelevant.jpg"

    window._navigate_to_list()

    titles = {c.data["title"] for c in window._list_view._cards}
    assert titles == {"One Piece", "Naruto"}


def test_removing_from_list_view_persists_and_refreshes_grid(window):
    window._watchlist_service.add_anime("One Piece")
    window._cover_cache["One Piece"] = "irrelevant.jpg"
    window._navigate_to_list()

    window._on_list_remove_clicked("One Piece")

    assert window._watchlist_service.is_favorited("One Piece") is False
    assert window._list_view._cards == []


def test_removing_currently_open_detail_anime_from_list_updates_its_button(window):
    window._watchlist_service.add_anime("One Piece")
    window._navigate_to_detail("One Piece")
    assert window._detail_view.in_list is True

    window._on_list_remove_clicked("One Piece")

    assert window._detail_view.in_list is False


# ── Card hover-preview bookmark toggle (Home / Search) ─────────────────


def test_search_results_carry_the_current_watchlist_state(window):
    window._watchlist_service.add_anime("One Piece")
    window._last_search_query = "one piece"

    window._on_search_finished(["One Piece", "Naruto"])

    cards = {c.data["title"]: c.data["in_list"] for c in window._search_view._cards}
    assert cards == {"One Piece": True, "Naruto": False}


def test_toggling_list_from_a_card_persists_and_updates_its_own_flag(window):
    window._last_search_query = "one piece"
    window._on_search_finished(["One Piece"])
    card = window._search_view._cards[0]
    assert card.data["in_list"] is False

    window._on_card_list_toggle(card.data)

    assert window._watchlist_service.is_favorited("One Piece") is True
    assert card.data["in_list"] is True


def test_toggling_list_off_from_a_card_persists_removal(window):
    window._watchlist_service.add_anime("One Piece")
    window._last_search_query = "one piece"
    window._on_search_finished(["One Piece"])
    card = window._search_view._cards[0]
    assert card.data["in_list"] is True

    window._on_card_list_toggle(card.data)

    assert window._watchlist_service.is_favorited("One Piece") is False
    assert card.data["in_list"] is False


def test_toggling_list_from_a_search_card_updates_detail_view_if_open(window):
    window._navigate_to_detail("One Piece")
    assert window._detail_view.in_list is False
    window._last_search_query = "one piece"
    window._on_search_finished(["One Piece"])
    card = window._search_view._cards[0]

    window._on_card_list_toggle(card.data)

    assert window._detail_view.in_list is True


def test_discover_cards_carry_the_current_watchlist_state(window):
    window._watchlist_service.add_anime("One Piece")
    trending = [{"title": "One Piece", "cover_path": None, "score": 87, "episodes": 1172}]
    seasonal = [{"title": "Naruto", "cover_path": None, "score": 80, "episodes": 220}]

    window._on_discover_loaded({"trending": trending, "seasonal": seasonal, "spotlights": []})

    trending_card = window._home_view.trending_section._cards[0]
    seasonal_card = window._home_view.seasonal_section._cards[0]
    assert trending_card.data["in_list"] is True
    assert seasonal_card.data["in_list"] is False
