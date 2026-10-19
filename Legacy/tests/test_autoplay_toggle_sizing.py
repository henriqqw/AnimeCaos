"""
TDD: the "Auto-play" label was getting clipped ("Auto-pla|"). Root cause:
_AutoplayToggle computed its fixed width from QFontMetrics(self.font()) in
__init__ — before the widget was parented and the app's global QSS
(font-family: "Segoe UI", ...) had been applied to it. The font used to
*measure* the text didn't match the font actually used to *paint* it, so the
box ended up a few pixels too narrow.
"""
from __future__ import annotations

from PySide6.QtGui import QFontMetrics

from animecaos.ui.gui.widgets.mini_player import MiniPlayer, _AutoplayToggle


def test_toggle_width_fits_its_own_label_after_being_shown(qtbot):
    player = MiniPlayer()
    qtbot.addWidget(player)
    player.show()
    qtbot.waitExposed(player)

    toggle = player.autoplay_checkbox
    needed = toggle._BOX + toggle._GAP + QFontMetrics(toggle.font()).horizontalAdvance(toggle._text)

    assert toggle.width() >= needed, (
        f"toggle is {toggle.width()}px wide but needs >= {needed}px to fit "
        f"'{toggle._text}' without clipping"
    )


def test_toggle_width_accounts_for_a_non_default_font(qtbot):
    toggle = _AutoplayToggle("Auto-play")
    qtbot.addWidget(toggle)

    font = toggle.font()
    font.setFamily("Segoe UI")
    font.setPointSize(14)  # larger than default — must not clip once applied
    toggle.setFont(font)
    toggle.show()
    qtbot.waitExposed(toggle)

    needed = toggle._BOX + toggle._GAP + QFontMetrics(toggle.font()).horizontalAdvance(toggle._text)
    assert toggle.width() >= needed
