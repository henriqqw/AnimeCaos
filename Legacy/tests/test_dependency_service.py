"""
Correcao sugerida: avisar quando um player de video ou outras dependencias
nao forem detectadas. Cobre tambem o bug reportado na build Linux — "Erro ao
nao encontrar o MPV instalado" — sem nenhuma instrucao de como resolver.

Bug de raiz em get_bin_path(): quando o binario nao e encontrado, a funcao
devolve o proprio NOME do binario (`return binary_name`) em vez de None —
entao nenhum chamador consegue distinguir "achei" de "nao achei". O erro so
aparecia la na frente, como um FileNotFoundError cru do subprocess, sem
contexto nenhum para o usuario. find_binary() e o que corrige isso; get_bin_path()
continua existindo (varios chamadores dependem do fallback para o nome cru)
mas agora e so uma casca fina sobre find_binary().
"""
from __future__ import annotations

import sys

import pytest

from animecaos.core.paths import find_binary, get_bin_path
from animecaos.services.dependency_service import DependencyService


# ── find_binary / get_bin_path ────────────────────────────────────


def test_find_binary_acha_binario_no_bundle(monkeypatch, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    binary_name = "mpv.exe" if sys.platform == "win32" else "mpv"
    planted = bin_dir / binary_name
    planted.write_bytes(b"fake-binary")

    monkeypatch.setattr("animecaos.core.paths.get_base_path", lambda: tmp_path)

    assert find_binary("mpv") == str(planted)


def test_find_binary_de_algo_inexistente_devolve_none(monkeypatch, tmp_path):
    monkeypatch.setattr("animecaos.core.paths.get_base_path", lambda: tmp_path)
    monkeypatch.setattr("shutil.which", lambda name: None)

    assert find_binary("naoexiste-xyz-binario-fake") is None


def test_get_bin_path_continua_devolvendo_o_nome_cru_quando_nao_encontra(monkeypatch, tmp_path):
    """Regressao: chamadores existentes (DownloadWorker, video_player, ...)
    dependem desse fallback para deixar o subprocess levantar
    FileNotFoundError do jeito que ja levantava antes desta mudanca."""
    monkeypatch.setattr("animecaos.core.paths.get_base_path", lambda: tmp_path)
    monkeypatch.setattr("shutil.which", lambda name: None)

    assert get_bin_path("naoexiste-xyz-binario-fake") == "naoexiste-xyz-binario-fake"


def test_get_bin_path_devolve_o_caminho_quando_encontra(monkeypatch, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    binary_name = "yt-dlp.exe" if sys.platform == "win32" else "yt-dlp"
    planted = bin_dir / binary_name
    planted.write_bytes(b"fake-binary")
    monkeypatch.setattr("animecaos.core.paths.get_base_path", lambda: tmp_path)

    assert get_bin_path("yt-dlp") == str(planted)


# ── DependencyService ──────────────────────────────────────────────


def _finder_not_found(_name: str) -> str | None:
    return None


def _finder_found(name: str) -> str | None:
    return f"/fake/bin/{name}"


def test_check_marca_found_true_quando_o_finder_acha():
    service = DependencyService(finder=_finder_found, platform="linux")
    status = service.check("mpv")
    assert status.found is True
    assert status.path == "/fake/bin/mpv"


def test_check_marca_found_false_e_um_hint_nao_vazio_quando_nao_acha():
    service = DependencyService(finder=_finder_not_found, platform="linux")
    status = service.check("mpv")
    assert status.found is False
    assert status.path is None
    assert status.install_hint.strip() != ""


def test_install_hint_difere_entre_linux_e_windows():
    linux_hint = DependencyService(finder=_finder_not_found, platform="linux").check("mpv").install_hint
    windows_hint = DependencyService(finder=_finder_not_found, platform="win32").check("mpv").install_hint
    assert linux_hint != windows_hint


def test_check_all_cobre_mpv_yt_dlp_e_geckodriver():
    service = DependencyService(finder=_finder_found, platform="linux")
    names = {status.name for status in service.check_all()}
    assert {"mpv", "yt-dlp", "geckodriver"} <= names


def test_missing_required_ignora_dependencias_opcionais():
    """geckodriver so e usado por um plugin de scraping — nao deve gerar o
    mesmo alarme bloqueante que o mpv (sem o qual nada toca)."""
    service = DependencyService(finder=_finder_not_found, platform="linux")
    missing = service.missing_required()
    missing_names = {d.name for d in missing}
    assert "mpv" in missing_names
    assert "geckodriver" not in missing_names


def test_missing_required_fica_vazio_quando_tudo_e_encontrado():
    service = DependencyService(finder=_finder_found, platform="linux")
    assert service.missing_required() == []


def test_mpv_e_obrigatorio_yt_dlp_e_obrigatorio():
    service = DependencyService(finder=_finder_not_found, platform="linux")
    by_name = {d.name: d for d in service.check_all()}
    assert by_name["mpv"].required is True
    assert by_name["yt-dlp"].required is True
    assert by_name["geckodriver"].required is False
