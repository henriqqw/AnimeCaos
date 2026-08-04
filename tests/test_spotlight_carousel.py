"""
TDD: SpotlightBanner used to show a single, static "spotlight" anime with no
way to navigate. This turns it into a real carousel — minimum handled here
is however many cards the caller passes in (main_window/loader_worker now
collect up to 5) — that auto-advances every 10s, supports prev/next arrows
and click-to-jump dots (bottom-left), and resets its auto-advance countdown
on manual navigation so it doesn't double-hop right after a user interaction.
"""
from __future__ import annotations

import animecaos.ui.gui.widgets.spotlight_banner as spotlight_banner_module
from animecaos.ui.gui.widgets.spotlight_banner import (
    AUTO_ADVANCE_MS,
    SpotlightBanner,
    _TITLE_MAX_LINES,
)


def _cards(n: int) -> list[dict]:
    return [{"title": f"Anime {i}", "anilist_id": i, "_rank": i + 1} for i in range(n)]


def test_single_card_has_no_carousel_chrome_and_does_not_auto_advance(qtbot):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)

    banner.set_cards(_cards(1))

    assert banner.isVisible() is True
    assert banner._prev_arrow.isVisible() is False
    assert banner._next_arrow.isVisible() is False
    assert banner._dots.isVisible() is False
    assert banner._timer.isActive() is False


def test_empty_cards_hides_the_banner(qtbot):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)

    banner.set_cards([])

    assert banner.isVisible() is False


def test_multiple_cards_shows_carousel_chrome_and_starts_the_timer(qtbot):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)

    banner.set_cards(_cards(5))

    assert banner._prev_arrow.isVisible() is True
    assert banner._next_arrow.isVisible() is True
    assert banner._dots.isVisible() is True
    assert banner._dots._count == 5
    assert banner._timer.isActive() is True
    assert banner._timer.interval() == AUTO_ADVANCE_MS == 10_000


def test_go_next_wraps_around_to_the_first_card(qtbot):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.set_cards(_cards(3))

    assert banner.current_card()["title"] == "Anime 0"
    banner.go_next()
    assert banner.current_card()["title"] == "Anime 1"
    banner.go_next()
    assert banner.current_card()["title"] == "Anime 2"
    banner.go_next()
    assert banner.current_card()["title"] == "Anime 0"


def test_go_prev_wraps_around_to_the_last_card(qtbot):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.set_cards(_cards(3))

    banner.go_prev()
    assert banner.current_card()["title"] == "Anime 2"


def test_clicking_a_dot_jumps_directly_to_that_card(qtbot):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.set_cards(_cards(5))

    banner._on_dot_clicked(3)

    assert banner.current_card()["title"] == "Anime 3"
    assert banner._dots._current == 3


def test_arrow_buttons_drive_navigation(qtbot):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.set_cards(_cards(3))

    qtbot.mouseClick(banner._next_arrow, spotlight_banner_module.Qt.MouseButton.LeftButton)
    assert banner.current_card()["title"] == "Anime 1"

    qtbot.mouseClick(banner._prev_arrow, spotlight_banner_module.Qt.MouseButton.LeftButton)
    assert banner.current_card()["title"] == "Anime 0"


def test_manual_navigation_keeps_the_auto_advance_timer_running(qtbot):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.set_cards(_cards(3))

    banner.go_next()

    assert banner._timer.isActive() is True
    assert banner._timer.interval() == AUTO_ADVANCE_MS


def test_watch_clicked_emits_the_currently_displayed_card(qtbot):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.set_cards(_cards(3))
    banner.go_next()

    with qtbot.waitSignal(banner.watch_clicked, timeout=1000) as blocker:
        banner._watch_btn.click()

    assert blocker.args[0]["title"] == "Anime 1"


def test_timer_timeout_actually_advances_to_the_next_card(qtbot, monkeypatch):
    monkeypatch.setattr(spotlight_banner_module, "AUTO_ADVANCE_MS", 30)
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.set_cards(_cards(3))

    def _advanced():
        assert banner.current_card()["title"] == "Anime 1"

    qtbot.waitUntil(_advanced, timeout=2000)


def test_long_title_never_overflows_the_labels_line_budget(qtbot):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.resize(1320, 420)

    banner.set_cards([{
        "title": "The Oblivious Saint Can't Contain Her Power Anymore This Season",
        "_rank": 2,
    }])

    rendered_lines = banner._title_lbl.text().split("\n")
    assert len(rendered_lines) <= _TITLE_MAX_LINES
    # Fixed height means this can never grow into the description below it,
    # regardless of how long the title is.
    assert banner._title_lbl.height() == int(
        banner._title_metrics.lineSpacing() * _TITLE_MAX_LINES
    ) + 4


def test_resizing_the_banner_rewraps_the_title_for_the_current_width(qtbot):
    # Font metrics vary by environment (headless test runners can lack
    # "Segoe UI" and fall back to a substitute with very different glyph
    # widths — see the QFontDatabase warning pytest prints). Rather than
    # asserting on exact rendered pixel-dependent text, verify the widget
    # recomputes wrapping from wrap_and_elide_lines() using its *current*
    # content width every time it's resized — that's the actual behavior
    # under test, and it holds regardless of which font is available.
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.show()
    qtbot.waitExposed(banner)
    long_title = "Mushoku Tensei: Jobless Reincarnation Season 3 Special Extended Edition"
    banner._current_title = long_title

    for width in (1320, 700, 1024):
        banner.resize(width, 420)
        qtbot.wait(10)
        expected_max_width = min(
            max(100, banner._content_widget.width() - 40),
            banner._title_lbl.maximumWidth(),
        )
        expected = "\n".join(
            spotlight_banner_module.wrap_and_elide_lines(
                long_title, banner._title_metrics, expected_max_width, _TITLE_MAX_LINES
            )
        )
        assert banner._title_lbl.text() == expected
        assert banner._title_lbl.text().count("\n") + 1 <= _TITLE_MAX_LINES
