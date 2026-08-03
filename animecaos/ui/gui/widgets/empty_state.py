from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class EmptyState(QWidget):
    """Shown when a section has no data. Displays icon pixmap + title + subtitle."""

    def __init__(
        self,
        icon_pixmap: QPixmap | None = None,
        title: str = "Nada aqui ainda",
        subtitle: str = "",
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
