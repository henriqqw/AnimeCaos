"""
TDD: the hero's meta badge row (TV / 24m / rating / episodes / HD) had no
width limit or wrapping — QHBoxLayout just lays widgets out left-to-right
forever. Most anime only trigger 4 badges (format, duration, score, "HD"),
which happened to fit, but any anime with BOTH a known score AND a known
episode count gets a 5th badge ("N eps"), and the row overflows past the
hero's fixed content width. Because the row sits inside a widget with a
QGraphicsOpacityEffect (used for the crossfade), Qt rasterizes it to that
widget's own rect, so anything past the edge is clipped mid-glyph — exactly
the "★7" / "13 ер" (garbled "13 eps") the user saw.

layout_badges_into_rows() wraps badges into as many rows as needed so this
becomes structurally impossible, the same fix pattern as the title.
"""
from __future__ import annotations

from PySide6.QtGui import QFont, QFontMetrics

from animecaos.ui.gui.widgets.spotlight_banner import (
    _BADGE_FONT_PX,
    _BADGE_H_PADDING,
    _BADGE_SPACING,
    layout_badges_into_rows,
)


def _metrics(qapp_instance) -> QFontMetrics:
    font = QFont("Segoe UI")
    font.setPixelSize(_BADGE_FONT_PX)
    return QFontMetrics(font)


def _row_width(row: list[str], metrics: QFontMetrics) -> float:
    badge_widths = [metrics.horizontalAdvance(t) + _BADGE_H_PADDING for t in row]
    return sum(badge_widths) + _BADGE_SPACING * (len(row) - 1)


def test_badges_that_fit_stay_on_one_row(qapp_instance):
    metrics = _metrics(qapp_instance)
    tags = ["TV", "24m", "★ 8.7", "HD"]
    rows = layout_badges_into_rows(tags, metrics, max_width=2000)
    assert rows == [tags]


def test_five_badges_wrap_to_a_second_row_when_narrow(qapp_instance):
    metrics = _metrics(qapp_instance)
    tags = ["TV", "24m", "★ 7.0", "13 eps", "HD"]
    total_width = sum(metrics.horizontalAdvance(t) for t in tags) + 200  # + paddings/gaps
    narrow = total_width // 2
    rows = layout_badges_into_rows(tags, metrics, max_width=narrow)
    assert len(rows) >= 2
    # No tag is ever dropped — wrapping must not lose information.
    assert [t for row in rows for t in row] == tags


def test_every_row_fits_within_max_width_or_is_a_single_oversized_badge(qapp_instance):
    metrics = _metrics(qapp_instance)
    tags = ["TV", "24m", "★ 7.0", "13 eps", "HD"]
    max_width = 150
    rows = layout_badges_into_rows(tags, metrics, max_width=max_width)
    for row in rows:
        width = _row_width(row, metrics)
        assert width <= max_width or len(row) == 1


def test_a_single_badge_wider_than_max_width_still_gets_its_own_row(qapp_instance):
    metrics = _metrics(qapp_instance)
    tags = ["A Very Long Format Name Indeed"]
    rows = layout_badges_into_rows(tags, metrics, max_width=10)
    assert rows == [["A Very Long Format Name Indeed"]]


def test_empty_tags_returns_no_rows(qapp_instance):
    metrics = _metrics(qapp_instance)
    assert layout_badges_into_rows([], metrics, max_width=500) == []


def test_widget_wraps_a_five_badge_card_without_losing_any_badge(qtbot):
    from animecaos.ui.gui.widgets.spotlight_banner import SpotlightBanner

    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.show()
    qtbot.waitExposed(banner)
    banner.resize(700, 420)  # narrow enough that cw hits its 380px floor

    banner.set_cards([{
        "title": "Some Anime",
        "format": "TV",
        "duration": 24,
        "score": 70,
        "episodes": 13,
        "_rank": 3,
    }])

    all_badge_texts = [b.text() for row in banner._meta_row_widgets for b in row.findChildren(type(banner._meta_badges[0]))]
    assert set(all_badge_texts) == {"TV", "24m", "★ 7.0", "13 eps", "HD"}
    assert len(all_badge_texts) == 5  # nothing silently dropped

    content_width = banner._content_widget.width()
    for row_widget in banner._meta_row_widgets:
        assert row_widget.sizeHint().width() <= content_width


def test_widget_resize_relayouts_badge_rows(qtbot):
    from animecaos.ui.gui.widgets.spotlight_banner import SpotlightBanner

    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.show()
    qtbot.waitExposed(banner)

    banner.resize(1320, 420)
    banner.set_cards([{
        "title": "Some Anime", "format": "TV", "duration": 24,
        "score": 70, "episodes": 13, "_rank": 1,
    }])
    wide_row_count = len(banner._meta_row_widgets)

    banner.resize(700, 420)
    qtbot.wait(10)
    narrow_row_count = len(banner._meta_row_widgets)

    # Narrower window must never end up with FEWER rows (badges never get
    # lost/merged) — going narrower can only keep the same count or wrap more.
    assert narrow_row_count >= wide_row_count
