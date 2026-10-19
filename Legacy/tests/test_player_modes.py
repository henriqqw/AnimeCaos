"""
Sugestao de usuario: permitir a execucao dos animes num player padrao ja
instalado, em vez de depender exclusivamente do mpv.

video_player.play_video() ganha um modo de reproducao ("mpv" | "system" |
"custom") mantendo compatibilidade retroativa: play_video(url) e
play_video(url, debug) continuam funcionando exatamente como antes (modo
"mpv" e o padrao).

Tradeoff que a UI precisa deixar claro (ver settings_view.py): fora do mpv
nao existe o log de saida que _detect_natural_eof() le, entao autoplay e a
sincronizacao de progresso com o AniList dependem de eof=True/watched>=30s
que os modos "system"/"custom" nunca fornecem da mesma forma.
"""
from __future__ import annotations

import sys

import pytest

from animecaos.player.video_player import build_player_command, play_video


# ── build_player_command ────────────────────────────────────────────


def test_modo_mpv_mantem_as_flags_atuais():
    cmd = build_player_command("https://example.com/video.m3u8", mode="mpv")
    assert "--ontop" in cmd
    assert "--hls-bitrate=max" in cmd
    assert any(c.endswith("mpv") or c.endswith("mpv.exe") for c in cmd[:1] + [cmd[0]])


def test_modo_mpv_e_o_padrao_quando_nenhum_modo_e_passado():
    assert build_player_command("https://example.com/video.m3u8") == build_player_command(
        "https://example.com/video.m3u8", mode="mpv"
    )


def test_modo_custom_monta_o_comando_com_o_caminho_do_player():
    cmd = build_player_command("C:/videos/ep1.mp4", mode="custom", player_path="C:/VLC/vlc.exe")
    assert cmd == ["C:/VLC/vlc.exe", "C:/videos/ep1.mp4"]


def test_modo_custom_sem_player_path_levanta_erro_claro():
    with pytest.raises(ValueError, match="[Pp]layer personalizado"):
        build_player_command("C:/videos/ep1.mp4", mode="custom", player_path=None)


def test_modo_system_no_linux_usa_xdg_open(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    cmd = build_player_command("/home/user/ep1.mp4", mode="system")
    assert cmd == ["xdg-open", "/home/user/ep1.mp4"]


def test_modo_system_no_macos_usa_open(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    cmd = build_player_command("/Users/user/ep1.mp4", mode="system")
    assert cmd == ["open", "/Users/user/ep1.mp4"]


def test_modo_desconhecido_levanta_erro():
    with pytest.raises(ValueError):
        build_player_command("x", mode="nao-existe")


# ── play_video ───────────────────────────────────────────────────


def test_play_video_sem_argumentos_novos_continua_usando_mpv(monkeypatch):
    """Regressao: chamadores existentes (AnimeService.play_url, cli/app.py)
    passam so (url) ou (url, debug) — precisam continuar funcionando."""
    captured_cmd: list[list[str]] = []

    class _FakeResult:
        returncode = 0

    def fake_run(cmd, **kwargs):
        captured_cmd.append(cmd)
        return _FakeResult()

    monkeypatch.setattr("animecaos.player.video_player.subprocess.run", fake_run)

    result = play_video("https://example.com/video.m3u8")

    assert captured_cmd, "subprocess.run nao foi chamado"
    assert any("--hls-bitrate=max" in c for c in captured_cmd[0])
    assert result == {"eof": False, "watched": False}


def test_play_video_modo_system_dispara_e_nao_espera(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    popen_calls: list[list[str]] = []

    class _FakeProcess:
        pass

    def fake_popen(cmd, **kwargs):
        popen_calls.append(cmd)
        return _FakeProcess()

    monkeypatch.setattr("animecaos.player.video_player.subprocess.Popen", fake_popen)

    result = play_video("https://example.com/video.m3u8", mode="system")

    assert popen_calls == [["xdg-open", "https://example.com/video.m3u8"]]
    # autoplay so deve avancar em EOF natural do mpv — modo system nunca
    # fornece esse sinal, entao tem que vir sempre False.
    assert result == {"eof": False, "watched": False}


def test_play_video_modo_custom_watched_false_quando_processo_e_rapido(monkeypatch, tmp_path):
    called = {}

    class _FakeResult:
        returncode = 0

    def fake_run(cmd, **kwargs):
        called["cmd"] = cmd
        return _FakeResult()

    monkeypatch.setattr("animecaos.player.video_player.subprocess.run", fake_run)
    monkeypatch.setattr("animecaos.player.video_player.time.monotonic", _fast_clock())

    result = play_video(
        "https://example.com/video.m3u8",
        mode="custom",
        player_path="/opt/vlc/vlc",
    )

    assert called["cmd"] == ["/opt/vlc/vlc", "https://example.com/video.m3u8"]
    assert result == {"eof": False, "watched": False}


def _fast_clock():
    """Returns a monotonic() stand-in whose successive calls report 0s
    elapsed, so tests don't depend on real wall-clock timing."""
    ticks = iter([0.0, 0.0])

    def _clock():
        return next(ticks, 0.0)

    return _clock


def test_play_video_modo_custom_watched_true_quando_processo_demora(monkeypatch):
    class _FakeResult:
        returncode = 0

    monkeypatch.setattr("animecaos.player.video_player.subprocess.run", lambda cmd, **kw: _FakeResult())
    ticks = iter([0.0, 45.0])
    monkeypatch.setattr("animecaos.player.video_player.time.monotonic", lambda: next(ticks))

    result = play_video("https://example.com/video.m3u8", mode="custom", player_path="/opt/vlc/vlc")

    assert result["eof"] is False
    assert result["watched"] is True
