from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCursor, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class _SocialLinkButton(QPushButton):
    """Icon + label pill that opens a URL in the system browser when clicked."""

    def __init__(self, icon_pixmap: QPixmap, label: str, url: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self._url = url
        self.setIcon(QIcon(icon_pixmap))
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet(
            "QPushButton { color: #E6E7EA; background: rgba(255,255,255,0.06);"
            " border: 1px solid rgba(255,255,255,0.12); border-radius: 16px;"
            " padding: 6px 16px; font-size: 12px; font-weight: 600; }"
            " QPushButton:hover { background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.22); }"
            " QPushButton:pressed { background: rgba(255,255,255,0.04); }"
        )
        self.clicked.connect(self._open)

    def _open(self) -> None:
        QDesktopServices.openUrl(QUrl(self._url))


class EmptyState(QWidget):
    """Shown when a section has no data. Displays icon pixmap + title + subtitle,
    optionally followed by a row of clickable social-link buttons (e.g. pointing
    users at social media to request content that couldn't be found)."""

    def __init__(
        self,
        icon_pixmap: QPixmap | None = None,
        title: str = "Nada aqui ainda",
        subtitle: str = "",
        social_links: list[tuple[QPixmap, str, str]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        if icon_pixmap:
            icon_label = QLabel()
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setPixmap(icon_pixmap)
            layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setObjectName("EmptyStateTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("EmptyStateSubtitle")
            sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub_label.setWordWrap(True)
            layout.addWidget(sub_label)

        self._social_buttons: list[_SocialLinkButton] = []
        if social_links:
            layout.addSpacing(4)
            row = QHBoxLayout()
            row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.setSpacing(10)
            for icon, label, url in social_links:
                btn = _SocialLinkButton(icon, label, url)
                row.addWidget(btn)
                self._social_buttons.append(btn)
            layout.addLayout(row)
