"""
TDD: hovering an anime cover on Home or Search should expand into a
Crunchyroll-style preview panel — rating, "1 Temporada" (every entry in this
app's data model already represents a single season), episode count,
synopsis, and Play/Adicionar-à-Lista buttons. Fields with no real data
source (Crunchyroll's detailed age rating, review count) are simply omitted
rather than fabricated.
"""
from __future__ import annotations

from animecaos.ui.gui.widgets.anime_card import AnimeCard


def test_preview_panel_is_hidden_by_default(qtbot):
    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)
    assert card._preview_panel.isVisible() is False


def test_first_hover_requests_preview_data_when_description_is_unknown(qtbot):
    # A discover row can hold ~50 cards — fetching every card's synopsis up
    # front (rather than lazily, on hover) is what tripped AniList's rate
    # limit for real users. Must only ever fetch on-demand.
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QEnterEvent

    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)

    with qtbot.waitSignal(card.preview_requested, timeout=1000) as blocker:
        card.enterEvent(QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(0, 0)))

    assert blocker.args == [{"title": "One Piece"}]


def test_second_hover_does_not_request_preview_data_again(qtbot):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QEnterEvent

    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)

    requests_seen = []
    card.preview_requested.connect(lambda d: requests_seen.append(d))

    card.enterEvent(QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(0, 0)))
    card.leaveEvent(QEvent(QEvent.Type.Leave))
    card.enterEvent(QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(0, 0)))

    assert len(requests_seen) == 1


def test_hovering_does_not_request_preview_data_when_already_known(qtbot):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QEnterEvent

    # Discover cards already carry score/episodes; a description also
    # already present (e.g. re-hovering after set_preview_data arrived)
    # means there is nothing left to fetch.
    card = AnimeCard({"title": "One Piece", "score": 87, "description": "Ja carregado."})
    qtbot.addWidget(card)

    requests_seen = []
    card.preview_requested.connect(lambda d: requests_seen.append(d))
    card.enterEvent(QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(0, 0)))

    assert requests_seen == []


def test_hovering_shows_the_panel_and_leaving_hides_it(qtbot):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QEnterEvent

    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)

    card.enterEvent(QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(0, 0)))
    assert card._preview_panel.isHidden() is False

    # leaveEvent debounces the hide (see _hide_timer) so a quick hop from the
    # small card onto the reparented preview panel doesn't flicker. Firing
    # the timer's own slot directly (rather than a real qtbot.wait) avoids
    # the offscreen QPA's synthetic cursor position re-triggering a real
    # Enter event when the widget is actually shown/exposed.
    card.leaveEvent(QEvent(QEvent.Type.Leave))
    assert card._hide_timer.isActive() is True
    assert card._preview_panel.isHidden() is False

    card._hide_preview()
    assert card._preview_panel.isHidden() is True


def test_re_entering_before_the_hide_delay_cancels_the_hide(qtbot):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QEnterEvent

    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)

    card.enterEvent(QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(0, 0)))
    card.leaveEvent(QEvent(QEvent.Type.Leave))
    assert card._hide_timer.isActive() is True

    # Mouse lands on the (separately-parented) preview panel almost
    # immediately — this must cancel the pending hide, not flicker it.
    card._preview_panel.hovered.emit(True)

    assert card._hide_timer.isActive() is False
    assert card._preview_panel.isHidden() is False


def test_score_is_shown_when_present_in_data():
    # _preview_score lives inside the (hidden-until-hover) preview panel, so
    # isVisible() would be False regardless — isHidden() reflects only the
    # widget's own explicit visibility flag, independent of its ancestor.
    card = AnimeCard({"title": "One Piece", "score": 87})
    assert card._preview_score.isHidden() is False
    assert "8.7" in card._preview_score.text()


def test_score_row_is_hidden_when_absent():
    card = AnimeCard({"title": "One Piece"})
    assert card._preview_score.isHidden() is True


def test_episode_count_is_shown_when_present():
    card = AnimeCard({"title": "One Piece", "episodes": 1172})
    assert card._preview_episodes.isHidden() is False
    assert "1172" in card._preview_episodes.text()


def test_synopsis_shows_placeholder_until_fetched():
    card = AnimeCard({"title": "One Piece"})
    assert "Carregando" in card._preview_synopsis.text()


def test_set_preview_data_populates_synopsis_score_and_episodes():
    card = AnimeCard({"title": "One Piece"})
    card.set_preview_data(score=91, episodes=1172, description="Uma aventura pirata.")

    assert card._preview_synopsis.text() == "Uma aventura pirata."
    assert "9.1" in card._preview_score.text()
    assert "1172" in card._preview_episodes.text()
    assert card.data["score"] == 91


def test_clicking_play_button_emits_clicked_with_card_data(qtbot):
    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)

    with qtbot.waitSignal(card.clicked, timeout=1000) as blocker:
        card._preview_play_btn.click()

    assert blocker.args == [{"title": "One Piece"}]


def test_clicking_list_button_emits_list_toggle_clicked_with_card_data(qtbot):
    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)

    with qtbot.waitSignal(card.list_toggle_clicked, timeout=1000) as blocker:
        card._preview_list_btn.click()

    assert blocker.args == [{"title": "One Piece"}]


def test_set_in_list_updates_data_flag_and_tooltip():
    card = AnimeCard({"title": "One Piece"})
    assert card._preview_list_btn.toolTip() == "Adicionar à lista"

    card.set_in_list(True)

    assert card.data["in_list"] is True
    assert card._preview_list_btn.toolTip() == "Remover da lista"
