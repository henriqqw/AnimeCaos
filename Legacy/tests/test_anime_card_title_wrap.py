"""
TDD: long anime titles (e.g. "Koukaku Kidoutai Arise: Ghost in the Shell -
Border:1 Ghost Pain") were rendering with the bottom half of the second line
cut off mid-character — QLabel's wordWrap+maximumHeight combo clips at a
pixel height that doesn't line up with actual line metrics whenever the text
wraps to exactly the max number of lines. This happened both on the plain
card (title_label) and the new hover preview panel (_preview_title).

Fix: pre-wrap with the same wrap_and_elide_lines() helper already used for
the home hero title, then size the label exactly for that many real lines —
long titles now end in a clean "…" instead of a broken half-line.
"""
from __future__ import annotations

from animecaos.ui.gui.widgets.anime_card import AnimeCard

_LONG_TITLE = "Koukaku Kidoutai Arise: Ghost in the Shell - Border:1 Ghost Pain"


def test_short_title_is_not_truncated():
    card = AnimeCard({"title": "One Piece"})
    assert card.title_label.text() == "One Piece"


def test_long_title_on_the_plain_card_ends_with_an_ellipsis():
    card = AnimeCard({"title": _LONG_TITLE})
    assert card.title_label.text().endswith("…")
    assert card.title_label.text().count("\n") <= 1


def test_long_title_label_height_is_fixed_not_clipped_by_max_height():
    # setMaximumHeight only caps growth (still allows the label to render
    # taller content clipped by an ancestor). setFixedHeight guarantees the
    # label's own sizeHint matches its actual rendered height exactly.
    card = AnimeCard({"title": _LONG_TITLE})
    assert card.title_label.minimumHeight() == card.title_label.maximumHeight()


def test_long_title_on_the_hover_preview_ends_with_an_ellipsis():
    card = AnimeCard({"title": _LONG_TITLE})
    assert card._preview_title.text().endswith("…")
    assert card._preview_title.text().count("\n") <= 1


def test_card_still_fits_its_fixed_size_regardless_of_title_length():
    card = AnimeCard({"title": _LONG_TITLE})
    assert card.size().toTuple() == (AnimeCard.CARD_WIDTH, AnimeCard.CARD_HEIGHT)
    assert card._preview_panel.size().toTuple() == (AnimeCard.CARD_WIDTH, AnimeCard.CARD_HEIGHT)
