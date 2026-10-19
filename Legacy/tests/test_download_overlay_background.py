"""
Sugestoes de usuario: downloads em segundo plano + fechamento automatico da
tela de Downloads. O DownloadOverlay ja tinha dismiss() separado de
cancel_requested, mas so o botao "Cancelar" chamava dismiss() — esconder e
cancelar eram a mesma acao. Agora existe um segundo botao, "Ocultar", que so
fecha o overlay (o download continua rodando na fila) — ver hide_requested.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import Qt as QtConst

from animecaos.ui.gui.overlays.download_overlay import DownloadOverlay


def _click(widget, pos: QPointF) -> None:
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        pos,
        QtConst.MouseButton.LeftButton,
        QtConst.MouseButton.LeftButton,
        QtConst.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(event)


def test_ocultar_esconde_sem_emitir_cancel_requested(qtbot):
    from PySide6.QtWidgets import QWidget
    parent = QWidget()
    qtbot.addWidget(parent)
    overlay = DownloadOverlay(parent)
    qtbot.addWidget(overlay)

    overlay.show_resolving("Naruto", 0)
    overlay.set_downloading()

    cancel_received = []
    hide_received = []
    overlay.cancel_requested.connect(lambda: cancel_received.append(1))
    overlay.hide_requested.connect(lambda: hide_received.append(1))

    secondary_rect = overlay._secondary_btn_rect()
    _click(overlay, secondary_rect.center())

    assert hide_received == [1]
    assert cancel_received == []


def test_cancelar_continua_emitindo_cancel_requested(qtbot):
    from PySide6.QtWidgets import QWidget
    parent = QWidget()
    qtbot.addWidget(parent)
    overlay = DownloadOverlay(parent)
    qtbot.addWidget(overlay)

    overlay.show_resolving("Naruto", 0)
    overlay.set_downloading()

    cancel_received = []
    overlay.cancel_requested.connect(lambda: cancel_received.append(1))

    primary_rect = overlay._primary_btn_rect()
    _click(overlay, primary_rect.center())

    assert cancel_received == [1]


def test_set_title_sobrescreve_o_cabecalho_para_o_agregado(qtbot):
    from PySide6.QtWidgets import QWidget
    parent = QWidget()
    qtbot.addWidget(parent)
    overlay = DownloadOverlay(parent)
    qtbot.addWidget(overlay)

    overlay.show_resolving("Naruto", 0)
    overlay.set_title("3 downloads em andamento", "2 de 3 concluidos")

    assert overlay._anime_name == "3 downloads em andamento"
    assert overlay._episode_label == "2 de 3 concluidos"


def test_set_queue_progress_atualiza_percentual_e_texto(qtbot):
    from PySide6.QtWidgets import QWidget
    parent = QWidget()
    qtbot.addWidget(parent)
    overlay = DownloadOverlay(parent)
    qtbot.addWidget(overlay)

    overlay.show_resolving("Naruto", 0)
    overlay.set_queue_progress(47.5, "Baixando 2 de 5", speed_text="1.2MiB/s", eta_text="00:30")

    assert overlay._percent == 47.5
    assert overlay._status_text == "Baixando 2 de 5"
    assert overlay._speed_text == "1.2MiB/s"
    assert overlay._eta_text == "00:30"
    assert overlay._state == overlay._ST_DOWNLOADING
