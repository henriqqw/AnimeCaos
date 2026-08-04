"""
TDD: the autoplay control in MiniPlayer used a plain QCheckBox. The app's
QSS styles a checked indicator as a solid accent-colored square with no
checkmark glyph (theme.py has no `border-image`/checkmark for
`QCheckBox::indicator:checked`), so — despite being a real, working
QCheckBox — it visually reads as a decorative red square rather than a
checkbox, which is exactly what was reported. This replaces it with a small
hand-painted toggle (matching the rest of the app's custom-drawn widgets)
that always renders an explicit checkmark when checked.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from animecaos.ui.gui.widgets.mini_player import MiniPlayer


def test_autoplay_is_checked_by_default(qtbot):
    player = MiniPlayer()
    qtbot.addWidget(player)
    assert player.is_autoplay() is True


def test_clicking_the_autoplay_toggle_flips_its_state(qtbot):
    player = MiniPlayer()
    qtbot.addWidget(player)
    toggle = player.autoplay_checkbox

    center = toggle.rect().center()
    qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton, pos=center)
    assert player.is_autoplay() is False

    qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton, pos=center)
    assert player.is_autoplay() is True


def test_toggle_emits_toggled_signal_with_new_state(qtbot):
    player = MiniPlayer()
    qtbot.addWidget(player)
    toggle = player.autoplay_checkbox

    with qtbot.waitSignal(toggle.toggled, timeout=1000) as blocker:
        qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton, pos=toggle.rect().center())
    assert blocker.args == [False]
