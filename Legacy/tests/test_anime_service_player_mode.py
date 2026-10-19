"""
AnimeService.play_url() precisa repassar o modo de player (mpv/sistema/
personalizado) e o caminho do executavel para video_player.play_video() —
ambos lidos do ConfigService pela MainWindow e passados por parametro aqui,
mantendo o AnimeService sem estado de configuracao proprio.

Continua funcionando sem argumentos novos (play_url(url) sozinho), que e
como o resto do app ainda o chama fora dos pontos atualizados nesta feature.
"""
from __future__ import annotations

from animecaos.services.anime_service import AnimeService


def test_play_url_sem_argumentos_novos_usa_mpv_por_padrao(monkeypatch):
    captured = {}

    def fake_play_video(url, debug=False, mode="mpv", player_path=None):
        captured.update(url=url, debug=debug, mode=mode, player_path=player_path)
        return {"eof": True, "watched": True}

    monkeypatch.setattr("animecaos.services.anime_service.play_video", fake_play_video)

    service = AnimeService(debug=False)
    result = service.play_url("https://example.com/video.m3u8")

    assert captured == {
        "url": "https://example.com/video.m3u8",
        "debug": False,
        "mode": "mpv",
        "player_path": None,
    }
    assert result == {"eof": True, "watched": True}


def test_play_url_repassa_modo_e_caminho_personalizados(monkeypatch):
    captured = {}

    def fake_play_video(url, debug=False, mode="mpv", player_path=None):
        captured.update(mode=mode, player_path=player_path)
        return {"eof": False, "watched": False}

    monkeypatch.setattr("animecaos.services.anime_service.play_video", fake_play_video)

    service = AnimeService(debug=False)
    service.play_url("https://example.com/video.m3u8", mode="custom", player_path="/opt/vlc/vlc")

    assert captured == {"mode": "custom", "player_path": "/opt/vlc/vlc"}
