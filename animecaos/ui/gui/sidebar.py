"""
Sidebar navigation with Lucide icon buttons.
Only Home, Search, Log, and Account — favorites and history are part of Home.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .icons import icon_download, icon_folder, icon_home, icon_search, icon_terminal, icon_user
from .views import AnimatedButton




class SidebarNav(QFrame):
    """Vertical icon sidebar for top-level navigation."""

    nav_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(56)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(4)

        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        # Home
        home_btn = self._make_nav_btn(icon_home(22, "#A7ACB5"), "Inicio")
        self._buttons["home"] = home_btn
        layout.addWidget(home_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        # Search
        search_btn = self._make_nav_btn(icon_search(22, "#A7ACB5"), "Buscar")
        self._buttons["search"] = search_btn
        layout.addWidget(search_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        # Downloads library
        dl_btn = self._make_nav_btn(icon_folder(22, "#A7ACB5"), "Downloads")
        self._buttons["downloads"] = dl_btn
        layout.addWidget(dl_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()

        # Account (before log)
        account_btn = self._make_nav_btn(icon_user(22, "#A7ACB5"), "Conta AniList")
        self._buttons["account"] = account_btn
        layout.addWidget(account_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        # Log at bottom
        log_btn = self._make_nav_btn(icon_terminal(22, "#A7ACB5"), "Log de eventos")
        self._buttons["log"] = log_btn
        layout.addWidget(log_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        # Default
        self._buttons["home"].setChecked(True)

        self._group.buttonClicked.connect(self._on_button_clicked)

    def _make_nav_btn(self, pixmap, tooltip: str) -> QPushButton:
        btn = AnimatedButton()
        btn.setObjectName("NavButton")
        btn.setIcon(QIcon(pixmap))
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setFixedSize(40, 40)
        btn.setIconSize(pixmap.size())
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
