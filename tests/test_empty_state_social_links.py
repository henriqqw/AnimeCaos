"""
TDD: the "no results" empty state on the search screen was just a terse
"Nenhum resultado / Tente outro termo de busca" with no path forward. The
user wants it to point people at the social channels
(@getanimecaos on Instagram/X) to request the anime, with clickable icon
buttons that open the right profile — not just plain text.

EmptyState gains an optional `social_links` param: a list of
(icon_pixmap, label, url) tuples rendered as clickable buttons. Passing
nothing keeps every other EmptyState usage (downloads, trending/seasonal
sections, etc.) exactly as before.
"""
from __future__ import annotations

from PySide6.QtGui import QPixmap

from animecaos.ui.gui.widgets.empty_state import EmptyState


def test_no_social_links_means_no_buttons(qtbot):
    widget = EmptyState(title="Nada aqui", subtitle="")
    qtbot.addWidget(widget)
    assert widget._social_buttons == []


def test_social_links_render_one_button_each(qtbot):
    icon = QPixmap(16, 16)
    links = [
        (icon, "Instagram", "https://www.instagram.com/getanimecaos/"),
        (icon, "X", "https://x.com/getanimecaos"),
    ]
    widget = EmptyState(title="Nenhum resultado", subtitle="", social_links=links)
    qtbot.addWidget(widget)
    assert len(widget._social_buttons) == 2
    assert widget._social_buttons[0].text() == "Instagram"
    assert widget._social_buttons[1].text() == "X"


def test_clicking_a_social_button_opens_its_url(qtbot, monkeypatch):
    from animecaos.ui.gui.widgets import empty_state as empty_state_module

    opened: list[str] = []
    monkeypatch.setattr(
        empty_state_module.QDesktopServices, "openUrl", lambda qurl: opened.append(qurl.toString())
    )

    icon = QPixmap(16, 16)
    widget = EmptyState(
        title="Nenhum resultado",
        subtitle="",
        social_links=[(icon, "Instagram", "https://www.instagram.com/getanimecaos/")],
    )
    qtbot.addWidget(widget)

    widget._social_buttons[0].click()

    assert opened == ["https://www.instagram.com/getanimecaos/"]
