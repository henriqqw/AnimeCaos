"""
Bug reportado na build Linux: "Erro ao nao encontrar o MPV instalado" nao
diz o que fazer. play_video() levantava um EnvironmentError com uma frase
seca ("Erro: 'mpv' nao esta instalado ou nao esta no PATH.") sem nenhuma
instrucao de instalacao.

Reaproveita DependencyService (ver tests/test_dependency_service.py) para
compor a mensagem com um hint acionavel e especifico da plataforma do
usuario.
"""
from __future__ import annotations

import pytest

from animecaos.player.video_player import play_video
from animecaos.services.dependency_service import DependencyService


def test_erro_de_mpv_ausente_inclui_o_hint_de_instalacao(monkeypatch):
    expected_hint = DependencyService().check("mpv").install_hint

    # get_bin_path() ja devolve o nome cru quando nao encontra (ver
    # test_dependency_service.py) — simula esse caso apontando para um
    # caminho que garantidamente nao existe, fazendo o subprocess.run()
    # real levantar o FileNotFoundError que play_video() precisa traduzir.
    monkeypatch.setattr(
        "animecaos.player.video_player.get_bin_path",
        lambda name: "/definitely/not/here/mpv-binary-fake",
    )

    with pytest.raises(EnvironmentError) as exc_info:
        play_video("http://example.com/video.m3u8")

    assert expected_hint in str(exc_info.value)
    assert "mpv" in str(exc_info.value).lower()
