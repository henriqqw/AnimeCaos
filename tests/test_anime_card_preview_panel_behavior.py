"""
TDD: two bugs reported after the hover-preview panel shipped.

1. The panel is reparented onto the top-level window while shown (so it can
   escape QScrollArea clipping), which meant a mouse-wheel scroll while
   hovering a cover hit the panel instead of the scroll area/row underneath
   it — scrolling silently stopped working the moment a card expanded. A
   naive fix (re-dispatch the event at the original card and let Qt bubble
   it up) does not actually work: Qt only auto-bubbles *ignored* wheel
   events up the parent chain for genuine hardware-originated events, not
   ones constructed and sent by our own code — confirmed empirically, not
   just from docs. The real fix walks the card's ancestor chain and drives
   whichever real scroll area(s) would have received the event directly.

2. Because the panel lives on the top-level window rather than inside the
   page that spawned it, switching pages didn't hide it — if the mouse sat
   still over a card, the expanded panel kept floating on top of whatever
   page came next. Fix: AnimatedStackedWidget.slide_to() force-closes
   whichever card's panel is currently shown before switching pages.

3. Hiding alone turned out to be insufficient: the panel sits *under the
   cursor*, so hiding it hands the cursor to the card beneath, which fires
   enterEvent and reopens the panel immediately. The reopened panel then
   outlives the page switch that triggered the hide (it is parented to the
   window, not the page), leaving it floating over the next page — the
   reported "ao dar play a capa vem junto". Hence suppress_previews(),
   which also blocks reopening for a moment.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QEnterEvent, QWheelEvent

from animecaos.ui.gui.widgets.anime_card import AnimeCard


@pytest.fixture(autouse=True)
def _reset_preview_state():
    # Both are class-level, so without this a suppression armed by one test
    # would silently swallow the next test's hover (they run milliseconds
    # apart, well inside the cooldown).
    AnimeCard._active_preview_card = None
    AnimeCard._suppressed_until = 0.0
    yield
    AnimeCard._active_preview_card = None
    AnimeCard._suppressed_until = 0.0


def _enter(card: AnimeCard) -> None:
    card.enterEvent(QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(0, 0)))


def _wheel(dx: int = 0, dy: int = 0) -> QWheelEvent:
    return QWheelEvent(
        QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(dx, dy),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )


def test_wheel_over_the_panel_scrolls_the_enclosing_page_scroll_area(qtbot):
    # e.g. Search/Lista: a plain vertical QScrollArea holding a grid of cards.
    from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    qtbot.addWidget(scroll)
    container = QWidget()
    layout = QVBoxLayout(container)
    card = AnimeCard({"title": "One Piece"}, parent=container)
    layout.addWidget(card)
    padding = QLabel()
    padding.setFixedSize(150, 2000)
    layout.addWidget(padding)
    scroll.setWidget(container)
    scroll.resize(300, 300)
    scroll.show()
    qtbot.waitExposed(scroll)

    _enter(card)
    bar = scroll.verticalScrollBar()
    assert bar.value() == 0

    card._preview_panel.wheelEvent(_wheel(dy=-240))

    assert bar.value() > 0


def test_wheel_over_the_panel_scrolls_its_horizontal_row(qtbot):
    from animecaos.ui.gui.widgets.card_scroll import HorizontalCardScroll

    row = HorizontalCardScroll("Em Alta")
    qtbot.addWidget(row)
    row.set_cards([{"title": f"Anime {i}"} for i in range(20)])
    row.resize(300, 300)
    row.show()
    qtbot.waitExposed(row)

    card = row.get_card(0)
    _enter(card)
    bar = row._scroll.horizontalScrollBar()
    assert bar.value() == 0

    card._preview_panel.wheelEvent(_wheel(dx=-240))

    assert bar.value() > 0


def test_wheel_over_the_panel_bubbles_past_a_horizontal_row_to_the_outer_page(qtbot):
    # e.g. Home: a vertical page QScrollArea containing horizontal rows.
    # Vertical scrolling while hovering a card in a row must scroll the
    # page, not get swallowed by the row (which has no vertical bar of its
    # own — ScrollBarAlwaysOff — so it must let it pass through).
    from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget
    from animecaos.ui.gui.widgets.card_scroll import HorizontalCardScroll

    outer = QScrollArea()
    outer.setWidgetResizable(True)
    qtbot.addWidget(outer)
    page = QWidget()
    page_layout = QVBoxLayout(page)
    row = HorizontalCardScroll("Em Alta")
    row.set_cards([{"title": f"Anime {i}"} for i in range(20)])
    page_layout.addWidget(row)
    padding = QLabel()
    padding.setFixedSize(150, 2000)
    page_layout.addWidget(padding)
    outer.setWidget(page)
    outer.resize(300, 400)
    outer.show()
    qtbot.waitExposed(outer)

    card = row.get_card(0)
    _enter(card)
    outer_bar = outer.verticalScrollBar()
    row_bar = row._scroll.horizontalScrollBar()
    assert outer_bar.value() == 0

    card._preview_panel.wheelEvent(_wheel(dy=-240))

    assert outer_bar.value() > 0
    assert row_bar.value() == 0


def test_showing_a_preview_registers_it_as_the_active_one(qtbot):
    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)
    _enter(card)

    assert AnimeCard._active_preview_card is card


def test_hide_all_previews_hides_the_active_panel(qtbot):
    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)
    _enter(card)
    assert card._preview_panel.isHidden() is False

    AnimeCard.hide_all_previews()

    assert card._preview_panel.isHidden() is True
    assert AnimeCard._active_preview_card is None


def test_hide_all_previews_is_a_no_op_when_nothing_is_shown():
    AnimeCard.hide_all_previews()
    assert AnimeCard._active_preview_card is None


def test_hide_all_previews_survives_a_stale_reference_to_a_destroyed_card():
    import shiboken6

    card = AnimeCard({"title": "One Piece"})
    _enter(card)
    assert AnimeCard._active_preview_card is card

    shiboken6.delete(card)

    AnimeCard.hide_all_previews()

    assert AnimeCard._active_preview_card is None


def test_suppressing_blocks_an_immediate_reopen(qtbot):
    # This is the crux of the "capa vem junto" bug: hiding the panel makes
    # Qt hand the cursor to the card underneath, whose enterEvent would
    # otherwise reopen it right away.
    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)
    _enter(card)

    AnimeCard.suppress_previews()
    assert card._preview_panel.isHidden() is True

    _enter(card)

    assert card._preview_panel.isHidden() is True


def test_suppression_expires_so_later_hovers_still_work(qtbot, monkeypatch):
    import animecaos.ui.gui.widgets.anime_card as anime_card_module

    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)
    _enter(card)
    AnimeCard.suppress_previews()

    # Jump past the cooldown rather than sleeping through it.
    real_monotonic = anime_card_module.time.monotonic
    monkeypatch.setattr(
        anime_card_module.time, "monotonic", lambda: real_monotonic() + 10.0
    )

    _enter(card)

    assert card._preview_panel.isHidden() is False


def test_suppressing_with_nothing_open_does_not_block_the_next_hover(qtbot):
    # Rebuild paths call suppress_previews() unconditionally; when no panel
    # was open there is no cursor-under-panel situation, so arming a
    # cooldown would only swallow a legitimate hover right afterwards.
    AnimeCard.suppress_previews()

    card = AnimeCard({"title": "One Piece"})
    qtbot.addWidget(card)
    _enter(card)

    assert card._preview_panel.isHidden() is False


def test_destroying_a_card_also_destroys_its_orphaned_panel(qtbot):
    import shiboken6
    from PySide6.QtWidgets import QWidget

    window = QWidget()
    qtbot.addWidget(window)
    card = AnimeCard({"title": "One Piece"}, parent=window)
    _enter(card)
    panel = card._preview_panel
    # Showing reparents it onto the top-level window, not the card, so
    # destroying the card would otherwise leave it floating forever.
    assert panel.parent() is window

    card.deleteLater()
    qtbot.wait(50)

    assert shiboken6.isValid(panel) is False


def test_rebuilding_a_horizontal_row_closes_a_shown_preview(qtbot):
    from animecaos.ui.gui.widgets.card_scroll import HorizontalCardScroll

    row = HorizontalCardScroll("Em Alta")
    qtbot.addWidget(row)
    row.set_cards([{"title": f"Anime {i}"} for i in range(5)])
    card = row.get_card(0)
    _enter(card)
    panel = card._preview_panel
    assert panel.isHidden() is False

    row.set_cards([{"title": "Outro"}])

    assert panel.isHidden() is True


def test_re_searching_closes_a_shown_preview(qtbot):
    from animecaos.ui.gui.views.search_view import SearchView

    view = SearchView()
    qtbot.addWidget(view)
    view.set_results([{"title": "Clevatess Season 2"}], query="clevatess")
    card = view._cards[0]
    _enter(card)
    panel = card._preview_panel
    assert panel.isHidden() is False

    view.show_searching("outra busca")

    assert panel.isHidden() is True


def test_rebuilding_the_list_view_closes_a_shown_preview(qtbot):
    from animecaos.ui.gui.views.list_view import ListView

    view = ListView()
    qtbot.addWidget(view)
    view.set_animes([{"title": "One Piece"}])
    card = view._cards[0]
    _enter(card)
    panel = card._preview_panel
    assert panel.isHidden() is False

    view.set_animes([])

    assert panel.isHidden() is True


def test_scrolling_a_horizontal_row_closes_a_shown_preview(qtbot):
    from animecaos.ui.gui.widgets.card_scroll import HorizontalCardScroll

    row = HorizontalCardScroll("Em Alta")
    qtbot.addWidget(row)
    row.set_cards([{"title": f"Anime {i}"} for i in range(20)])
    row.resize(300, 300)
    row.show()
    qtbot.waitExposed(row)

    card = row.get_card(0)
    _enter(card)
    assert card._preview_panel.isHidden() is False

    row._scroll.horizontalScrollBar().setValue(200)

    assert card._preview_panel.isHidden() is True


def test_scrolling_the_search_page_closes_a_shown_preview(qtbot):
    from animecaos.ui.gui.views.search_view import SearchView

    view = SearchView()
    qtbot.addWidget(view)
    view.set_results([{"title": f"Anime {i}"} for i in range(40)], query="a")
    view.resize(400, 300)
    view.show()
    qtbot.waitExposed(view)
    qtbot.wait(50)  # let the grid lay out so the scroll range is real

    card = view._cards[0]
    _enter(card)
    assert card._preview_panel.isHidden() is False

    bar = view._scroll.verticalScrollBar()
    assert bar.maximum() > 0
    bar.setValue(bar.maximum())

    assert card._preview_panel.isHidden() is True


def test_navigating_between_pages_hides_a_lingering_preview_panel(qtbot):
    from animecaos.ui.gui.widgets.animated_stack import AnimatedStackedWidget
    from PySide6.QtWidgets import QWidget

    stack = AnimatedStackedWidget()
    qtbot.addWidget(stack)
    page_a = QWidget()
    page_b = QWidget()
    stack.addWidget(page_a)
    stack.addWidget(page_b)

    card = AnimeCard({"title": "One Piece"}, parent=page_a)
    qtbot.addWidget(card)
    _enter(card)
    assert card._preview_panel.isHidden() is False

    stack.slide_to(1)

    assert card._preview_panel.isHidden() is True
