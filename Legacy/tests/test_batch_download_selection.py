"""
Sugestao de usuario: uma opcao para fazer o download em lote. Selecionar
varios episodios de uma vez e baixa-los todos, em vez de clicar episodio por
episodio. Os downloads em si continuam passando pela fila
(DownloadQueueService, ver test_download_queue.py) — o lote so decide QUAIS
episodios entram na fila de uma vez; a fila e quem controla quantos rodam
em paralelo, exatamente como um download avulso.
"""
from __future__ import annotations

from animecaos.ui.gui.views.detail_view import AnimeDetailView
from animecaos.ui.gui.widgets.episode_row import EpisodeRow


# ── EpisodeRow ───────────────────────────────────────────────────────


def test_set_selectable_true_mostra_o_checkbox(qtbot):
    # row aqui e um widget solto, sem uma janela de topo mostrada — isHidden()
    # reflete a flag de visibilidade do proprio widget, independente da
    # cadeia de ancestrais (mesma convencao de test_anime_card_hover_preview.py).
    row = EpisodeRow(1, "Episodio 1", url="")
    qtbot.addWidget(row)

    row.set_selectable(True)

    assert row._checkbox.isHidden() is False


def test_set_selectable_false_esconde_e_limpa_a_selecao(qtbot):
    row = EpisodeRow(1, "Episodio 1", url="")
    qtbot.addWidget(row)

    row.set_selectable(True)
    row.set_selected(True)
    row.set_selectable(False)

    assert row._checkbox.isHidden() is True
    assert row.is_selected() is False


def test_clicar_na_linha_em_modo_selecao_nao_dispara_play_ou_download(qtbot):
    row = EpisodeRow(1, "Episodio 1", url="")
    qtbot.addWidget(row)
    row.set_selectable(True)

    play_received = []
    download_received = []
    row.play_clicked.connect(lambda *_: play_received.append(1))
    row.download_clicked.connect(lambda *_: download_received.append(1))

    from PySide6.QtCore import Qt as QtConst
    from PySide6.QtGui import QMouseEvent

    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        row.rect().center().toPointF(),
        QtConst.MouseButton.LeftButton,
        QtConst.MouseButton.LeftButton,
        QtConst.KeyboardModifier.NoModifier,
    )
    row.mousePressEvent(event)

    assert play_received == []
    assert download_received == []
    assert row.is_selected() is True  # o clique alternou a selecao


def test_sair_do_modo_selecao_restaura_os_botoes_normais(qtbot):
    row = EpisodeRow(1, "Episodio 1", url="")
    qtbot.addWidget(row)

    row.set_selectable(True)
    assert row._play_btn.isHidden() is True
    assert row._dl_btn.isHidden() is True

    row.set_selectable(False)
    assert row._play_btn.isHidden() is False
    assert row._dl_btn.isHidden() is False


# ── AnimeDetailView ──────────────────────────────────────────────────


def _view_with_episodes(qtbot, count=5):
    view = AnimeDetailView()
    qtbot.addWidget(view)
    view.set_episodes([f"Episodio {i + 1}" for i in range(count)])
    return view


def test_selecionar_todos_marca_todos_os_episodios(qtbot):
    view = _view_with_episodes(qtbot, 5)
    view.enter_selection_mode()

    view.select_all_episodes()

    assert all(row.is_selected() for row in view._episode_rows)


def test_selecionar_nenhum_limpa_a_selecao(qtbot):
    view = _view_with_episodes(qtbot, 5)
    view.enter_selection_mode()
    view.select_all_episodes()

    view.select_no_episodes()

    assert all(not row.is_selected() for row in view._episode_rows)


def test_download_batch_clicked_emite_indices_ordenados_sem_duplicatas(qtbot):
    view = _view_with_episodes(qtbot, 5)
    view.enter_selection_mode()

    view._episode_rows[3].set_selected(True)
    view._episode_rows[0].set_selected(True)
    view._episode_rows[1].set_selected(True)

    received = []
    view.download_batch_clicked.connect(received.append)

    view._on_download_selected_clicked()

    assert received == [[0, 1, 3]]


def test_sair_do_modo_selecao_via_view_restaura_botoes(qtbot):
    view = _view_with_episodes(qtbot, 3)
    view.enter_selection_mode()
    assert view._episode_rows[0]._checkbox.isHidden() is False

    view.exit_selection_mode()

    assert view._episode_rows[0]._checkbox.isHidden() is True
    assert view._episode_rows[0]._play_btn.isHidden() is False


# ── integracao com MainWindow ────────────────────────────────────────


def test_baixar_selecionados_enfileira_todos_os_episodios(main_window_factory, qtbot):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"
    window._detail_view.set_episodes([f"Episodio {i + 1}" for i in range(5)])

    window._detail_view.download_batch_clicked.emit([0, 2, 4])

    qtbot.waitUntil(
        lambda: len(window._download_queue.active) + len(window._download_queue.pending) == 3,
        timeout=2000,
    )
    episodes = sorted(
        item.episode_index for item in window._download_queue.active + window._download_queue.pending
    )
    assert episodes == [0, 2, 4]

    window._on_download_cancel()
