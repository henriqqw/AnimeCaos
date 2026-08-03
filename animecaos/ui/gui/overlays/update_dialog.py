from __future__ import annotations

import os
import re
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget


class UpdateDialog(QDialog):
    def __init__(self, parent: QWidget, latest_version: str, release_notes: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Atualizacao Disponivel")
        self.setFixedSize(500, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setObjectName("UpdateDialog")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        try:
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.abspath(".")
        icon_path = os.path.join(base_path, "assets", "icons", "icon.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(base_path, "public", "icon.png")

        icon_label = QLabel()
        pixmap = QPixmap(icon_path).scaled(
            48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        icon_label.setPixmap(pixmap)
        header_layout.addWidget(icon_label)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title = QLabel("Nova versao disponivel!")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #F2F3F5;")
        version_badge = QLabel(f"v{latest_version}")
        version_badge.setStyleSheet("""
            background-color: rgba(212, 66, 66, 0.2); color: #D44242;
            border: 1px solid rgba(212, 66, 66, 0.4); border-radius: 4px;
            padding: 2px 8px; font-size: 11px; font-weight: 700;
        """)
        badge_container = QHBoxLayout()
        badge_container.addWidget(version_badge)
        badge_container.addStretch()
        title_layout.addWidget(title)
        title_layout.addLayout(badge_container)
        header_layout.addLayout(title_layout)
        layout.addLayout(header_layout)

        notes_title = QLabel("Notas da Versao:")
        notes_title.setObjectName("MutedText")
        notes_title.setStyleSheet("font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;")
        layout.addWidget(notes_title)

        self.notes_browser = QTextBrowser()
        self.notes_browser.setHtml(self._format_notes(release_notes))
        self.notes_browser.setOpenExternalLinks(True)
        self.notes_browser.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px; padding: 12px; color: #E6E7EA; line-height: 1.5;
        """)
        layout.addWidget(self.notes_browser, 1)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        self.btn_ignore = QPushButton("Lembrar depois")
        self.btn_ignore.setFixedHeight(38)
        self.btn_ignore.clicked.connect(self.reject)
        self.btn_update = QPushButton("Atualizar Agora")
        self.btn_update.setObjectName("PrimaryButton")
        self.btn_update.setFixedHeight(38)
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.clicked.connect(self.accept)
        actions_layout.addWidget(self.btn_ignore, 1)
        actions_layout.addWidget(self.btn_update, 2)
        layout.addLayout(actions_layout)

    def _format_notes(self, notes: str) -> str:
        html = notes
        html = re.sub(r'^### (.*)$', r'<h3 style="color: #F2F3F5; margin-top: 10px; margin-bottom: 5px;">\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*)$', r'<h2 style="color: #F2F3F5; margin-top: 12px; margin-bottom: 6px;">\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.*)$', r'<h1 style="color: #F2F3F5; margin-top: 14px; margin-bottom: 8px;">\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.*?)\*\*', r'<b style="color: #ffffff;">\1</b>', html)
        html = re.sub(r'^- (.*)$', r'<li style="margin-left: 10px; margin-bottom: 3px;">\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'<img .*?src="(.*?)".*?>', r'<br/><a href="\1" style="color: #D44242; text-decoration: none;">[Ver Screenshot]</a><br/>', html)
        html = html.replace('\n', '<br/>')
        return f'<div style="font-family: Segoe UI, sans-serif; font-size: 13px;">{html}</div>'
