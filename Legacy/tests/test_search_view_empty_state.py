"""
TDD: searching for an anime with no results used to just say "Nenhum
resultado / Tente outro termo de busca" — a dead end. It should now point
the user at the social channels to request the anime, with clickable
Instagram/X buttons pointing at the right profiles.
"""
from __future__ import annotations

from animecaos.ui.gui.views.search_view import INSTAGRAM_URL, X_URL, SearchView


def test_empty_state_has_instagram_and_x_buttons_with_correct_urls(qtbot):
    view = SearchView()
    qtbot.addWidget(view)

    buttons = view._empty_state._social_buttons
    urls = {btn.text(): btn._url for btn in buttons}

    assert urls == {"Instagram": INSTAGRAM_URL, "X": X_URL}


def test_empty_state_shows_after_a_search_with_no_results(qtbot):
    view = SearchView()
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view)

    view.set_results([], query="anime que nao existe")

    assert view._empty_state.isVisible() is True
