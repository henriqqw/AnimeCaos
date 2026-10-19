"""
Integracao: clicar na engrenagem da sidebar leva a tela de Configuracoes
(espelha o padrao de test_sidebar_list_nav.py + a navegacao de Conta em
main_window.py), e cada sinal da SettingsView e persistido na chave certa
do ConfigService (mesmo padrao do discord_toggled -> _on_discord_toggled).
"""
from __future__ import annotations

from animecaos.services.dependency_service import DependencyStatus
from animecaos.ui.gui.main_window import MainWindow


def _settings_view_index(window) -> int:
    return window._stack.indexOf(window._settings_view)


def test_settings_view_is_registered_in_the_stack(main_window_factory):
    window = main_window_factory()
    assert _settings_view_index(window) != -1


def test_clicking_settings_sidebar_button_navigates_to_settings_view(main_window_factory, qtbot):
    window = main_window_factory()
    window._sidebar._buttons["settings"].click()

    # AnimatedStackedWidget.slide_to() only calls setCurrentIndex() once its
    # ~200ms fade animation finishes (see animated_stack.py) — not
    # synchronously on click.
    qtbot.waitUntil(lambda: window._stack.currentIndex() == _settings_view_index(window), timeout=1000)
    assert window._sidebar._buttons["settings"].isChecked()


def test_ui_scale_changed_persists_to_config(main_window_factory):
    window = main_window_factory()
    window._settings_view.ui_scale_changed.emit(1.5)
    assert window._config_service.get("ui_scale") == 1.5


def test_player_changed_persists_mode_and_path(main_window_factory):
    window = main_window_factory()
    window._settings_view.player_changed.emit("custom", r"C:\VLC\vlc.exe")
    assert window._config_service.get("player_mode") == "custom"
    assert window._config_service.get("player_path") == r"C:\VLC\vlc.exe"


def test_downloads_settings_changed_persists_every_key(main_window_factory):
    window = main_window_factory()
    payload = {
        "downloads_dir": r"D:\Anime",
        "downloads_auto_close": False,
        "downloads_auto_close_delay_ms": 5000,
    }
    window._settings_view.downloads_settings_changed.emit(payload)
    for key, value in payload.items():
        assert window._config_service.get(key) == value


def test_recheck_dependencies_refreshes_the_settings_card(main_window_factory):
    window = main_window_factory(
        dependency_service=_FakeDependencyService([
            DependencyStatus(name="mpv", found=False, path=None, required=True, install_hint="instale mpv"),
        ])
    )
    window._settings_view.recheck_dependencies_requested.emit()
    assert "instale mpv" in window._settings_view._dependency_hint_labels["mpv"].text()


class _FakeDependencyService:
    def __init__(self, statuses: list[DependencyStatus]) -> None:
        self._statuses = statuses

    def check_all(self) -> list[DependencyStatus]:
        return self._statuses

    def missing_required(self) -> list[DependencyStatus]:
        return [s for s in self._statuses if s.required and not s.found]
