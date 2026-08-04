"""
Fase 4 (TDD): PlayOverlay is shown while resolving/opening the video player
and today has no way to dismiss it — no button, no signal, no keyboard
escape. If the backend hangs (see Fase 1/2), the user is stuck staring at
"Aguarde, carregando stream..." forever with nothing to click. DownloadOverlay
already has this (cancel_requested signal + a Cancelar button) — PlayOverlay
needs the same affordance.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QWidget

from animecaos.ui.gui.widgets.play_overlay import PlayOverlay


def test_play_overlay_has_cancel_requested_signal():
    assert hasattr(PlayOverlay, "cancel_requested")


def test_clicking_cancel_button_emits_cancel_requested(qtbot, qapp_instance):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)

    overlay = PlayOverlay(parent)
    qtbot.addWidget(overlay)
    overlay.show_loading("Some Anime", 0)

    rect = overlay._primary_btn_rect()
    center = rect.center()

    with qtbot.waitSignal(overlay.cancel_requested, timeout=1000):
        qtbot.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=center.toPoint())


def test_clicking_outside_the_button_does_not_emit_cancel_requested(qtbot, qapp_instance):
    parent = QWidget()
    parent.resize(800, 600)
    qtbot.addWidget(parent)

    overlay = PlayOverlay(parent)
    qtbot.addWidget(overlay)
    overlay.show_loading("Some Anime", 0)

    received = []
    overlay.cancel_requested.connect(lambda: received.append(True))

    # Top-left corner of the card, well away from the cancel button.
    qtbot.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=QPointF(5, 5).toPoint())

    assert not received
