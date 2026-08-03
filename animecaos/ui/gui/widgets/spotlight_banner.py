from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QCursor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


class _MetaBadge(QLabel):
    """Dark pill badge for metadata (TV, 24m, HD…)."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(
            "QLabel { background: rgba(255,255,255,0.12); color: #E8E9EC; border-radius: 14px;"
            " padding: 4px 14px; font-size: 12px; font-weight: 500; }"
        )
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class SpotlightBanner(QWidget):
    """
    Hero spotlight — full-width, Crunchyroll-style:
      • The anime artwork fills the ENTIRE widget as background.
      • A horizontal gradient overlay darkens the left half so text is readable.
      • All content (badge, title, description, meta, buttons) sits on top.
    """

    watch_clicked = Signal(dict)
    anilist_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SpotlightBanner")
        self.setFixedHeight(420)
        self._card: dict = {}
        self._raw_pixmap: QPixmap | None = None
        self._bg_pixmap: QPixmap | None = None
        self._meta_badges: list[_MetaBadge] = []

        content_widget = QWidget(self)
        content_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        content_widget.setStyleSheet("background: transparent;")

        content = QVBoxLayout(content_widget)
        content.setContentsMargins(40, 36, 0, 36)
        content.setSpacing(0)

        self._rank_badge = QLabel()
        self._rank_badge.setStyleSheet(
            "QLabel { color: #F5D060; background: rgba(245,208,96,0.14);"
            " border: 1px solid rgba(245,208,96,0.40); border-radius: 14px;"
            " padding: 4px 14px; font-size: 11px; font-weight: 700; letter-spacing: 1px; }"
        )
        self._rank_badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        content.addWidget(self._rank_badge)
        content.addSpacing(18)

        self._title_lbl = QLabel()
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setMaximumWidth(520)
        self._title_lbl.setStyleSheet(
            "QLabel { color: #FFFFFF; font-size: 38px; font-weight: 800;"
            " background: transparent; }"
        )
        self._title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content.addWidget(self._title_lbl)
        content.addSpacing(14)

        desc_wrapper = QFrame()
        desc_wrapper.setStyleSheet(
            "QFrame { border-left: 3px solid rgba(255,255,255,0.30);"
            " background: transparent; padding-left: 0px; }"
        )
        desc_inner = QHBoxLayout(desc_wrapper)
        desc_inner.setContentsMargins(12, 2, 0, 2)
        desc_inner.setSpacing(0)
        self._desc_lbl = QLabel()
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setMaximumWidth(480)
        self._desc_lbl.setMaximumHeight(68)
        self._desc_lbl.setStyleSheet(
            "QLabel { color: rgba(210,215,228,0.85); font-size: 13px;"
            " background: transparent; border: none; }"
        )
        desc_inner.addWidget(self._desc_lbl)
        content.addWidget(desc_wrapper)
        content.addSpacing(20)

        self._meta_row = QHBoxLayout()
        self._meta_row.setSpacing(8)
        self._meta_row.setContentsMargins(0, 0, 0, 0)
        content.addLayout(self._meta_row)
        content.addSpacing(24)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.setContentsMargins(0, 0, 0, 0)

        self._watch_btn = QPushButton("▶   Assistir")
        self._watch_btn.setFixedHeight(46)
        self._watch_btn.setMinimumWidth(160)
        self._watch_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._watch_btn.setStyleSheet(
            "QPushButton { background: #FFFFFF; color: #0B0C0F; border: none;"
            " border-radius: 23px; font-size: 14px; font-weight: 700; padding: 0 24px; }"
            " QPushButton:hover { background: #E8E9EC; }"
            " QPushButton:pressed { background: #CDCFD4; }"
        )
        self._watch_btn.clicked.connect(lambda: self.watch_clicked.emit(self._card))

        self._list_btn = QPushButton("≡")
        self._list_btn.setFixedSize(46, 46)
        self._list_btn.setToolTip("Ver no AniList")
        self._list_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._list_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.14); color: #FFFFFF; border: none;"
            " border-radius: 23px; font-size: 18px; }"
            " QPushButton:hover { background: rgba(255,255,255,0.22); }"
            " QPushButton:pressed { background: rgba(255,255,255,0.08); }"
        )
        self._list_btn.clicked.connect(self._on_list_btn_clicked)

        btn_row.addWidget(self._watch_btn)
        btn_row.addWidget(self._list_btn)
        btn_row.addStretch()
        content.addLayout(btn_row)

        content.addStretch()

        content_widget.setFixedWidth(self.width() // 2 if self.width() > 0 else 560)
        self._content_widget = content_widget

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w = self.width()
        cw = max(380, min(600, w // 2))
        self._content_widget.setGeometry(0, 0, cw, self.height())
        if self._raw_pixmap:
            self._build_bg()
            self.update()

    def set_data(self, card: dict, rank: int = 1) -> None:
        self._card = card

        self._rank_badge.setText(f"★  #{rank} DESTAQUE DA TEMPORADA")
        self._title_lbl.setText(card.get("title", ""))
        self._list_btn.setVisible(bool(card.get("anilist_id")))

        desc = card.get("description") or ""
        if desc:
            words = desc.split()
            truncated = " ".join(words[:30])
            if len(words) > 30:
                truncated += "..."
            self._desc_lbl.setText(truncated)
            self._desc_lbl.parentWidget().show()
        else:
            self._desc_lbl.parentWidget().hide()

        self._rebuild_meta_badges(card)

        cover_path = card.get("cover_path")
        banner_path = card.get("banner_path")
        img_path = banner_path or cover_path
        if img_path and os.path.exists(str(img_path)):
            self._load_image(str(img_path))

    def set_banner(self, path: str) -> None:
        if os.path.exists(path):
            self._load_image(path)

    def set_cover(self, path: str) -> None:
        if os.path.exists(path) and self._raw_pixmap is None:
            self._load_image(path)

    def _on_list_btn_clicked(self) -> None:
        anilist_id = self._card.get("anilist_id")
        if anilist_id:
            self.anilist_clicked.emit(int(anilist_id))

    def _rebuild_meta_badges(self, card: dict) -> None:
        for b in self._meta_badges:
            b.deleteLater()
        self._meta_badges.clear()

        tags: list[str] = []
        fmt = card.get("format")
        if fmt:
            tags.append(fmt.replace("_", " "))
        dur = card.get("duration")
        if dur:
            tags.append(f"{dur}m")
        score = card.get("score")
        if score:
            tags.append(f"★ {score / 10:.1f}")
        episodes = card.get("episodes")
        if episodes:
            tags.append(f"{episodes} eps")
        tags.append("HD")

        for tag in tags:
            badge = _MetaBadge(tag)
            self._meta_row.addWidget(badge)
            self._meta_badges.append(badge)
        self._meta_row.addStretch()

    def _load_image(self, path: str) -> None:
        raw = QPixmap(path)
        if raw.isNull():
            return
        self._raw_pixmap = raw
        self._build_bg()
        self.update()

    def _build_bg(self) -> None:
        if not self._raw_pixmap:
            return
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        scaled = self._raw_pixmap.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, scaled.width() - w)
        y = max(0, (scaled.height() - h) // 2)
        self._bg_pixmap = scaled.copy(x, y, w, min(h, scaled.height()))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        w, h = rect.width(), rect.height()

        painter.fillRect(rect, QColor(10, 10, 14))

        if self._bg_pixmap:
            painter.drawPixmap(0, 0, self._bg_pixmap)

        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.00, QColor(8, 8, 12, 255))
        grad.setColorAt(0.38, QColor(8, 8, 12, 220))
        grad.setColorAt(0.55, QColor(8, 8, 12, 100))
        grad.setColorAt(0.72, QColor(8, 8, 12, 30))
        grad.setColorAt(1.00, QColor(8, 8, 12, 0))
        painter.fillRect(rect, grad)

        vign = QLinearGradient(0, h - 80, 0, h)
        vign.setColorAt(0.0, QColor(8, 8, 12, 0))
        vign.setColorAt(1.0, QColor(8, 8, 12, 200))
        painter.fillRect(rect, vign)

        painter.end()
        super().paintEvent(event)
