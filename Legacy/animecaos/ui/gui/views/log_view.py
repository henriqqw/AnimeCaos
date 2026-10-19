from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget


class LogView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Log de Eventos")
        title.setObjectName("SectionTitleLarge")
        layout.addWidget(title)

        subtitle = QLabel("Registro de atividades da aplicacao")
        subtitle.setObjectName("MutedText")
        layout.addWidget(subtitle)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(400)
        layout.addWidget(self.log_output, 1)

        url_row = QHBoxLayout()
        url_label = QLabel("Ultima URL:")
        url_label.setObjectName("MutedText")
        url_row.addWidget(url_label)
        self.url_output = QLineEdit()
        self.url_output.setReadOnly(True)
        url_row.addWidget(self.url_output, 1)
        layout.addLayout(url_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(10)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
