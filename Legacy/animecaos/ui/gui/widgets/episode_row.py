from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QCheckBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from animecaos.ui.gui.icons import icon_check, icon_download, icon_play
from animecaos.ui.gui.widgets.loading_spinner import LoadingSpinner


class EpisodeRow(QFrame):
    """Episode list row component."""

    play_clicked = Signal(str, str)
    download_clicked = Signal(str, str)
    # Emitted whenever this row's checkbox toggles, while in selection mode
    # (see set_selectable) — lets AnimeDetailView recompute the selected count.
    selection_changed = Signal()

    _DOWNLOAD_CONFIRM_MS = 1000

    def __init__(
        self,
        number: int,
        title: str,
        url: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("EpisodeRow")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(44)
        self.url = url
        self.title = title
        self.number = number

        self._anim_effect: QGraphicsOpacityEffect | None = None
        self._anim: QPropertyAnimation | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)

        self._selectable = False
        self._checkbox = QCheckBox()
        self._checkbox.setVisible(False)
        self._checkbox.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._checkbox.toggled.connect(self._on_checkbox_toggled)
        layout.addWidget(self._checkbox)

        self._num_label = QLabel(f"{number:02d}")
        self._num_label.setFixedWidth(32)
        self._num_label.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #A7ACB5;"
        )
        layout.addWidget(self._num_label)

        self._title_label = QLabel(title)
        self._title_label.setWordWrap(False)
        self._title_label.setStyleSheet("font-size: 13px; color: #E6E7EA;")
        layout.addWidget(self._title_label, 1)

        self._loading_lbl = QLabel("Carregando…")
        self._loading_lbl.setObjectName("MutedText")
        self._loading_lbl.setStyleSheet("font-size: 11px; color: #A7ACB5;")
        self._loading_lbl.setVisible(False)
        layout.addWidget(self._loading_lbl)

        self._play_btn = QPushButton()
        self._play_btn.setFixedSize(32, 32)
        self._play_btn.setIcon(icon_play(16, "#FFFFFF"))
        self._play_btn.setToolTip("Assistir episódio")
        self._play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._play_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.08); border-radius: 6px; border: none; }"
            "QPushButton:hover { background: rgba(255,255,255,0.18); }"
        )
        self._play_btn.clicked.connect(lambda: self.play_clicked.emit(self.title, self.url))
        layout.addWidget(self._play_btn)

        self._spinner = LoadingSpinner(26)
        self._spinner.setVisible(False)
        layout.addWidget(self._spinner)

        self._dl_btn = QPushButton()
        self._dl_btn.setFixedSize(32, 32)
        self._dl_btn.setIcon(icon_download(16, "#A7ACB5"))
        self._dl_btn.setToolTip("Baixar episódio")
        self._dl_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._dl_btn.setStyleSheet(
            "QPushButton { background: transparent; border-radius: 6px; border: none; }"
            "QPushButton:hover { background: rgba(255,255,255,0.1); }"
        )
        self._dl_btn.clicked.connect(lambda: self.download_clicked.emit(self.title, self.url))
        layout.addWidget(self._dl_btn)

        self._loading = False

        self._dl_btn_effect: QGraphicsOpacityEffect | None = None
        self._dl_btn_anim: QPropertyAnimation | None = None
        self._download_confirm_timer = QTimer(self)
        self._download_confirm_timer.setSingleShot(True)
        self._download_confirm_timer.setInterval(self._DOWNLOAD_CONFIRM_MS)
        self._download_confirm_timer.timeout.connect(self._on_download_confirm_timeout)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._selectable:
                self._checkbox.setChecked(not self._checkbox.isChecked())
                return
            self._trigger_flash()
            if not self._loading:
                self.play_clicked.emit(self.title, self.url)
        super().mousePressEvent(event)

    # ── Batch selection ──────────────────────────────────────────

    def set_selectable(self, selectable: bool) -> None:
        """Enters/exits selection mode. Entering shows the checkbox and
        hides the play/download buttons (clicking the row toggles selection
        instead of playing); exiting clears any selection."""
        self._selectable = selectable
        self._checkbox.setVisible(selectable)
        self._play_btn.setVisible(not selectable and not self._loading)
        self._dl_btn.setVisible(not selectable and not self._loading)
        if not selectable:
            self._checkbox.setChecked(False)

    def is_selected(self) -> bool:
        return self._checkbox.isChecked()

    def set_selected(self, selected: bool) -> None:
        self._checkbox.setChecked(selected)

    def _on_checkbox_toggled(self, _checked: bool) -> None:
        self.selection_changed.emit()

    def _trigger_flash(self) -> None:
        if self._anim_effect is None or not self._anim_effect.parent():
            self._anim_effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self._anim_effect)
            self._anim = QPropertyAnimation(self._anim_effect, b"opacity", self)
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim.stop()
        self._anim.setDuration(90)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.4)

        def _fade_back():
            if self._anim and self._anim_effect:
                self._anim.stop()
                self._anim.setDuration(160)
                self._anim.setStartValue(0.4)
                self._anim.setEndValue(1.0)
                self._anim.start()

        self._anim.finished.connect(_fade_back)
        self._anim.start()

    def set_playing(self, playing: bool) -> None:
        if playing:
            self._num_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #6366F1;")
            self.setStyleSheet(
                "EpisodeRow { background: rgba(99,102,241,0.12); border-radius: 8px; }"
            )
        else:
            self._num_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #A7ACB5;")
            self.setStyleSheet("")

    def set_loading(self, loading: bool) -> None:
        """Show/hide an inline loading spinner + 'Carregando…' while the player resolves."""
        self._loading = loading
        self._play_btn.setVisible(not loading)
        self._spinner.setVisible(loading)
        self._loading_lbl.setVisible(loading)
        self._play_btn.setEnabled(not loading)
        self._dl_btn.setEnabled(not loading)
        if loading:
            self._spinner.start()
        else:
            self._spinner.stop()

    # ── Download click feedback ─────────────────────────────────

    def play_download_confirmation(self) -> None:
        """Brief visual confirmation that a download click was registered —
        swaps the icon to a green check for ~1s, then fades back to the
        download icon. Purely cosmetic: doesn't reflect actual download
        progress (that's DownloadOverlay's job) — it only confirms the
        click itself was received, before the URL has even been resolved."""
        self._dl_btn.setIcon(icon_check(16, "#3DD68C"))
        self._flash_download_button()
        self._download_confirm_timer.start()

    def _on_download_confirm_timeout(self) -> None:
        self._dl_btn.setIcon(icon_download(16, "#A7ACB5"))
        self._flash_download_button()

    def _flash_download_button(self) -> None:
        if self._dl_btn_effect is None or not self._dl_btn_effect.parent():
            self._dl_btn_effect = QGraphicsOpacityEffect(self._dl_btn)
            self._dl_btn.setGraphicsEffect(self._dl_btn_effect)
            self._dl_btn_anim = QPropertyAnimation(self._dl_btn_effect, b"opacity", self)
            self._dl_btn_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._dl_btn_anim.stop()
        self._dl_btn_anim.setDuration(180)
        self._dl_btn_anim.setStartValue(0.15)
        self._dl_btn_anim.setEndValue(1.0)
        self._dl_btn_anim.start()
