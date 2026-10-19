"""
TDD: the anime detail page needs an "Adicionar à Lista" / "Na Lista" toggle
button (like Crunchyroll/Netflix's My List button), placed under the title.
The view only owns presentation state (set_in_list / in_list); MainWindow
decides what to persist via WatchlistService when list_toggle_clicked fires.
"""
from __future__ import annotations

from animecaos.ui.gui.views.detail_view import AnimeDetailView


def test_starts_not_in_list(qtbot):
    view = AnimeDetailView()
    qtbot.addWidget(view)
    assert view.in_list is False
    assert "Adicionar" in view._list_btn.text()


def test_set_in_list_true_updates_button_text_and_state(qtbot):
    view = AnimeDetailView()
    qtbot.addWidget(view)
    view.set_in_list(True)
    assert view.in_list is True
    assert "Na Lista" in view._list_btn.text()


def test_set_in_list_false_reverts_button(qtbot):
    view = AnimeDetailView()
    qtbot.addWidget(view)
    view.set_in_list(True)
    view.set_in_list(False)
    assert view.in_list is False
    assert "Adicionar" in view._list_btn.text()


def test_clicking_toggle_button_emits_list_toggle_clicked(qtbot):
    view = AnimeDetailView()
    qtbot.addWidget(view)

    with qtbot.waitSignal(view.list_toggle_clicked, timeout=1000):
        view._list_btn.click()


def test_set_anime_resets_in_list_state(qtbot):
    view = AnimeDetailView()
    qtbot.addWidget(view)
    view.set_in_list(True)

    view.set_anime("Another Anime")

    assert view.in_list is False
