"""
Bug reportado na build Linux: o icone que aparece na barra de tarefas e na
barra de titulo e o generico do Wayland, nao o do AnimeCaos.

Causa raiz: sob Wayland o compositor casa a janela com o arquivo .desktop
pelo app_id, que o Qt tira de QGuiApplication.setDesktopFileName() — nunca
chamado neste app. Sem app_id o compositor cai no icone padrao.

Um segundo problema, adjacente: a resolucao do caminho do icone
(get_base_path() -> os.path.abspath(".") quando nao empacotado) depende do
diretorio de trabalho atual. Isso e exatamente o caso de um lancador
.desktop, que normalmente inicia o processo com um cwd arbitrario (nao a
raiz do projeto) — entao mesmo com o app_id certo, o icone poderia nao ser
encontrado.
"""
from __future__ import annotations

import sys

from animecaos.core.paths import get_base_path, resolve_icon_path


def test_resolve_icon_path_existe_rodando_do_repo():
    path = resolve_icon_path()
    import os
    assert os.path.exists(path), f"icone nao encontrado em {path!r}"


def test_resolve_icon_path_usa_meipass_quando_empacotado(monkeypatch, tmp_path):
    fake_meipass = tmp_path / "meipass"
    (fake_meipass / "public").mkdir(parents=True)
    icon_file = fake_meipass / "public" / "icon.png"
    icon_file.write_bytes(b"fake-png-bytes")

    monkeypatch.setattr(sys, "_MEIPASS", str(fake_meipass), raising=False)

    assert resolve_icon_path() == str(icon_file)


def test_resolve_icon_path_nao_depende_do_cwd(monkeypatch, tmp_path):
    """Um lancador .desktop pode iniciar o processo com qualquer cwd —
    resolver o icone nao pode depender dele."""
    monkeypatch.chdir(tmp_path)
    path = resolve_icon_path()
    import os
    assert os.path.exists(path)


def test_get_base_path_nao_depende_do_cwd_quando_nao_empacotado(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    base = get_base_path()
    assert (base / "public").exists()
    assert (base / "animecaos").exists()


# ── .desktop / app_id ───────────────────────────────────────────────


def test_desktop_file_declara_startup_wm_class():
    from pathlib import Path

    desktop_path = Path(__file__).resolve().parent.parent / "deploy" / "com.animecaos.App.desktop"
    text = desktop_path.read_text(encoding="utf-8")
    assert "StartupWMClass=com.animecaos.App" in text


def test_startup_wm_class_casa_com_o_desktop_file_name_usado_no_app():
    """O valor passado a setDesktopFileName() (ver animecaos/ui/gui/app.py)
    precisa ser exatamente o mesmo id declarado no StartupWMClass do
    .desktop — e o casamento entre os dois que corrige o icone no Wayland."""
    from pathlib import Path

    import animecaos.ui.gui.app as app_module

    source = Path(app_module.__file__).read_text(encoding="utf-8")
    assert 'setDesktopFileName("com.animecaos.App")' in source

    desktop_path = Path(__file__).resolve().parent.parent / "deploy" / "com.animecaos.App.desktop"
    assert "StartupWMClass=com.animecaos.App" in desktop_path.read_text(encoding="utf-8")
