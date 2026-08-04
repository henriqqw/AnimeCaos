"""
TDD: the spotlight hero title used a plain QLabel with word-wrap and no line
cap. A long title (e.g. "The Oblivious Saint Can't Contain Her Power") wraps
to 3 lines, but the surrounding QVBoxLayout was sized assuming ~2 lines, so
the third line visually overlapped the description text below it — not a
crash, but a real layout bug ("titulos mt grande...estao sendo cortando").

Fix: wrap_and_elide_lines() bounds the title to a fixed number of lines
regardless of length — long titles get "..." on the last line instead of
overflowing — so the layout height is always predictable and this class of
bug becomes structurally impossible, not just fixed for this one title.
"""
from __future__ import annotations

from PySide6.QtGui import QFont, QFontMetrics

from animecaos.ui.gui.widgets.spotlight_banner import wrap_and_elide_lines


def _metrics(qapp_instance) -> QFontMetrics:
    font = QFont("Segoe UI")
    font.setPixelSize(38)
    font.setWeight(QFont.Weight.ExtraBold)
    return QFontMetrics(font)


def test_short_title_fits_on_one_line(qapp_instance):
    metrics = _metrics(qapp_instance)
    lines = wrap_and_elide_lines("One Piece", metrics, max_width=480, max_lines=2)
    assert lines == ["One Piece"]


def test_never_exceeds_max_lines_for_a_very_long_title(qapp_instance):
    metrics = _metrics(qapp_instance)
    title = "The Oblivious Saint Can't Contain Her Power Anymore This Season"
    lines = wrap_and_elide_lines(title, metrics, max_width=480, max_lines=2)
    assert len(lines) <= 2


def test_truncated_title_ends_with_an_ellipsis(qapp_instance):
    metrics = _metrics(qapp_instance)
    title = "The Oblivious Saint Can't Contain Her Power Anymore This Season"
    lines = wrap_and_elide_lines(title, metrics, max_width=480, max_lines=2)
    assert lines[-1].endswith("…")


def test_every_line_fits_within_max_width(qapp_instance):
    metrics = _metrics(qapp_instance)
    title = "Mushoku Tensei: Jobless Reincarnation Season 3 Special Extended Edition"
    max_width = 480
    lines = wrap_and_elide_lines(title, metrics, max_width=max_width, max_lines=2)
    for line in lines:
        assert metrics.horizontalAdvance(line) <= max_width


def test_title_that_fits_exactly_in_two_lines_is_not_truncated(qapp_instance):
    metrics = _metrics(qapp_instance)
    title = "Attack on Titan"
    # Wide enough to hold "Attack on" (and "Titan" alone, which is shorter)
    # on their own lines, narrow enough that the full title needs 2 lines.
    max_width = int(metrics.horizontalAdvance("Attack on") * 1.15)
    lines = wrap_and_elide_lines(title, metrics, max_width=max_width, max_lines=2)
    assert len(lines) == 2
    assert not lines[-1].endswith("…")
    assert " ".join(lines) == title


def test_empty_title_returns_empty_list(qapp_instance):
    metrics = _metrics(qapp_instance)
    assert wrap_and_elide_lines("", metrics, max_width=480, max_lines=2) == []


def test_single_word_longer_than_max_width_still_returns_bounded_lines(qapp_instance):
    metrics = _metrics(qapp_instance)
    title = "Supercalifragilisticexpialidocious"
    lines = wrap_and_elide_lines(title, metrics, max_width=100, max_lines=2)
    assert 1 <= len(lines) <= 2
    for line in lines:
        assert metrics.horizontalAdvance(line) <= 100
