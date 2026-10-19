"""
Nova tela de Configuracoes: acessibilidade (zoom da UI), player externo,
pasta/concorrencia de downloads e status de dependencias — tudo num unico
lugar, seguindo o padrao de cards GlassPanel da AccountView existente
(ver animecaos/ui/gui/views/anilist_view.py).

A view nao escreve no ConfigService diretamente: emite sinais que a
MainWindow trata e persiste (mesmo padrao do discord_toggled ->
_on_discord_toggled em main_window.py), o que a mantem testavel sem I/O.
"""
from __future__ import annotations

from animecaos.services.dependency_service import DependencyStatus
from animecaos.ui.gui.scaling import MAX_SCALE
from animecaos.ui.gui.views.settings_view import SettingsView

_DEFAULT_VALUES = {
    "ui_scale": 1.0,
    "player_mode": "mpv",
    "player_path": "",
    "downloads_dir": r"C:\Users\test\Downloads\AnimeCaos",
    "downloads_auto_close": True,
    "downloads_auto_close_delay_ms": 3000,
}


def test_view_carrega_os_valores_passados_na_construcao(qapp_instance):
    values = dict(_DEFAULT_VALUES, ui_scale=1.5)
    view = SettingsView(values=values)

    assert view._scale_slider.value() == 150
    assert view._downloads_dir_edit.text() == values["downloads_dir"]
    assert view._auto_close_checkbox.isChecked() is True


def test_mexer_no_slider_emite_ui_scale_changed_com_valor_clampado(qapp_instance):
    view = SettingsView(values=_DEFAULT_VALUES)

    received: list[float] = []
    view.ui_scale_changed.connect(received.append)

    # O proprio QSlider clampa ao range (100-150) configurado a partir de
    # scaling.MIN_SCALE/MAX_SCALE — um valor absurdo cai no maximo.
    view._scale_slider.setValue(999)

    assert received
    assert received[-1] == MAX_SCALE


def test_escolher_personalizado_habilita_o_campo_de_caminho(qapp_instance):
    view = SettingsView(values=_DEFAULT_VALUES)

    assert view._player_path_edit.isEnabled() is False  # modo padrao e "mpv"
    assert view._player_browse_btn.isEnabled() is False

    view._player_mode_buttons["custom"].setChecked(True)
    assert view._player_path_edit.isEnabled() is True
    assert view._player_browse_btn.isEnabled() is True

    view._player_mode_buttons["mpv"].setChecked(True)
    assert view._player_path_edit.isEnabled() is False
    assert view._player_browse_btn.isEnabled() is False


def test_procurar_player_preenche_o_campo_e_emite_player_changed(qapp_instance, monkeypatch):
    """A UI so tinha o campo de texto pra o modo Personalizado, sem forma
    de abrir um seletor de arquivo — usuario nao sabia como preencher o
    caminho do executavel. Botao "Procurar..." resolve isso."""
    view = SettingsView(values=_DEFAULT_VALUES)
    view._player_mode_buttons["custom"].setChecked(True)

    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        lambda *a, **k: (r"C:\VLC\vlc.exe", ""),
    )

    received: list[tuple[str, str]] = []
    view.player_changed.connect(lambda mode, path: received.append((mode, path)))

    view._on_browse_player_path()

    assert view._player_path_edit.text() == r"C:\VLC\vlc.exe"
    assert received[-1] == ("custom", r"C:\VLC\vlc.exe")


def test_procurar_player_cancelado_nao_altera_nada(qapp_instance, monkeypatch):
    view = SettingsView(values=dict(_DEFAULT_VALUES, player_mode="custom"))
    view._player_path_edit.setText(r"C:\old\path.exe")

    monkeypatch.setattr("PySide6.QtWidgets.QFileDialog.getOpenFileName", lambda *a, **k: ("", ""))

    received: list[tuple[str, str]] = []
    view.player_changed.connect(lambda mode, path: received.append((mode, path)))

    view._on_browse_player_path()

    assert view._player_path_edit.text() == r"C:\old\path.exe"
    assert received == []


def test_selecionar_modo_de_player_emite_player_changed(qapp_instance):
    view = SettingsView(values=_DEFAULT_VALUES)
    received: list[tuple[str, str]] = []
    view.player_changed.connect(lambda mode, path: received.append((mode, path)))

    view._player_mode_buttons["system"].setChecked(True)

    assert received[-1][0] == "system"


def test_dependency_card_mostra_o_install_hint_das_que_faltam(qapp_instance):
    statuses = [
        DependencyStatus(name="mpv", found=False, path=None, required=True, install_hint="Instale com: sudo apt install mpv"),
        DependencyStatus(name="yt-dlp", found=True, path="/usr/bin/yt-dlp", required=True, install_hint="irrelevante"),
    ]
    view = SettingsView(values=_DEFAULT_VALUES, dependency_statuses=statuses)

    assert "sudo apt install mpv" in view._dependency_hint_labels["mpv"].text()
    assert view._dependency_hint_labels["yt-dlp"].text() == ""


def test_botao_verificar_novamente_emite_sinal(qapp_instance):
    view = SettingsView(values=_DEFAULT_VALUES)
    received = []
    view.recheck_dependencies_requested.connect(lambda: received.append(1))

    view._recheck_btn.click()

    assert received == [1]


def test_alternar_auto_fechar_emite_downloads_settings_changed(qapp_instance):
    view = SettingsView(values=_DEFAULT_VALUES)
    received: list[dict] = []
    view.downloads_settings_changed.connect(received.append)

    view._auto_close_checkbox.setChecked(False)

    assert received
    assert received[-1]["downloads_auto_close"] is False


def test_auto_fechar_usa_o_toggle_estilizado_nao_um_qcheckbox_cru(qapp_instance):
    """QCheckBox puro renderia como um quadrado colorido decorativo — a QSS
    global do app nao desenha o glifo de check por cima (ver
    widgets/toggle_checkbox.py). Downloads precisa do mesmo widget que o
    toggle de autoplay do mini-player ja usa."""
    from animecaos.ui.gui.widgets.toggle_checkbox import ToggleCheckbox

    view = SettingsView(values=_DEFAULT_VALUES)
    assert isinstance(view._auto_close_checkbox, ToggleCheckbox)
