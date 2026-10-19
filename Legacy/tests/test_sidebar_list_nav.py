"""
TDD: the sidebar needs a "Minha Lista" (watchlist) nav button using the new
Crunchyroll-style bookmark icon, wired through the same generic nav_changed
signal as every other sidebar button.
"""
from __future__ import annotations

from animecaos.ui.gui.widgets.sidebar import SidebarNav


def test_sidebar_has_a_list_button(qtbot):
    sidebar = SidebarNav()
    qtbot.addWidget(sidebar)
    assert "list" in sidebar._buttons
    assert sidebar._buttons["list"].toolTip() == "Minha Lista"


def test_clicking_list_button_emits_nav_changed_with_list_key(qtbot):
    sidebar = SidebarNav()
    qtbot.addWidget(sidebar)

    with qtbot.waitSignal(sidebar.nav_changed, timeout=1000) as blocker:
        sidebar._buttons["list"].click()

    assert blocker.args == ["list"]


def test_set_active_list_checks_the_list_button(qtbot):
    sidebar = SidebarNav()
    qtbot.addWidget(sidebar)
    sidebar.set_active("list")
    assert sidebar._buttons["list"].isChecked()
