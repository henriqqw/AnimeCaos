"""
TDD: new "Minha Lista" page — a grid of the user's saved animes (like
Crunchyroll/Netflix's My List), where the user can click a card to open its
detail page or remove it directly from the grid.
"""
from __future__ import annotations

from animecaos.ui.gui.views.list_view import ListView


def test_empty_list_shows_empty_state(qtbot):
    view = ListView()
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view)
    assert view._empty_state.isVisible() is True
    assert view._grid_container.isVisible() is False


def test_set_animes_renders_a_card_per_item_and_hides_empty_state(qtbot):
    view = ListView()
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view)

    view.set_animes([{"title": "One Piece"}, {"title": "Naruto"}])

    assert len(view._cards) == 2
    assert view._empty_state.isVisible() is False
    assert view._grid_container.isVisible() is True


def test_cards_in_list_view_are_removable(qtbot):
    view = ListView()
    qtbot.addWidget(view)
    view.set_animes([{"title": "One Piece"}])
    assert view._cards[0].removable is True


def test_clicking_a_card_emits_anime_clicked_with_its_data(qtbot):
    view = ListView()
    qtbot.addWidget(view)
    view.set_animes([{"title": "One Piece"}])

    with qtbot.waitSignal(view.anime_clicked, timeout=1000) as blocker:
        view._cards[0].clicked.emit(view._cards[0].data)

    assert blocker.args[0]["title"] == "One Piece"


def test_removing_a_card_emits_remove_clicked_with_the_title(qtbot):
    view = ListView()
    qtbot.addWidget(view)
    view.set_animes([{"title": "One Piece"}])

    with qtbot.waitSignal(view.remove_clicked, timeout=1000) as blocker:
        view._cards[0]._remove_btn.click()

    assert blocker.args == ["One Piece"]


def test_set_animes_again_replaces_previous_cards(qtbot):
    view = ListView()
    qtbot.addWidget(view)
    view.set_animes([{"title": "One Piece"}, {"title": "Naruto"}])
    view.set_animes([{"title": "Bleach"}])

    assert len(view._cards) == 1
    assert view._cards[0].data["title"] == "Bleach"


def test_set_animes_empty_after_having_items_shows_empty_state_again(qtbot):
    view = ListView()
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view)
    view.set_animes([{"title": "One Piece"}])
    view.set_animes([])

    assert view._empty_state.isVisible() is True
    assert view._cards == []


def test_every_card_here_starts_marked_as_in_list(qtbot):
    view = ListView()
    qtbot.addWidget(view)
    view.set_animes([{"title": "One Piece"}])
    assert view._cards[0].data["in_list"] is True


def test_toggling_the_bookmark_button_routes_to_remove_clicked(qtbot):
    # Every card here is already in the watchlist by definition, so the
    # hover panel's bookmark toggle must mean the same thing as the X button.
    view = ListView()
    qtbot.addWidget(view)
    view.set_animes([{"title": "One Piece"}])

    with qtbot.waitSignal(view.remove_clicked, timeout=1000) as blocker:
        view._cards[0]._preview_list_btn.click()

    assert blocker.args == ["One Piece"]


def test_update_card_preview_applies_to_the_matching_card(qtbot):
    view = ListView()
    qtbot.addWidget(view)
    view.set_animes([{"title": "One Piece"}])

    view.update_card_preview("One Piece", score=91, episodes=1172, description="Uma aventura pirata.")

    card = view._cards[0]
    assert card.data["score"] == 91
    assert card.data["episodes"] == 1172
    assert card._preview_synopsis.text() == "Uma aventura pirata."


def test_update_cover_applies_to_the_matching_card(qtbot, tmp_path):
    from PySide6.QtGui import QPixmap

    cover_path = tmp_path / "cover.png"
    QPixmap(10, 10).save(str(cover_path))

    view = ListView()
    qtbot.addWidget(view)
    view.set_animes([{"title": "One Piece"}])

    view.update_cover("One Piece", str(cover_path))

    assert not view._cards[0].cover_label.pixmap().isNull()
