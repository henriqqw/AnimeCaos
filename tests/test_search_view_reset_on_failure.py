"""
Fase 5 (TDD): when a search fails (e.g. the ReadTimeoutError from
animesonlinecc.to seen in production logs, now surfaced as a real exception
thanks to the Fase 1/2 timeouts), _on_task_failed() dismisses the play/
download overlays but never touches SearchView — its animated skeleton
("Buscando animes...") keeps spinning forever, and navigating away and back
doesn't reset it because SearchView is a persistent widget in the QStackedLayout.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def window(main_window_factory):
    return main_window_factory()


def test_search_failure_stops_the_skeleton_loading_animation(window, fake_anime_service, qtbot, monkeypatch):
    from animecaos.ui.gui import main_window as main_window_module

    # _on_task_failed() shows a real (modal) QMessageBox on error — stub it so
    # the test doesn't block waiting for a dialog nobody can click.
    monkeypatch.setattr(main_window_module.QMessageBox, "critical", lambda *a, **k: None)

    fake_anime_service.search_exception = RuntimeError("Read timed out.")

    window._search_input.setText("one piece")
    window._on_search_clicked()

    assert window._search_view._skeleton.isVisible() is True

    def _search_done():
        assert window._busy is False

    qtbot.waitUntil(_search_done, timeout=3000)

    assert window._search_view._skeleton.isVisible() is False
    assert window._search_view._skeleton._timer.isActive() is False
