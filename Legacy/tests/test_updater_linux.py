"""
Bug real na build Linux (parte do pedido de AppImage com auto-update):
UpdaterService.check_for_updates() so sabia escolher entre .zip e .exe —
num Release com os dois (Windows) MAIS um .AppImage (Linux), o usuario
Linux baixaria o artefato errado (o .zip do Windows). E perform_update()
so sabia escrever um update.bat, que no Linux nao faz nada.

_select_asset() e o que corrige a escolha; perform_update() ganha um
caminho Linux que detecta a variavel de ambiente APPIMAGE (definida pelo
runtime do AppImage), baixa o .AppImage novo NO MESMO DIRETORIO do atual
(para que os.replace() seja atomico — funciona so dentro do mesmo
filesystem) e reinicia via os.execv().
"""
from __future__ import annotations

import os
import sys

import pytest

from animecaos.services.updater_service import UpdaterService, _select_asset


# ── _select_asset ────────────────────────────────────────────────


def _assets(*names: str) -> list[dict]:
    return [{"name": n, "browser_download_url": f"https://x/{n}"} for n in names]


def test_select_asset_escolhe_appimage_no_linux_mesmo_com_zip_e_exe():
    assets = _assets("AnimeCaos_v2.1.0_windows.zip", "AnimeCaos_setup.exe", "AnimeCaos-x86_64.AppImage")
    chosen = _select_asset(assets, "linux")
    assert chosen["name"] == "AnimeCaos-x86_64.AppImage"


def test_select_asset_mantem_prioridade_zip_antes_de_exe_no_windows():
    assets = _assets("AnimeCaos_v2.1.0_windows.zip", "AnimeCaos_setup.exe", "AnimeCaos-x86_64.AppImage")
    chosen = _select_asset(assets, "win32")
    assert chosen["name"] == "AnimeCaos_v2.1.0_windows.zip"


def test_select_asset_cai_em_exe_no_windows_sem_zip():
    assets = _assets("AnimeCaos_setup.exe", "AnimeCaos-x86_64.AppImage")
    chosen = _select_asset(assets, "win32")
    assert chosen["name"] == "AnimeCaos_setup.exe"


def test_select_asset_com_lista_vazia_devolve_none():
    assert _select_asset([], "linux") is None
    assert _select_asset([], "win32") is None


def test_select_asset_linux_sem_appimage_disponivel_devolve_none():
    assets = _assets("AnimeCaos_v2.1.0_windows.zip", "AnimeCaos_setup.exe")
    assert _select_asset(assets, "linux") is None


# ── perform_update (Linux) ───────────────────────────────────────


def test_perform_update_linux_sem_appimage_no_ambiente_nao_faz_nada(monkeypatch):
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")

    svc = UpdaterService()
    svc.download_url = "https://x/AnimeCaos-x86_64.AppImage"
    svc.download_name = "AnimeCaos-x86_64.AppImage"

    calls = []
    monkeypatch.setattr(
        "animecaos.services.updater_service.urllib.request.urlretrieve",
        lambda *a, **k: calls.append(a),
    )

    assert svc.perform_update() is False
    assert calls == []


def test_perform_update_linux_com_appimage_substitui_o_arquivo_e_reinicia(monkeypatch, tmp_path):
    current_appimage = tmp_path / "AnimeCaos-x86_64.AppImage"
    current_appimage.write_bytes(b"old-version-bytes")

    monkeypatch.setenv("APPIMAGE", str(current_appimage))
    monkeypatch.setattr(sys, "platform", "linux")

    svc = UpdaterService()
    svc.download_url = "https://x/AnimeCaos-x86_64.AppImage"
    svc.download_name = "AnimeCaos-x86_64.AppImage"

    def fake_urlretrieve(url, path, reporthook=None):
        # Simula o download escrevendo bytes "novos" no destino esperado.
        with open(path, "wb") as f:
            f.write(b"new-version-bytes")
        return (str(path), None)

    exec_calls = []

    def fake_execv(path, argv):
        exec_calls.append((path, argv))

    monkeypatch.setattr("animecaos.services.updater_service.urllib.request.urlretrieve", fake_urlretrieve)
    monkeypatch.setattr("animecaos.services.updater_service.os.execv", fake_execv)

    result = svc.perform_update()

    assert result is True
    assert current_appimage.read_bytes() == b"new-version-bytes"
    if os.name != "nt":
        # Bit de execucao so faz sentido fora do Windows — os.chmod() no
        # Windows nao tem esse conceito da mesma forma.
        assert os.access(current_appimage, os.X_OK)
    assert exec_calls == [(str(current_appimage), [str(current_appimage)])]


# ── regressao ────────────────────────────────────────────────────


def test_is_newer_version_continua_correto():
    svc = UpdaterService()
    assert svc._is_newer_version("2.1.0", "2.0.0") is True
    assert svc._is_newer_version("2.0.0", "2.0.0") is False
    assert svc._is_newer_version("2.0.0", "2.1.0") is False
