"""
Sugestao de usuario: prevenir downloads duplicados. Antes de enfileirar um
episodio, MainWindow verifica (via DownloadQueueService.find_active_or_queued
— ver test_download_queue.py, o UNICO ponto onde essa checagem acontece) se
ele ja esta na fila/baixando. Se estiver, mostra um dialogo de confirmacao
com foco padrao em "Nao" antes de duplicar. O clique so dispara o feedback
visual (checkmark) e a mensagem de sucesso quando o download de fato entra
na fila — nunca quando o usuario recusa o duplicado.
"""
from __future__ import annotations


def _in_flight_count(window) -> int:
    return len(window._download_queue.active) + len(window._download_queue.pending)


# ── dialogo de duplicado: estrutura ──────────────────────────────


def test_dialogo_de_duplicado_tem_titulo_mensagem_e_foco_padrao_em_nao(main_window_factory):
    window = main_window_factory()
    box, no_btn, yes_btn = window._build_duplicate_download_dialog()

    assert box.windowTitle() == "Episodio ja esta na fila"
    assert "Deseja adicionar outro download mesmo assim" in box.text()
    assert box.defaultButton() is no_btn
    assert box.escapeButton() is no_btn
    assert no_btn.text() == "Nao"
    assert yes_btn.text() == "Sim, baixar novamente"


# ── primeiro clique: enfileira normalmente, sem perguntar nada ──


def test_primeiro_clique_enfileira_sem_perguntar(main_window_factory, monkeypatch):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"

    asked = []
    monkeypatch.setattr(window, "_ask_duplicate_download_confirmation", lambda: asked.append(1) or True)

    window._on_episode_download_clicked(0)

    assert asked == []
    assert _in_flight_count(window) == 1
    window._on_download_cancel()


def test_primeiro_clique_toca_a_animacao_de_confirmacao_na_linha_certa(main_window_factory, monkeypatch):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"
    window._detail_view.set_episodes([f"Episodio {i + 1}" for i in range(3)])

    original_icon = window._detail_view._episode_rows[1]._dl_btn.icon().cacheKey()
    window._on_episode_download_clicked(1)

    assert window._detail_view._episode_rows[1]._dl_btn.icon().cacheKey() != original_icon
    window._on_download_cancel()


def test_primeiro_clique_mostra_mensagem_de_sucesso(main_window_factory, monkeypatch):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"

    messages = []
    monkeypatch.setattr(window, "_set_status", lambda text: messages.append(text))

    window._on_episode_download_clicked(0)

    assert messages[-1] == "Download adicionado a fila."
    window._on_download_cancel()


# ── segundo clique no mesmo episodio: pergunta antes de duplicar ─


def test_segundo_clique_no_mesmo_episodio_pergunta_e_nao_duplica_se_recusado(main_window_factory, monkeypatch):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"

    window._on_episode_download_clicked(0)
    assert _in_flight_count(window) == 1

    monkeypatch.setattr(window, "_ask_duplicate_download_confirmation", lambda: False)
    window._on_episode_download_clicked(0)

    assert _in_flight_count(window) == 1  # nao duplicou
    window._on_download_cancel()


def test_segundo_clique_confirmado_duplica(main_window_factory, monkeypatch):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"

    window._on_episode_download_clicked(0)
    monkeypatch.setattr(window, "_ask_duplicate_download_confirmation", lambda: True)
    window._on_episode_download_clicked(0)

    assert _in_flight_count(window) == 2
    window._on_download_cancel()


def test_recusar_duplicado_nao_toca_a_animacao_de_confirmacao(main_window_factory, monkeypatch):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"
    window._detail_view.set_episodes([f"Episodio {i + 1}" for i in range(3)])

    window._on_episode_download_clicked(0)
    icon_after_first_click = window._detail_view._episode_rows[0]._dl_btn.icon().cacheKey()
    # O timer real (1s) ainda nao rodou, entao o icone deveria continuar
    # sendo o check nesse ponto; simulamos o retorno ao icone normal pra
    # isolar o teste do timing real.
    window._detail_view._episode_rows[0]._on_download_confirm_timeout()
    icon_after_reset = window._detail_view._episode_rows[0]._dl_btn.icon().cacheKey()

    monkeypatch.setattr(window, "_ask_duplicate_download_confirmation", lambda: False)
    window._on_episode_download_clicked(0)

    assert window._detail_view._episode_rows[0]._dl_btn.icon().cacheKey() == icon_after_reset
    window._on_download_cancel()


# ── mensagens amigaveis por status do item existente ─────────────


def test_recusar_duplicado_ja_baixando_mostra_mensagem_especifica(main_window_factory, monkeypatch):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"
    window._on_episode_download_clicked(0)

    item = window._download_queue.find_active_or_queued("One Piece", 0)
    item.status = "downloading"

    monkeypatch.setattr(window, "_ask_duplicate_download_confirmation", lambda: False)
    messages = []
    monkeypatch.setattr(window, "_set_status", lambda text: messages.append(text))

    window._on_episode_download_clicked(0)

    assert messages[-1] == "Episodio ja esta sendo baixado."
    window._on_download_cancel()


def test_recusar_duplicado_ainda_na_fila_mostra_mensagem_especifica(main_window_factory, monkeypatch):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"
    window._on_episode_download_clicked(0)

    item = window._download_queue.find_active_or_queued("One Piece", 0)
    item.status = "queued"

    monkeypatch.setattr(window, "_ask_duplicate_download_confirmation", lambda: False)
    messages = []
    monkeypatch.setattr(window, "_set_status", lambda text: messages.append(text))

    window._on_episode_download_clicked(0)

    assert messages[-1] == "Episodio ja esta na fila."
    window._on_download_cancel()


# ── transicoes de status da fila anunciadas de forma amigavel ────


def test_item_concluido_anuncia_mensagem_amigavel(main_window_factory, monkeypatch):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"
    window._on_episode_download_clicked(0)

    item = window._download_queue.find_active_or_queued("One Piece", 0)
    messages = []
    monkeypatch.setattr(window, "_set_status", lambda text: messages.append(text))

    item.status = "done"
    window._on_queue_item_changed(item)

    assert any("conclu" in m.lower() for m in messages)
    window._on_download_cancel()


def test_item_com_falha_anuncia_mensagem_amigavel_sem_jargao(main_window_factory, monkeypatch):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"
    window._on_episode_download_clicked(0)

    item = window._download_queue.find_active_or_queued("One Piece", 0)
    messages = []
    monkeypatch.setattr(window, "_set_status", lambda text: messages.append(text))

    item.status = "failed"
    item.error = "HTTP 403 Forbidden: connection reset by peer"
    window._on_queue_item_changed(item)

    assert messages[-1] == "Falha ao iniciar download."
    window._on_download_cancel()


def test_mesma_transicao_de_status_nao_repete_a_mensagem(main_window_factory, monkeypatch):
    """item_changed dispara varias vezes por causa do progresso (%, veloci
    dade, ETA) — a mensagem de status so deve aparecer UMA vez por
    transicao real de estado, senao vira spam."""
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"
    window._on_episode_download_clicked(0)

    item = window._download_queue.find_active_or_queued("One Piece", 0)
    item.status = "downloading"
    messages = []
    monkeypatch.setattr(window, "_set_status", lambda text: messages.append(text))

    window._on_queue_item_changed(item)  # 1a vez: deve anunciar "iniciado"
    item.percent = 42.0
    window._on_queue_item_changed(item)  # so progresso, mesmo status: nao deve repetir
    window._on_queue_item_changed(item)

    started_messages = [m for m in messages if "iniciado" in m.lower()]
    assert len(started_messages) == 1
    window._on_download_cancel()


# ── lote: duplicados sao pulados silenciosamente ─────────────────


def test_lote_pula_duplicados_e_adiciona_so_os_novos(main_window_factory, monkeypatch):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"
    window._detail_view.set_episodes([f"Episodio {i + 1}" for i in range(5)])

    window._on_episode_download_clicked(2)  # ja fica na fila/baixando
    assert _in_flight_count(window) == 1

    window._detail_view.download_batch_clicked.emit([0, 2, 4])

    # So 0 e 4 sao novos; o 2 ja estava e nao deve duplicar.
    assert _in_flight_count(window) == 3
    episodes_in_flight = sorted(
        item.episode_index for item in window._download_queue.active + window._download_queue.pending
    )
    assert episodes_in_flight == [0, 2, 4]
    window._on_download_cancel()


def test_lote_totalmente_duplicado_nao_adiciona_nada_e_avisa(main_window_factory, monkeypatch):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"
    window._detail_view.set_episodes([f"Episodio {i + 1}" for i in range(3)])

    window._on_episode_download_clicked(0)
    before = _in_flight_count(window)

    messages = []
    monkeypatch.setattr(window, "_set_status", lambda text: messages.append(text))
    window._detail_view.download_batch_clicked.emit([0])

    assert _in_flight_count(window) == before
    assert messages[-1] == "Todos os episodios selecionados ja estao na fila."
    window._on_download_cancel()


# ── sem opcao de downloads simultaneos: sempre um por vez ────────


def test_main_window_constroi_a_fila_com_um_download_por_vez(main_window_factory):
    """A opcao de downloads simultaneos foi removida das Configuracoes —
    a fila sempre processa um episodio por vez, sem excecao."""
    window = main_window_factory()
    assert window._download_queue._max_concurrent == 1


def test_dois_episodios_na_fila_so_um_baixa_por_vez(main_window_factory):
    window = main_window_factory()
    window._detail_view.set_anime("One Piece")
    window._current_anime = "One Piece"
    window._detail_view.set_episodes([f"Episodio {i + 1}" for i in range(3)])

    window._on_episode_download_clicked(0)
    window._on_episode_download_clicked(1)

    assert len(window._download_queue.active) == 1
    assert len(window._download_queue.pending) == 1
    window._on_download_cancel()
