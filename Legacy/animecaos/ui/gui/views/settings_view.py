"""Settings screen: UI scale (accessibility), player, downloads and
dependency status — one place for the preferences that used to have nowhere
to live (the app only had the AniList account screen before this).

The view never touches ConfigService directly. Every control change is
emitted as a signal that MainWindow listens to and persists — the same
pattern the existing discord_toggled -> _on_discord_toggled already uses in
main_window.py — which keeps this view testable without any I/O.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from animecaos.services.dependency_service import DependencyStatus
from animecaos.ui.gui.widgets.accent_slider import AccentSlider
from animecaos.ui.gui.widgets.animated_button import AnimatedButton
from animecaos.ui.gui.widgets.toggle_checkbox import ToggleCheckbox
from animecaos.ui.gui.scaling import MAX_SCALE, MIN_SCALE

_PLAYER_MODES = (("mpv", "mpv"), ("system", "Sistema"), ("custom", "Personalizado"))


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("GlassPanel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(14)
    return frame, layout


def _card_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-size: 15px; font-weight: 700; color: #F2F3F5;")
    return label


class SettingsView(QWidget):
    """Preferences screen: appearance, player, downloads and dependencies."""

    ui_scale_changed = Signal(float)
    restart_requested = Signal()
    player_changed = Signal(str, str)  # (mode, path)
    downloads_settings_changed = Signal(dict)
    recheck_dependencies_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        values: dict | None = None,
        dependency_statuses: list[DependencyStatus] | None = None,
    ) -> None:
        super().__init__(parent)
        self._values = dict(values or {})
        self._dependency_hint_labels: dict[str, QLabel] = {}
        self._dependency_status_dots: dict[str, QLabel] = {}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(16)

        title = QLabel("Configuracoes")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #F2F3F5;")
        outer.addWidget(title)

        outer.addWidget(self._build_appearance_card())
        outer.addWidget(self._build_player_card())
        outer.addWidget(self._build_downloads_card())
        outer.addWidget(self._build_dependencies_card())
        outer.addStretch()

        scroll.setWidget(inner)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        if dependency_statuses is not None:
            self.set_dependency_statuses(dependency_statuses)

    # ── Appearance ───────────────────────────────────────────────

    def _build_appearance_card(self) -> QFrame:
        card, layout = _card()
        layout.addWidget(_card_title("Aparencia"))

        sub = QLabel("Aumenta o tamanho de fontes e da interface. Requer reiniciar o app.")
        sub.setWordWrap(True)
        sub.setStyleSheet("font-size: 12px; color: #A7ACB5;")
        layout.addWidget(sub)

        row = QHBoxLayout()
        self._scale_slider = AccentSlider()
        self._scale_slider.setRange(int(MIN_SCALE * 100), int(MAX_SCALE * 100))
        self._scale_slider.setSingleStep(5)
        self._scale_slider.setValue(int(float(self._values.get("ui_scale", 1.0)) * 100))
        self._scale_slider.valueChanged.connect(self._on_scale_changed)
        row.addWidget(self._scale_slider, 1)

        self._scale_value_lbl = QLabel(f"{self._scale_slider.value()}%")
        self._scale_value_lbl.setFixedWidth(48)
        row.addWidget(self._scale_value_lbl)
        layout.addLayout(row)

        self._restart_btn = AnimatedButton("Aplicar e reiniciar")
        self._restart_btn.clicked.connect(self.restart_requested.emit)
        layout.addWidget(self._restart_btn, 0, Qt.AlignmentFlag.AlignLeft)

        return card

    def _on_scale_changed(self, raw_value: int) -> None:
        scale = raw_value / 100.0
        self._scale_value_lbl.setText(f"{raw_value}%")
        self.ui_scale_changed.emit(scale)

    # ── Player ───────────────────────────────────────────────────

    def _build_player_card(self) -> QFrame:
        card, layout = _card()
        layout.addWidget(_card_title("Player"))

        sub = QLabel(
            "O mpv ja vem incluido no instalador — na maioria dos casos voce nao precisa "
            "mexer aqui. 'Personalizado' e so para quem prefere abrir os episodios em outro "
            "player (ex.: VLC). Fora do mpv, autoplay e sincronizacao com o AniList nao "
            "funcionam — o player externo nao informa quando o video termina."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("font-size: 12px; color: #A7ACB5;")
        layout.addWidget(sub)

        mode_row = QHBoxLayout()
        self._player_mode_buttons: dict[str, QRadioButton] = {}
        self._player_mode_group = QButtonGroup(self)
        self._player_mode_group.setExclusive(True)
        current_mode = self._values.get("player_mode", "mpv")
        for key, label in _PLAYER_MODES:
            btn = QRadioButton(label)
            btn.setChecked(key == current_mode)
            btn.toggled.connect(lambda checked, k=key: checked and self._on_player_mode_changed(k))
            self._player_mode_group.addButton(btn)
            self._player_mode_buttons[key] = btn
            mode_row.addWidget(btn)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        path_row = QHBoxLayout()
        self._player_path_edit = QLineEdit(self._values.get("player_path", ""))
        self._player_path_edit.setPlaceholderText(r"Caminho do executavel (ex.: C:\VLC\vlc.exe)")
        self._player_path_edit.setEnabled(current_mode == "custom")
        self._player_path_edit.editingFinished.connect(self._on_player_path_edited)
        path_row.addWidget(self._player_path_edit, 1)

        self._player_browse_btn = QPushButton("Procurar...")
        self._player_browse_btn.setEnabled(current_mode == "custom")
        self._player_browse_btn.clicked.connect(self._on_browse_player_path)
        path_row.addWidget(self._player_browse_btn)
        layout.addLayout(path_row)

        return card

    def _on_player_mode_changed(self, mode: str) -> None:
        is_custom = mode == "custom"
        self._player_path_edit.setEnabled(is_custom)
        self._player_browse_btn.setEnabled(is_custom)
        self.player_changed.emit(mode, self._player_path_edit.text())

    def _on_player_path_edited(self) -> None:
        mode = self._current_player_mode()
        self.player_changed.emit(mode, self._player_path_edit.text())

    def _on_browse_player_path(self) -> None:
        import sys as _sys

        from PySide6.QtWidgets import QFileDialog

        file_filter = "Executaveis (*.exe)" if _sys.platform == "win32" else "Todos os arquivos (*)"
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Escolha o executavel do player", self._player_path_edit.text(), file_filter
        )
        if chosen:
            self._player_path_edit.setText(chosen)
            self.player_changed.emit(self._current_player_mode(), chosen)

    def _current_player_mode(self) -> str:
        for key, btn in self._player_mode_buttons.items():
            if btn.isChecked():
                return key
        return "mpv"

    # ── Downloads ────────────────────────────────────────────────

    def _build_downloads_card(self) -> QFrame:
        card, layout = _card()
        layout.addWidget(_card_title("Downloads"))

        dir_row = QHBoxLayout()
        self._downloads_dir_edit = QLineEdit(self._values.get("downloads_dir", ""))
        self._downloads_dir_edit.editingFinished.connect(self._emit_downloads_settings)
        dir_row.addWidget(self._downloads_dir_edit, 1)
        browse_btn = QPushButton("Procurar...")
        browse_btn.clicked.connect(self._on_browse_downloads_dir)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)

        self._auto_close_checkbox = ToggleCheckbox(
            "Fechar automaticamente ao concluir todos os downloads",
            checked=bool(self._values.get("downloads_auto_close", True)),
        )
        self._auto_close_checkbox.toggled.connect(lambda _v: self._emit_downloads_settings())
        layout.addWidget(self._auto_close_checkbox)

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Atraso antes de fechar (segundos):"))
        self._auto_close_delay_spin = QSpinBox()
        self._auto_close_delay_spin.setRange(0, 60)
        self._auto_close_delay_spin.setValue(
            int(self._values.get("downloads_auto_close_delay_ms", 3000)) // 1000
        )
        self._auto_close_delay_spin.valueChanged.connect(lambda _v: self._emit_downloads_settings())
        delay_row.addWidget(self._auto_close_delay_spin)
        delay_row.addStretch()
        layout.addLayout(delay_row)

        return card

    def _on_browse_downloads_dir(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        chosen = QFileDialog.getExistingDirectory(self, "Escolha a pasta de downloads", self._downloads_dir_edit.text())
        if chosen:
            self._downloads_dir_edit.setText(chosen)
            self._emit_downloads_settings()

    def _emit_downloads_settings(self) -> None:
        self.downloads_settings_changed.emit(
            {
                "downloads_dir": self._downloads_dir_edit.text(),
                "downloads_auto_close": self._auto_close_checkbox.isChecked(),
                "downloads_auto_close_delay_ms": self._auto_close_delay_spin.value() * 1000,
            }
        )

    # ── Dependencies ─────────────────────────────────────────────

    def _build_dependencies_card(self) -> QFrame:
        card, layout = _card()
        header_row = QHBoxLayout()
        header_row.addWidget(_card_title("Dependencias"))
        header_row.addStretch()
        self._recheck_btn = QPushButton("Verificar novamente")
        self._recheck_btn.clicked.connect(self.recheck_dependencies_requested.emit)
        header_row.addWidget(self._recheck_btn)
        layout.addLayout(header_row)

        self._dependencies_rows_layout = QVBoxLayout()
        self._dependencies_rows_layout.setSpacing(6)
        layout.addLayout(self._dependencies_rows_layout)

        return card

    def set_dependency_statuses(self, statuses: list[DependencyStatus]) -> None:
        while self._dependencies_rows_layout.count():
            item = self._dependencies_rows_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._dependency_hint_labels.clear()
        self._dependency_status_dots.clear()

        for status in statuses:
            row = QHBoxLayout()
            dot = QLabel("\u25cf")
            dot.setStyleSheet(f"color: {'#3DD68C' if status.found else '#D46432'}; font-size: 12px;")
            row.addWidget(dot)
            self._dependency_status_dots[status.name] = dot

            name_lbl = QLabel(status.name)
            name_lbl.setStyleSheet("font-size: 12px; color: #E6E7EA;")
            name_lbl.setFixedWidth(80)
            row.addWidget(name_lbl)

            hint_lbl = QLabel("" if status.found else status.install_hint)
            hint_lbl.setWordWrap(True)
            hint_lbl.setStyleSheet("font-size: 11px; color: #A7ACB5;")
            row.addWidget(hint_lbl, 1)
            self._dependency_hint_labels[status.name] = hint_lbl

            row_widget = QWidget()
            row_widget.setLayout(row)
            self._dependencies_rows_layout.addWidget(row_widget)

    # ── Values ───────────────────────────────────────────────────

    def set_values(self, values: dict) -> None:
        """Repopulates every control from a fresh values dict — used when
        the user navigates back into Settings after changing something
        elsewhere (e.g. downloads folder migrated)."""
        self._values = dict(values)
        self._scale_slider.setValue(int(float(values.get("ui_scale", 1.0)) * 100))
        mode = values.get("player_mode", "mpv")
        if mode in self._player_mode_buttons:
            self._player_mode_buttons[mode].setChecked(True)
        self._player_path_edit.setText(values.get("player_path", ""))
        self._player_path_edit.setEnabled(mode == "custom")
        self._player_browse_btn.setEnabled(mode == "custom")
        self._downloads_dir_edit.setText(values.get("downloads_dir", ""))
        self._auto_close_checkbox.setChecked(bool(values.get("downloads_auto_close", True)))
        self._auto_close_delay_spin.setValue(int(values.get("downloads_auto_close_delay_ms", 3000)) // 1000)
