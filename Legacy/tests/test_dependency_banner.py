"""
Correcao sugerida: avisar quando um player de video ou outras dependencias
nao forem detectadas — em vez de deixar o usuario descobrir sozinho quando
o play falha.

Reaproveita o padrao ja existente do banner "AniList offline" na HomeView
(_AniListOfflineBanner + show_anilist_offline_banner/hide_anilist_offline_banner)
para um segundo aviso, independente, sobre dependencias ausentes (mpv,
yt-dlp). MainWindow consulta DependencyService.missing_required() na
inicializacao e decide se mostra o banner.
"""
from __future__ import annotations

from animecaos.services.dependency_service import DependencyStatus
from animecaos.ui.gui.views.home_view import HomeView


def test_dependency_banner_comeca_escondido(qapp_instance):
    # HomeView aqui e um widget solto, sem uma janela de topo mostrada, entao
    # isVisible() seria sempre False independente do estado do banner —
    # isHidden() reflete a flag de visibilidade do proprio widget, nao da
    # cadeia de ancestrais (mesma convencao usada em
    # tests/test_anime_card_hover_preview.py).
    view = HomeView()
    assert view._dependency_banner.isHidden() is True


def test_show_dependency_banner_exibe_titulo_e_descricao(qapp_instance):
    view = HomeView()
    view.show_dependency_banner("Dependencia ausente: mpv", "Instale com: sudo apt install mpv")
    assert view._dependency_banner.isHidden() is False
    assert view._dependency_banner._title_lbl.text() == "Dependencia ausente: mpv"
    assert "sudo apt install mpv" in view._dependency_banner._desc_lbl.text()


def test_hide_dependency_banner_esconde(qapp_instance):
    view = HomeView()
    view.show_dependency_banner("x", "y")
    view.hide_dependency_banner()
    assert view._dependency_banner.isHidden() is True


# ── integracao com MainWindow ──────────────────────────────────────


class _FakeDependencyService:
    def __init__(self, missing: list[DependencyStatus]) -> None:
        self._missing = missing

    def missing_required(self) -> list[DependencyStatus]:
        return self._missing

    def check_all(self) -> list[DependencyStatus]:
        # SettingsView's dependency card also queries this at MainWindow
        # construction time — the missing set doubles as "everything we
        # know about" since these tests don't care about the found ones.
        return self._missing


def test_main_window_mostra_o_banner_quando_falta_dependencia_obrigatoria(main_window_factory):
    missing = [
        DependencyStatus(
            name="mpv", found=False, path=None, required=True,
            install_hint="Instale com: sudo apt install mpv",
        )
    ]
    window = main_window_factory(dependency_service=_FakeDependencyService(missing))
    assert window._home_view._dependency_banner.isVisible() is True
    assert "mpv" in window._home_view._dependency_banner._title_lbl.text()
    assert "sudo apt install mpv" in window._home_view._dependency_banner._desc_lbl.text()


def test_main_window_nao_mostra_o_banner_quando_tudo_presente(main_window_factory):
    window = main_window_factory(dependency_service=_FakeDependencyService([]))
    assert window._home_view._dependency_banner.isVisible() is False
