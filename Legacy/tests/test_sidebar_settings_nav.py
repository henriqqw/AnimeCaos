"""
Nova tela de Configuracoes (zoom da UI, player, downloads, dependencias)
precisa de um botao dedicado na sidebar, seguindo o mesmo padrao generico de
nav_changed usado por todos os outros botoes (ver test_sidebar_list_nav.py).
"""
from __future__ import annotations

from animecaos.ui.gui.widgets.sidebar import SidebarNav


def test_sidebar_has_a_settings_button(qtbot):
    sidebar = SidebarNav()
    qtbot.addWidget(sidebar)
    assert "settings" in sidebar._buttons
    assert sidebar._buttons["settings"].toolTip() == "Configuracoes"


def test_clicking_settings_button_emits_nav_changed_with_settings_key(qtbot):
    sidebar = SidebarNav()
    qtbot.addWidget(sidebar)

    with qtbot.waitSignal(sidebar.nav_changed, timeout=1000) as blocker:
        sidebar._buttons["settings"].click()

    assert blocker.args == ["settings"]


def test_set_active_settings_checks_the_settings_button(qtbot):
    sidebar = SidebarNav()
    qtbot.addWidget(sidebar)
    sidebar.set_active("settings")
    assert sidebar._buttons["settings"].isChecked()
