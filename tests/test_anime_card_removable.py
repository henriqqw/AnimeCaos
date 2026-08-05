"""
TDD: the new "Minha Lista" (watchlist) page needs a way for the user to
remove an anime directly from its card, without entering the detail page.
AnimeCard gains an opt-in `removable` flag that overlays a small remove
button on the cover and emits `remove_clicked` with the card's data —
default behavior (search results, discover sections) is untouched.
"""
from __future__ import annotations

from animecaos.ui.gui.widgets.anime_card import AnimeCard


def test_card_is_not_removable_by_default(qtbot):
    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)
    assert card._remove_btn is None


def test_removable_card_shows_a_remove_button(qtbot):
    card = AnimeCard({"title": "One Piece"}, removable=True)
    qtbot.addWidget(card)
    assert card._remove_btn is not None
    assert card._remove_btn.isVisible() or not card._remove_btn.isHidden()


def test_clicking_remove_button_emits_remove_clicked_with_card_data(qtbot):
    card = AnimeCard({"title": "One Piece"}, removable=True)
    qtbot.addWidget(card)

    with qtbot.waitSignal(card.remove_clicked, timeout=1000) as blocker:
        card._remove_btn.click()

    assert blocker.args == [{"title": "One Piece"}]


def test_clicking_remove_button_does_not_also_trigger_card_clicked(qtbot):
    card = AnimeCard({"title": "One Piece"}, removable=True)
    qtbot.addWidget(card)

    clicked_calls = []
    card.clicked.connect(lambda d: clicked_calls.append(d))

    with qtbot.waitSignal(card.remove_clicked, timeout=1000):
        card._remove_btn.click()

    assert clicked_calls == []
