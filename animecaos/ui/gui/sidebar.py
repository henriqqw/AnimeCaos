"""
Sidebar navigation with Lucide icon buttons.
Only Home, Search, Log, and Account — favorites and history are part of Home.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QCursor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .icons import icon_book, icon_download, icon_folder, icon_home, icon_search, icon_terminal, icon_user
from .views import AnimatedButton


_ICON_SIZE = 20
_BTN_SIZE  = 40
_COLOR_OFF = "#8A8F9A"
_COLOR_ON  = "#FFFFFF"


def _dual_icon(fn, size: int = _ICON_SIZE) -> QIcon:
    """Build a QIcon with separate pixmaps for Off (muted) and On (white) states."""
    icon = QIcon()
    icon.addPixmap(fn(size, _COLOR_OFF), QIcon.Mode.Normal,   QIcon.State.Off)
    icon.addPixmap(fn(size, _COLOR_ON),  QIcon.Mode.Normal,   QIcon.State.On)
    icon.addPixmap(fn(size, _COLOR_ON),  QIcon.Mode.Active,   QIcon.State.Off)
    icon.addPixmap(fn(size, _COLOR_ON),  QIcon.Mode.Selected, QIcon.State.Off)
    return icon


class SidebarNav(QFrame):
    """Vertical icon sidebar — floating pill with circular icon highlights."""

    nav_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(56)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 14, 8, 14)
        layout.setSpacing(6)

        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        # Home
        self._buttons["home"] = self._make_btn(_dual_icon(icon_home), "Inicio")
        layout.addWidget(self._buttons["home"], 0, Qt.AlignmentFlag.AlignHCenter)

        # Search
        self._buttons["search"] = self._make_btn(_dual_icon(icon_search), "Buscar")
        layout.addWidget(self._buttons["search"], 0, Qt.AlignmentFlag.AlignHCenter)

        # Downloads
        self._buttons["downloads"] = self._make_btn(_dual_icon(icon_folder), "Downloads")
        layout.addWidget(self._buttons["downloads"], 0, Qt.AlignmentFlag.AlignHCenter)

        # Manga
        self._buttons["manga"] = self._make_btn(_dual_icon(icon_book), "Manga")
        layout.addWidget(self._buttons["manga"], 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()

        # Account
        self._buttons["account"] = self._make_btn(_dual_icon(icon_user), "Conta AniList")
        layout.addWidget(self._buttons["account"], 0, Qt.AlignmentFlag.AlignHCenter)

        # Log
        self._buttons["log"] = self._make_btn(_dual_icon(icon_terminal), "Log de eventos")
        layout.addWidget(self._buttons["log"], 0, Qt.AlignmentFlag.AlignHCenter)

        self._buttons["home"].setChecked(True)
        self._group.buttonClicked.connect(self._on_button_clicked)

    def _make_btn(self, icon: QIcon, tooltip: str) -> QPushButton:
        btn = AnimatedButton()
        btn.setObjectName("NavButton")
        btn.setIcon(icon)
        btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setFixedSize(_BTN_SIZE, _BTN_SIZE)
        self._group.addButton(btn)
        return btn

    def _on_button_clicked(self, btn: QPushButton) -> None:
        for key, b in self._buttons.items():
            if b is btn:
                self.nav_changed.emit(key)
                break

    def set_active(self, key: str) -> None:
        btn = self._buttons.get(key)
        if btn:
            btn.setChecked(True)

    def set_account_connected(self, connected: bool) -> None:
        pass
