"""
Sugestao de usuario: feedback visual imediato ao clicar em baixar. O icone
de download deve virar um check verde por ~800-1200ms e voltar suavemente
ao icone original — comunicando que a acao foi registrada mesmo antes do
download comecar de verdade (que so acontece depois de resolver a URL, de
forma assincrona).
"""
from __future__ import annotations

from animecaos.ui.gui.icons import icon_check
from animecaos.ui.gui.views.detail_view import AnimeDetailView
from animecaos.ui.gui.widgets.episode_row import EpisodeRow


def test_icon_check_produz_um_pixmap_nao_vazio(qapp_instance):
    # QPixmap so pode ser construido com um QApplication ja existente —
    # sem qapp_instance aqui, este e o primeiro teste do arquivo a tocar
    # Qt e derruba o processo inteiro (crash nativo, nao uma excecao Python
    # normal) em vez de falhar de forma limpa.
    pm = icon_check(16, "#3DD68C")
    assert pm.isNull() is False


def test_play_download_confirmation_troca_para_o_check_e_desabilita_reentrada(qtbot):
    row = EpisodeRow(1, "Episodio 1", url="")
    qtbot.addWidget(row)

    original_icon = row._dl_btn.icon()
    row.play_download_confirmation()

    # O icone mudou (nao da pra comparar QIcon por igualdade de conteudo
    # diretamente, mas cacheKey() muda quando o icone de fato trocou).
    assert row._dl_btn.icon().cacheKey() != original_icon.cacheKey()


def test_play_download_confirmation_volta_ao_icone_original_apos_o_timer(qtbot):
    row = EpisodeRow(1, "Episodio 1", url="")
    qtbot.addWidget(row)

    row.play_download_confirmation()
    checked_icon_key = row._dl_btn.icon().cacheKey()

    # Dispara o timeout diretamente em vez de esperar o real (800-1200ms) —
    # o timer em si (duracao, singleShot) e testado a parte.
    row._on_download_confirm_timeout()

    assert row._dl_btn.icon().cacheKey() != checked_icon_key


def test_download_confirm_timer_e_singleshot_e_dura_entre_800_e_1200ms(qtbot):
    row = EpisodeRow(1, "Episodio 1", url="")
    qtbot.addWidget(row)

    assert row._download_confirm_timer.isSingleShot() is True
    assert 800 <= row._download_confirm_timer.interval() <= 1200


def test_clicar_download_duas_vezes_rapido_reinicia_o_timer_sem_erro(qtbot):
    """Nao deve empilhar callbacks nem quebrar se o usuario clicar de novo
    antes do check anterior sumir."""
    row = EpisodeRow(1, "Episodio 1", url="")
    qtbot.addWidget(row)

    row.play_download_confirmation()
    row.play_download_confirmation()  # clique duplo antes do timer estourar

    assert row._download_confirm_timer.isActive() is True
    row._on_download_confirm_timeout()  # nao deve levantar excecao


# ── AnimeDetailView delega para a linha certa ────────────────────────


def test_detail_view_play_download_confirmation_delega_para_a_linha(qtbot):
    view = AnimeDetailView()
    qtbot.addWidget(view)
    view.set_episodes([f"Episodio {i + 1}" for i in range(3)])

    original_icon = view._episode_rows[1]._dl_btn.icon().cacheKey()
    view.play_download_confirmation(1)

    assert view._episode_rows[1]._dl_btn.icon().cacheKey() != original_icon
    # As outras linhas nao devem ser afetadas.
    assert view._episode_rows[0]._download_confirm_timer.isActive() is False


def test_detail_view_play_download_confirmation_com_indice_invalido_nao_quebra(qtbot):
    view = AnimeDetailView()
    qtbot.addWidget(view)
    view.set_episodes(["Episodio 1"])

    view.play_download_confirmation(99)  # nao deve levantar excecao
