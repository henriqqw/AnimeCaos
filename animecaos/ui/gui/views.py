"""
Views for the AnimeCaos redesigned UI.

HomeView        – landing page with Continue Watching + Favorites only
SearchView      – dedicated search results page with card grid + loading
AnimeDetailView – full anime page with metadata + episode list
"""
from __future__ import annotations

import math
import os
import sys
from typing import Any

from PySide6.QtCore import (
    Qt,
    Signal,
    QSize,
    QRectF,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    Property,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QCursor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QTextEdit,
    QGridLayout,
    QMessageBox,
)

from .components import (
    AnimeCard,
    EmptyState,
    EpisodeRow,
    HorizontalCardScroll,
    generate_dynamic_cover,
)
from .icons import (
    icon_arrow_left,
    icon_book,
    icon_clock,
    icon_folder,
    icon_loader,
    icon_monitor,
    icon_search,
    icon_search_x,
    icon_trash,
    icon_user,
    icon_x,
)
from animecaos.services.downloads_service import DownloadEntry
from animecaos.services.manga_download_service import MangaDownloadEntry
from .loading_overlay import LoadingOverlay


# ═══════════════════════════════════════════════════════════════════
#  ANIMATED BUTTON
# ═══════════════════════════════════════════════════════════════════

class AnimatedButton(QPushButton):
    """QPushButton with a smooth opacity fade on press/release."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._effect: QGraphicsOpacityEffect | None = None
        self._anim: QPropertyAnimation | None = None

    def _ensure_effect(self) -> QGraphicsOpacityEffect:
        """Return active effect, recreating if Qt deleted the previous one."""
        if self._effect is None or not self._effect.parent():
            self._effect = QGraphicsOpacityEffect(self)
            self._effect.setOpacity(1.0)
            self.setGraphicsEffect(self._effect)
            self._anim = QPropertyAnimation(self._effect, b"opacity", self)
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.finished.connect(self._on_anim_finished)
        return self._effect

    def _on_anim_finished(self) -> None:
        if self._effect and self._effect.opacity() >= 1.0:
            self.setGraphicsEffect(None)
            self._effect = None
            self._anim = None

    def mousePressEvent(self, event):
        effect = self._ensure_effect()
        self._anim.stop()
        self._anim.setDuration(80)
        self._anim.setStartValue(effect.opacity())
        self._anim.setEndValue(0.55)
        self._anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        effect = self._ensure_effect()
        self._anim.stop()
        self._anim.setDuration(160)
        self._anim.setStartValue(effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().mouseReleaseEvent(event)


# ═══════════════════════════════════════════════════════════════════
#  SPOTLIGHT BANNER
# ═══════════════════════════════════════════════════════════════════

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
    Hero spotlight — full-width, split layout:
      LEFT  45%: badge · title · description · meta pills · watch button
      RIGHT 55%: banner artwork image (rounded corners)
    Matches Tatakai reference design.
    """

    watch_clicked = Signal(dict)
    anilist_clicked = Signal(int)  # anilist_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SpotlightBanner")
        self.setFixedHeight(420)
        self._card: dict = {}
        self._image_pixmap: QPixmap | None = None   # banner or cover
        self._meta_badges: list[_MetaBadge] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ══ LEFT PANEL ══
        left_widget = QWidget()
        left_widget.setStyleSheet("background: transparent;")
        left = QVBoxLayout(left_widget)
        left.setContentsMargins(36, 36, 24, 32)
        left.setSpacing(0)

        # Badge: ★ #N SPOTLIGHT
        self._rank_badge = QLabel()
        self._rank_badge.setStyleSheet(
            "QLabel { color: #F5D060; background: rgba(245,208,96,0.14);"
            " border: 1px solid rgba(245,208,96,0.40); border-radius: 14px;"
            " padding: 4px 14px; font-size: 11px; font-weight: 700; letter-spacing: 1px; }"
        )
        self._rank_badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        left.addWidget(self._rank_badge)
        left.addSpacing(16)

        # Title — very large bold
        self._title_lbl = QLabel()
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setStyleSheet(
            "QLabel { color: #FFFFFF; font-size: 36px; font-weight: 800;"
            " background: transparent; line-height: 1.05; }"
        )
        self._title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        left.addWidget(self._title_lbl)
        left.addSpacing(16)

        # Description with left accent bar
        desc_wrapper = QFrame()
        desc_wrapper.setStyleSheet(
            "QFrame { border-left: 3px solid rgba(255,255,255,0.22);"
            " background: transparent; padding-left: 0px; }"
        )
        desc_inner = QHBoxLayout(desc_wrapper)
        desc_inner.setContentsMargins(12, 2, 0, 2)
        desc_inner.setSpacing(0)
        self._desc_lbl = QLabel()
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setMaximumHeight(68)
        self._desc_lbl.setStyleSheet(
            "QLabel { color: rgba(210,212,220,0.80); font-size: 13px;"
            " background: transparent; border: none; }"
        )
        desc_inner.addWidget(self._desc_lbl)
        left.addWidget(desc_wrapper)
        left.addSpacing(20)

        # Meta badges row
        self._meta_row = QHBoxLayout()
        self._meta_row.setSpacing(8)
        self._meta_row.setContentsMargins(0, 0, 0, 0)
        left.addLayout(self._meta_row)
        left.addSpacing(24)

        # Buttons row
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
            "QPushButton { background: rgba(255,255,255,0.12); color: #FFFFFF; border: none;"
            " border-radius: 23px; font-size: 18px; }"
            " QPushButton:hover { background: rgba(255,255,255,0.18); }"
            " QPushButton:pressed { background: rgba(255,255,255,0.08); }"
        )
        self._list_btn.clicked.connect(self._on_list_btn_clicked)

        btn_row.addWidget(self._watch_btn)
        btn_row.addWidget(self._list_btn)
        btn_row.addStretch()
        left.addLayout(btn_row)

        left.addStretch()

        root.addWidget(left_widget, 45)

        # ══ RIGHT PANEL — artwork image ══
        self._image_lbl = QLabel()
        self._image_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_lbl.setStyleSheet("background: transparent;")
        self._image_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._image_lbl, 55)

    # ── Public API ──────────────────────────────────────────────

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
            self._load_image(str(img_path), prefer_banner=bool(banner_path))

    def set_banner(self, path: str) -> None:
        if os.path.exists(path):
            self._load_image(path, prefer_banner=True)

    def set_cover(self, path: str) -> None:
        if os.path.exists(path) and self._image_pixmap is None:
            self._load_image(path, prefer_banner=False)

    def _on_list_btn_clicked(self) -> None:
        anilist_id = self._card.get("anilist_id")
        if anilist_id:
            self.anilist_clicked.emit(int(anilist_id))

    # ── Internal ────────────────────────────────────────────────

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

    def _load_image(self, path: str, prefer_banner: bool) -> None:
        raw = QPixmap(path)
        if raw.isNull():
            return

        panel = self._image_lbl
        pw = panel.width() if panel.width() > 0 else 600
        ph = self.height()

        if prefer_banner:
            # Banner: scale to fill right panel width
            scaled = raw.scaled(
                pw, ph,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Crop to panel size centered
            x = max(0, (scaled.width() - pw) // 2)
            y = max(0, (scaled.height() - ph) // 2)
            cropped = scaled.copy(x, y, min(pw, scaled.width()), min(ph, scaled.height()))
            final = self._apply_rounded(cropped, 16)
        else:
            # Cover/poster: scale to fit height, center horizontally
            th = ph - 32
            tw = int(th * 0.70)
            scaled = raw.scaled(tw, th, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
            final = self._apply_rounded(scaled, 12)

        self._image_pixmap = final
        panel.setPixmap(final)

    @staticmethod
    def _apply_rounded(pm: QPixmap, radius: int) -> QPixmap:
        out = QPixmap(pm.size())
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(out.rect()), radius, radius)
        p.setClipPath(clip)
        p.drawPixmap(0, 0, pm)
        p.end()
        return out

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Reload image at new panel size when widget is resized
        if self._card:
            banner_path = self._card.get("banner_path")
            cover_path = self._card.get("cover_path")
            img_path = banner_path or cover_path
            if img_path and os.path.exists(str(img_path)):
                self._image_pixmap = None
                self._load_image(str(img_path), prefer_banner=bool(banner_path))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        # Solid dark background
        painter.fillRect(rect, QColor(10, 10, 12))
        painter.end()
        super().paintEvent(event)


# ═══════════════════════════════════════════════════════════════════
#  HOME VIEW
# ═══════════════════════════════════════════════════════════════════

class _AniListOfflineBanner(QFrame):
    """Dismissible warning banner shown when AniList API is unavailable."""

    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background: rgba(212,100,50,0.15); border: 1px solid rgba(212,100,50,0.4);"
            " border-radius: 10px; }"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 12, 12)
        row.setSpacing(12)

        self._icon = QLabel("!")
        self._icon.setStyleSheet("color: #D46432; font-size: 18px; font-weight: 900; background: transparent; border: none;")
        self._icon.setFixedWidth(22)
        row.addWidget(self._icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            "color: #F2C97D; font-size: 13px; font-weight: 700; background: transparent; border: none;"
        )
        self._desc_lbl = QLabel()
        self._desc_lbl.setStyleSheet(
            "color: rgba(242,201,125,0.75); font-size: 12px; background: transparent; border: none;"
        )
        self._desc_lbl.setWordWrap(True)
        text_col.addWidget(self._title_lbl)
        text_col.addWidget(self._desc_lbl)
        row.addLayout(text_col, 1)

        close_btn = QPushButton("x")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: rgba(242,201,125,0.6);"
            " font-size: 14px; } QPushButton:hover { color: #F2C97D; }"
        )
        close_btn.clicked.connect(self._dismiss)
        row.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

    def update_status(self, title: str, description: str) -> None:
        self._title_lbl.setText(title)
        self._desc_lbl.setText(description)

    def _dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()


class HomeView(QWidget):
    """Landing view with Continue Watching section."""

    history_clicked = Signal(object)
    discover_clicked = Signal(object)
    anilist_page_requested = Signal(int)  # anilist_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        # Root container — zero margins so spotlight fills edge to edge
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── AniList offline banner (inside padded inner) ──
        self._offline_banner = _AniListOfflineBanner()
        self._offline_banner.hide()

        # ── Spotlight Hero — full width, no side margins ──
        self.spotlight = SpotlightBanner()
        self.spotlight.watch_clicked.connect(self.discover_clicked.emit)
        self.spotlight.anilist_clicked.connect(self.anilist_page_requested.emit)
        self.spotlight.hide()
        root_layout.addWidget(self.spotlight)

        # ── Inner padded section for all other content ──
        inner_widget = QWidget()
        inner_widget.setStyleSheet("background: transparent;")
        self._content = QVBoxLayout(inner_widget)
        self._content.setContentsMargins(24, 20, 24, 24)
        self._content.setSpacing(24)

        self._content.addWidget(self._offline_banner)

        # ── Continue Watching ──
        self.history_section = HorizontalCardScroll("Continue Assistindo")
        self.history_section.card_clicked.connect(self.history_clicked.emit)
        self.history_section.set_empty(
            icon_clock(36, "rgba(255,255,255,0.15)"),
            "Nenhum historico",
            "Os animes que voce assistir aparecerao aqui",
        )
        self._content.addWidget(self.history_section)

        # ── Em Alta ──
        self.trending_section = HorizontalCardScroll("Em Alta")
        self.trending_section.card_clicked.connect(self.discover_clicked.emit)
        self.trending_section.set_empty(
            icon_loader(36, "rgba(255,255,255,0.15)"),
            "Carregando...",
            "",
        )
        self._content.addWidget(self.trending_section)

        # ── Temporada Atual ──
        self._seasonal_title = self._current_season_label()
        self.seasonal_section = HorizontalCardScroll(self._seasonal_title)
        self.seasonal_section.card_clicked.connect(self.discover_clicked.emit)
        self.seasonal_section.set_empty(
            icon_loader(36, "rgba(255,255,255,0.15)"),
            "Carregando...",
            "",
        )
        self._content.addWidget(self.seasonal_section)

        self._content.addStretch()

        root_layout.addWidget(inner_widget)

        self._scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

    @staticmethod
    def _current_season_label() -> str:
        from datetime import datetime
        month = datetime.now().month
        year = datetime.now().year
        if month <= 3:
            season = "Inverno"
        elif month <= 6:
            season = "Primavera"
        elif month <= 9:
            season = "Verão"
        else:
            season = "Outono"
        return f"Temporada Atual — {season} {year}"

    def set_history_cards(self, items: list[dict[str, Any]]) -> None:
        if items:
            self.history_section.set_cards(items)
        else:
            self.history_section.set_empty(
                icon_clock(36, "rgba(255,255,255,0.15)"),
                "Nenhum historico",
                "Os animes que voce assistir aparecerao aqui",
            )

    def update_card_cover(self, title: str, cover_path: str) -> None:
        self.history_section.update_card_cover(title, cover_path)

    def set_trending_cards(self, items: list[Any]) -> None:
        if items:
            self.trending_section.set_cards(items)
        else:
            self.trending_section.set_empty(
                icon_loader(36, "rgba(255,255,255,0.10)"),
                "Sem resultados",
                "Nao foi possivel carregar os dados",
            )

    def set_seasonal_cards(self, items: list[Any]) -> None:
        if items:
            self.seasonal_section.set_cards(items)
        else:
            self.seasonal_section.set_empty(
                icon_loader(36, "rgba(255,255,255,0.10)"),
                "Sem resultados",
                "Nao foi possivel carregar os dados",
            )

    def remove_trending_card(self, title: str) -> None:
        self.trending_section.remove_card(title)

    def remove_seasonal_card(self, title: str) -> None:
        self.seasonal_section.remove_card(title)

    def trim_discover_sections(self, max_cards: int = 10) -> None:
        self.trending_section.trim_to(max_cards)
        self.seasonal_section.trim_to(max_cards)

    def set_spotlight(self, card: dict, rank: int = 1) -> None:
        self.spotlight.set_data(card, rank)
        self.spotlight.show()

    def set_spotlight_banner(self, path: str) -> None:
        self.spotlight.set_banner(path)

    def set_spotlight_cover(self, path: str) -> None:
        self.spotlight.set_cover(path)

    def update_discover_cover(self, title: str, cover_path: str) -> None:
        self.trending_section.update_card_cover(title, cover_path)
        self.seasonal_section.update_card_cover(title, cover_path)

    def show_anilist_offline_banner(self, title: str, description: str) -> None:
        self._offline_banner.update_status(title, description)
        self._offline_banner.show()

    def hide_anilist_offline_banner(self) -> None:
        self._offline_banner.hide()


# ═══════════════════════════════════════════════════════════════════
#  SEARCH VIEW
# ═══════════════════════════════════════════════════════════════════

class _SkeletonCardCanvas(QWidget):
    """Animated loading: 1 row of skeleton cards + spinning ring + dynamic messages."""

    _CARD_W = 150
    _CARD_H = 250
    _COVER_H = 190
    _GAP = 14
    _RADIUS = 10
    _SHIMMER_W = 0.30

    # Spinner geometry
    _RING_RADIUS = 22
    _RING_STROKE = 2.5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._phase = 0.0
        self._ring_angle = 0.0
        self._status_text = "Buscando animes..."
        self._elapsed_ms = 0

        self._status_messages: list[tuple[int, str]] = [
            (0,     "Buscando animes..."),
            (4000,  "Consultando fontes... isso pode levar alguns segundos"),
            (10000, "Aguarde, algumas fontes demoram mais para responder..."),
            (18000, "Quase la... finalizando busca em todas as fontes"),
            (28000, "Ainda buscando... a conexao pode estar lenta"),
        ]
        self._next_msg = 1

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

        self.setMinimumHeight(500)

    def start(self) -> None:
        self._phase = 0.0
        self._ring_angle = 0.0
        self._elapsed_ms = 0
        self._next_msg = 1
        self._status_text = self._status_messages[0][1]
        self._timer.start()
        self.setVisible(True)

    def stop(self) -> None:
        self._timer.stop()
        self.setVisible(False)

    def _tick(self) -> None:
        dt = 16.0 / 1000.0
        self._phase = (self._phase + dt * 0.5) % 1.0
        self._ring_angle = (self._ring_angle + 4.0) % 360.0
        self._elapsed_ms += 16

        if self._next_msg < len(self._status_messages):
            ms, msg = self._status_messages[self._next_msg]
            if self._elapsed_ms >= ms:
                self._status_text = msg
                self._next_msg += 1

        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        cols = max(1, (w + self._GAP) // (self._CARD_W + self._GAP))

        # ── Row of skeleton cards ──
        for col in range(cols):
            x = col * (self._CARD_W + self._GAP)
            y = 0
            if x + self._CARD_W > w:
                break

            card_rect = QRectF(x, y, self._CARD_W, self._CARD_H)
            card_path = QPainterPath()
            card_path.addRoundedRect(card_rect, self._RADIUS, self._RADIUS)
            p.fillPath(card_path, QColor(255, 255, 255, 12))

            # Cover
            cover_rect = QRectF(x + 6, y + 6, self._CARD_W - 12, self._COVER_H)
            cover_path = QPainterPath()
            cover_path.addRoundedRect(cover_rect, 8, 8)
            p.fillPath(cover_path, QColor(255, 255, 255, 18))
            self._draw_shimmer(p, cover_path, cover_rect)

            # Title lines
            t1 = QRectF(x + 6, y + self._COVER_H + 14, self._CARD_W * 0.78, 11)
            t1p = QPainterPath()
            t1p.addRoundedRect(t1, 4, 4)
            p.fillPath(t1p, QColor(255, 255, 255, 14))
            self._draw_shimmer(p, t1p, t1)

            t2 = QRectF(x + 6, y + self._COVER_H + 31, self._CARD_W * 0.5, 11)
            t2p = QPainterPath()
            t2p.addRoundedRect(t2, 4, 4)
            p.fillPath(t2p, QColor(255, 255, 255, 10))
            self._draw_shimmer(p, t2p, t2)

        # ── Centered spinner area below cards ──
        spinner_area_y = self._CARD_H + 48
        cx = w / 2.0
        cy = spinner_area_y + self._RING_RADIUS + 8

        # Ring track
        track_pen = QPen(QColor(255, 255, 255, 20), self._RING_STROKE)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(track_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(
            cx - self._RING_RADIUS, cy - self._RING_RADIUS,
            self._RING_RADIUS * 2, self._RING_RADIUS * 2,
        ))

        # Spinning arc (conical gradient)
        arc_rect = QRectF(
            cx - self._RING_RADIUS, cy - self._RING_RADIUS,
            self._RING_RADIUS * 2, self._RING_RADIUS * 2,
        )
        gradient = QConicalGradient(cx, cy, self._ring_angle)
        gradient.setColorAt(0.0, QColor(212, 66, 66, 230))
        gradient.setColorAt(0.25, QColor(212, 66, 66, 60))
        gradient.setColorAt(0.3, QColor(212, 66, 66, 0))

        arc_pen = QPen(gradient, self._RING_STROKE)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc_pen)
        start_angle = int(self._ring_angle * 16)
        span_angle = 90 * 16
        p.drawArc(arc_rect, start_angle, span_angle)

        # ── Status text below spinner ──
        p.setPen(QColor(167, 172, 181, 230))
        font = p.font()
        font.setPixelSize(14)
        font.setWeight(font.Weight.Medium)
        p.setFont(font)

        text_y = cy + self._RING_RADIUS + 18
        text_rect = QRectF(0, text_y, w, 28)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self._status_text)

        # ── Subtle dot animation below text ──
        dot_y = text_y + 36
        dot_count = 3
        dot_spacing = 12
        dot_start = cx - (dot_count - 1) * dot_spacing / 2
        dot_phase = (self._elapsed_ms / 400.0)

        for i in range(dot_count):
            bounce = math.sin(dot_phase - i * 0.7) * 0.5 + 0.5
            r = 3.0 * (0.5 + 0.5 * bounce)
            alpha = int(80 + 175 * bounce)
            dx = dot_start + i * dot_spacing
            dy = dot_y - math.sin(dot_phase - i * 0.7) * 2.5

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(212, 66, 66, alpha))
            p.drawEllipse(QRectF(dx - r, dy - r, r * 2, r * 2))

        p.end()

    def _draw_shimmer(self, p: QPainter, clip_path: QPainterPath, rect: QRectF) -> None:
        grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
        clr_t = QColor(255, 255, 255, 0)
        clr_h = QColor(255, 255, 255, 30)
        hw = self._SHIMMER_W / 2
        c = self._phase
        grad.setColorAt(0.0, clr_t)
        if c - hw > 0.01:
            grad.setColorAt(c - hw, clr_t)
        if 0.01 < c < 0.99:
            grad.setColorAt(c, clr_h)
        if c + hw < 0.99:
            grad.setColorAt(c + hw, clr_t)
        grad.setColorAt(1.0, clr_t)
        p.save()
        p.setClipPath(clip_path)
        p.fillRect(rect, grad)
        p.restore()


class SearchView(QWidget):
    """Dedicated search results page with animated skeleton loading and card grid."""

    anime_clicked = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._has_searched = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._content = QVBoxLayout(container)
        self._content.setContentsMargins(24, 16, 24, 24)
        self._content.setSpacing(16)

        # Header
        header = QHBoxLayout()
        self._query_label = QLabel("Buscar")
        self._query_label.setObjectName("SectionTitleLarge")
        header.addWidget(self._query_label)

        self._count_badge = QLabel("")
        self._count_badge.setObjectName("Badge")
        self._count_badge.setVisible(False)
        header.addWidget(self._count_badge)

        header.addStretch()
        self._content.addLayout(header)

        # ── Welcome state (shown before first search) ──
        self._welcome = QWidget()
        self._welcome.setStyleSheet("background: transparent;")
        welcome_layout = QVBoxLayout(self._welcome)
        welcome_layout.setContentsMargins(0, 60, 0, 0)
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        welcome_layout.setSpacing(16)

        # App icon
        try:
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.abspath(".")
        icon_path = os.path.join(base_path, "public", "icon.png")

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        raw_icon = QPixmap(icon_path)
        if not raw_icon.isNull():
            from PySide6.QtGui import QPainter as _P, QPainterPath as _PP
            scaled = raw_icon.scaled(
                64, 64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            rounded_icon = QPixmap(scaled.size())
            rounded_icon.fill(Qt.GlobalColor.transparent)
            painter = _P(rounded_icon)
            painter.setRenderHint(_P.RenderHint.Antialiasing)
            clip = _PP()
            clip.addRoundedRect(0, 0, scaled.width(), scaled.height(), 14, 14)
            painter.setClipPath(clip)
            painter.drawPixmap(0, 0, scaled)
            painter.end()
            icon_label.setPixmap(rounded_icon)
        welcome_layout.addWidget(icon_label)

        welcome_title = QLabel("Encontre seu anime")
        welcome_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_title.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #F2F3F5;"
        )
        welcome_layout.addWidget(welcome_title)

        welcome_sub = QLabel("Use a barra de busca acima ou pressione Ctrl+F")
        welcome_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_sub.setStyleSheet("font-size: 13px; color: #A7ACB5;")
        welcome_layout.addWidget(welcome_sub)

        # Shortcut hints
        hints_container = QWidget()
        hints_container.setStyleSheet("background: transparent;")
        hints_layout = QHBoxLayout(hints_container)
        hints_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hints_layout.setSpacing(24)

        for key, desc in [("Ctrl+F", "Buscar"), ("Esc", "Voltar"), ("Alt+\u2190", "Anterior")]:
            chip = QLabel(f'<span style="color: #D44242; font-weight: 600;">{key}</span>'
                          f'<span style="color: #7F848D;">  {desc}</span>')
            chip.setStyleSheet(
                "background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08);"
                "border-radius: 6px; padding: 6px 14px; font-size: 12px;"
            )
            hints_layout.addWidget(chip)

        welcome_layout.addSpacing(8)
        welcome_layout.addWidget(hints_container)

        self._content.addWidget(self._welcome)

        # Animated skeleton loading
        self._skeleton = _SkeletonCardCanvas()
        self._skeleton.setVisible(False)
        self._content.addWidget(self._skeleton)

        # Cards grid
        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: transparent;")
        self._grid_layout = _FlowLayout(self._grid_container, spacing=14)
        self._content.addWidget(self._grid_container)

        # Empty state (after search with no results)
        self._empty_state = EmptyState(
            icon_search_x(48, "rgba(255,255,255,0.12)"),
            "Nenhum resultado",
            "Tente outro termo de busca",
        )
        self._empty_state.setVisible(False)
        self._empty_state.setMinimumHeight(300)
        self._content.addWidget(self._empty_state)

        self._content.addStretch()
        self._scroll.setWidget(container)
        outer.addWidget(self._scroll)

        self._cards: list[AnimeCard] = []

    def show_searching(self, query: str) -> None:
        self._has_searched = True
        self._welcome.setVisible(False)
        self._query_label.setText(f'Resultados para "{query}"')
        self._count_badge.setVisible(False)
        self._clear_cards()
        self._empty_state.setVisible(False)
        self._grid_container.setVisible(False)
        self._skeleton.start()

    def set_results(self, items: list[dict[str, Any]], query: str = "") -> None:
        self._skeleton.stop()
        self._welcome.setVisible(False)
        self._clear_cards()
        self._grid_container.setVisible(True)

        if query:
            self._query_label.setText(f'Resultados para "{query}"')

        if not items:
            self._empty_state.setVisible(True)
            self._count_badge.setVisible(False)
            return

        self._empty_state.setVisible(False)
        self._count_badge.setText(f"{len(items)} encontrados")
        self._count_badge.setVisible(True)

        for data in items:
            card = AnimeCard(data)
            card.clicked.connect(self.anime_clicked.emit)
            self._cards.append(card)
            self._grid_layout.addWidget(card)

    def reset_to_welcome(self) -> None:
        """Reset view back to initial welcome state."""
        self._skeleton.stop()
        self._clear_cards()
        self._empty_state.setVisible(False)
        self._grid_container.setVisible(True)
        self._count_badge.setVisible(False)
        self._query_label.setText("Buscar")
        if not self._has_searched:
            self._welcome.setVisible(True)

    def update_card_cover(self, title: str, cover_path: str) -> None:
        for card in self._cards:
            if card.data.get("title") == title:
                card.set_cover_from_path(cover_path)
                break

    def _clear_cards(self) -> None:
        for card in self._cards:
            self._grid_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()


class _FlowLayout(QVBoxLayout):
    """Grid-based flow layout for cards."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 12) -> None:
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)
        self._spacing = spacing
        self._widgets: list[QWidget] = []
        self._flow_widget = QWidget()
        self._flow_widget.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._flow_widget)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(spacing)
        self._col_count = 7
        self._row = 0
        self._col = 0
        super().addWidget(self._flow_widget)

    def addWidget(self, widget: QWidget) -> None:
        self._widgets.append(widget)
        self._grid.addWidget(widget, self._row, self._col)
        self._col += 1
        if self._col >= self._col_count:
            self._col = 0
            self._row += 1

    def removeWidget(self, widget: QWidget) -> None:
        self._grid.removeWidget(widget)
        if widget in self._widgets:
            self._widgets.remove(widget)

    def clear_all(self) -> None:
        for w in self._widgets:
            self._grid.removeWidget(w)
        self._widgets.clear()
        self._row = 0
        self._col = 0


# ═══════════════════════════════════════════════════════════════════
#  ANIME DETAIL VIEW
# ═══════════════════════════════════════════════════════════════════

class AnimeDetailView(QWidget):
    """Full anime details page with cover, synopsis, and episode list."""

    back_clicked = Signal()
    play_clicked = Signal(int)
    download_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_anime: str = ""
        self._episode_count: int = 0
        self._current_episode_idx: int = -1

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._content = QVBoxLayout(container)
        self._content.setContentsMargins(24, 16, 24, 24)
        self._content.setSpacing(20)

        # ── Back button ──
        header = QHBoxLayout()
        self._back_btn = QPushButton(" Voltar")
        self._back_btn.setObjectName("IconButton")
        self._back_btn.setIcon(QIcon(icon_arrow_left(16, "#A7ACB5")))
        self._back_btn.setIconSize(QSize(16, 16))
        self._back_btn.setStyleSheet("font-size: 14px; padding: 8px 16px;")
        self._back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._back_btn.clicked.connect(self.back_clicked.emit)
        header.addWidget(self._back_btn)
        header.addStretch()
        self._content.addLayout(header)

        # ── Metadata section ──
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(24)

        self._cover_label = QLabel()
        self._cover_label.setFixedSize(200, 280)
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setStyleSheet(
            "background: rgba(255,255,255,0.05); border-radius: 12px;"
        )
        meta_layout.addWidget(self._cover_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(12)

        self._title_label = QLabel("")
        self._title_label.setObjectName("ViewTitle")
        self._title_label.setWordWrap(True)
        info_layout.addWidget(self._title_label)

        self._synopsis = QTextEdit()
        self._synopsis.setReadOnly(True)
        self._synopsis.setFrameShape(QFrame.Shape.NoFrame)
        self._synopsis.setObjectName("MutedText")
        self._synopsis.setStyleSheet(
            "font-size: 13px; color: #A7ACB5; background: transparent; border: none;"
        )
        self._synopsis.setMinimumHeight(80)
        self._synopsis.setMaximumHeight(180)
        info_layout.addWidget(self._synopsis, 1)

        info_layout.addStretch()
        meta_layout.addLayout(info_layout, 1)
        self._content.addLayout(meta_layout)

        # ── Episodes header ──
        ep_header = QHBoxLayout()
        self._ep_title = QLabel("Episodios")
        self._ep_title.setObjectName("SectionTitleLarge")
        ep_header.addWidget(self._ep_title)

        self._ep_count_badge = QLabel("")
        self._ep_count_badge.setObjectName("Badge")
        self._ep_count_badge.setVisible(False)
        ep_header.addWidget(self._ep_count_badge)
        ep_header.addStretch()
        self._content.addLayout(ep_header)

        # Loading
        self._loading_label = QLabel("Carregando episodios...")
        self._loading_label.setObjectName("MutedText")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setVisible(False)
        self._content.addWidget(self._loading_label)

        # Episodes container
        self._episodes_container = QWidget()
        self._episodes_container.setStyleSheet("background: transparent;")
        self._episodes_layout = QVBoxLayout(self._episodes_container)
        self._episodes_layout.setContentsMargins(0, 0, 0, 0)
        self._episodes_layout.setSpacing(4)
        self._content.addWidget(self._episodes_container)

        # Empty state
        self._episodes_empty = EmptyState(
            icon_monitor(48, "rgba(255,255,255,0.12)"),
            "Nenhum episodio carregado",
            "Aguarde o carregamento...",
        )
        self._episodes_empty.setVisible(False)
        self._content.addWidget(self._episodes_empty)

        self._content.addStretch()
        self._scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

        self._episode_rows: list[EpisodeRow] = []

    def set_anime(self, name: str) -> None:
        self._current_anime = name
        self._title_label.setText(name)
        # Show dynamic cover immediately while real cover loads async
        if name:
            self._cover_label.setPixmap(generate_dynamic_cover(name, 200, 280, radius=12))
        else:
            self._cover_label.clear()
            self._cover_label.setStyleSheet(
                "background: rgba(255,255,255,0.05); border-radius: 12px;"
            )
        self._synopsis.setText("Buscando detalhes...")
        self._clear_episodes()
        self._loading_label.setVisible(True)
        self._episodes_empty.setVisible(False)

    def set_metadata(self, description: str | None, cover_path: str | None) -> None:
        if description:
            self._synopsis.setText(description)
        else:
            self._synopsis.setText("Sem sinopse disponivel.")

        if cover_path and os.path.exists(cover_path):
            self._set_cover(cover_path)

    def _set_cover(self, path: str) -> None:
        w, h = 200, 280
        source = QPixmap(path)
        if source.isNull():
            return
        scaled = source.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (scaled.width() - w) // 2
        y = (scaled.height() - h) // 2
        cropped = scaled.copy(x, y, w, h)
        rounded = QPixmap(w, h)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, 12, 12)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self._cover_label.setPixmap(rounded)

    def set_episodes(self, titles: list[str], current_index: int = -1) -> None:
        self._loading_label.setVisible(False)
        self._clear_episodes()
        self._episode_count = len(titles)

        if not titles:
            self._episodes_empty.setVisible(True)
            self._ep_count_badge.setVisible(False)
            return

        self._episodes_empty.setVisible(False)
        self._ep_count_badge.setText(f"{len(titles)} eps")
        self._ep_count_badge.setVisible(True)

        for i, title in enumerate(titles):
            row = EpisodeRow(i, title, is_current=(i == current_index))
            row.play_clicked.connect(self.play_clicked.emit)
            row.download_clicked.connect(self.download_clicked.emit)
            self._episode_rows.append(row)
            self._episodes_layout.addWidget(row)

    def highlight_episode(self, index: int) -> None:
        self._current_episode_idx = index
        for row in self._episode_rows:
            row.set_current(row.index == index)

    def _clear_episodes(self) -> None:
        for row in self._episode_rows:
            row.setParent(None)
            row.deleteLater()
        self._episode_rows.clear()

    def scroll_to_episode(self, index: int) -> None:
        if 0 <= index < len(self._episode_rows):
            self._scroll.ensureWidgetVisible(self._episode_rows[index])

    @property
    def anime_name(self) -> str:
        return self._current_anime

    @property
    def episode_count(self) -> int:
        return self._episode_count


# ═══════════════════════════════════════════════════════════════════
#  ACCOUNT VIEW
# ═══════════════════════════════════════════════════════════════════

class AccountView(QWidget):
    """AniList account connection view — shows login or profile + stats."""

    connect_clicked = Signal()
    disconnect_clicked = Signal()
    refresh_clicked = Signal()
    discord_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(0)

        # ─── Page header ─────────────────────────────────────────────
        page_title = QLabel("Conta")
        page_title.setStyleSheet("font-size: 22px; font-weight: 700; color: #F2F3F5;")
        outer.addWidget(page_title)
        outer.addSpacing(4)

        page_sub = QLabel("Gerencie sua conta AniList e integrações.")
        page_sub.setStyleSheet("font-size: 13px; color: #6B7280;")
        outer.addWidget(page_sub)
        outer.addSpacing(24)

        # ─── Cards row ───────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(20)
        cards_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # ── AniList card ──────────────────────────────────────────────
        self._card = QFrame()
        self._card.setObjectName("GlassPanel")
        self._card.setFixedWidth(400)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(0)

        # ─── Not connected ───────────────────────────────────────────
        self._not_connected = QWidget()
        nc = QVBoxLayout(self._not_connected)
        nc.setContentsMargins(0, 0, 0, 0)
        nc.setSpacing(0)
        nc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setPixmap(icon_user(52, "#A7ACB5"))
        nc.addWidget(icon_lbl)
        nc.addSpacing(18)

        nc_title = QLabel("AniList")
        nc_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nc_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #F2F3F5;")
        nc.addWidget(nc_title)
        nc.addSpacing(6)

        nc_sub = QLabel("Conecte sua conta para sincronizar\nseu progresso automaticamente.")
        nc_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nc_sub.setStyleSheet("font-size: 12px; color: #6B7280;")
        nc.addWidget(nc_sub)
        nc.addSpacing(18)

        benefits_box = QFrame()
        benefits_box.setObjectName("BenefitsBox")
        benefits_box.setStyleSheet(
            "QFrame#BenefitsBox { background: rgba(255,255,255,0.03);"
            " border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; }"
        )
        bl = QVBoxLayout(benefits_box)
        bl.setContentsMargins(14, 10, 14, 10)
        bl.setSpacing(6)
        for text in [
            "Tracking autom\u00e1tico de epis\u00f3dios assistidos",
            "Stats importados da sua conta AniList",
            "Lista atualizada em tempo real ap\u00f3s cada ep",
        ]:
            row = QHBoxLayout()
            row.setSpacing(8)
            dot = QLabel("\u2713")
            dot.setFixedWidth(14)
            dot.setStyleSheet("color: #3DD68C; font-size: 11px; font-weight: 700;")
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size: 11px; color: #6B7280;")
            row.addWidget(dot)
            row.addWidget(lbl, 1)
            bl.addLayout(row)
        nc.addWidget(benefits_box)
        nc.addSpacing(18)

        self._connect_btn = AnimatedButton("Conectar com AniList")
        self._connect_btn.setObjectName("PrimaryButton")
        self._connect_btn.setFixedHeight(42)
        self._connect_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._connect_btn.clicked.connect(self.connect_clicked.emit)
        nc.addWidget(self._connect_btn)

        card_layout.addWidget(self._not_connected)

        # ─── Connected ───────────────────────────────────────────────
        self._connected = QWidget()
        co = QVBoxLayout(self._connected)
        co.setContentsMargins(0, 0, 0, 0)
        co.setSpacing(0)

        # Profile header — avatar left, name+badge right
        profile_row = QHBoxLayout()
        profile_row.setSpacing(14)
        profile_row.setContentsMargins(0, 0, 0, 0)

        self._avatar_label = QLabel()
        self._avatar_label.setFixedSize(56, 56)
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar_label.setStyleSheet(
            "background: rgba(255,255,255,0.08); border-radius: 28px;"
        )
        profile_row.addWidget(self._avatar_label, 0, Qt.AlignmentFlag.AlignVCenter)

        name_col = QVBoxLayout()
        name_col.setSpacing(3)
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._username_label = QLabel("")
        self._username_label.setStyleSheet("font-size: 17px; font-weight: 700; color: #F2F3F5;")
        name_col.addWidget(self._username_label)

        ok_badge = QLabel("\u25cf  Conectado ao AniList")
        ok_badge.setStyleSheet("color: #3DD68C; font-size: 11px; font-weight: 600; letter-spacing: 0.4px;")
        name_col.addWidget(ok_badge)

        profile_row.addLayout(name_col, 1)
        co.addLayout(profile_row)
        co.addSpacing(20)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(255,255,255,0.07);")
        co.addWidget(div)
        co.addSpacing(18)

        # Stats row
        stats_frame = QFrame()
        stats_frame.setObjectName("StatsFrame")
        stats_frame.setStyleSheet("QFrame#StatsFrame { background: rgba(255,255,255,0.04); border-radius: 10px; }")
        stats_row = QHBoxLayout(stats_frame)
        stats_row.setContentsMargins(0, 16, 0, 16)
        stats_row.setSpacing(0)

        self._stat_labels: dict[str, QLabel] = {}
        for i, (key, label_text) in enumerate([
            ("animes", "ANIMES"),
            ("episodes", "EPIS\u00d3DIOS"),
            ("hours", "TEMPO"),
        ]):
            if i > 0:
                vsep = QFrame()
                vsep.setFrameShape(QFrame.Shape.VLine)
                vsep.setFixedWidth(1)
                vsep.setStyleSheet("color: rgba(255,255,255,0.07);")
                stats_row.addWidget(vsep)

            cell = QWidget()
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(4)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            val = QLabel("\u2014")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val.setStyleSheet("font-size: 22px; font-weight: 700; color: #F2F3F5;")
            self._stat_labels[key] = val

            name_lbl = QLabel(label_text)
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_lbl.setStyleSheet("font-size: 10px; color: #6B7280; letter-spacing: 1px;")

            cl.addWidget(val)
            cl.addWidget(name_lbl)
            stats_row.addWidget(cell, 1)

        co.addWidget(stats_frame)
        co.addSpacing(6)

        anilist_src = QLabel("\u2b24  Dados do AniList \u00b7 Sincronizado automaticamente")
        anilist_src.setAlignment(Qt.AlignmentFlag.AlignCenter)
        anilist_src.setStyleSheet("font-size: 10px; color: #3B3E4A; letter-spacing: 0.3px;")
        co.addWidget(anilist_src, 0, Qt.AlignmentFlag.AlignHCenter)
        co.addSpacing(16)

        # How tracking works
        how_box = QFrame()
        how_box.setObjectName("HowBox")
        how_box.setStyleSheet(
            "QFrame#HowBox { background: rgba(255,255,255,0.03);"
            " border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; }"
        )
        hl = QVBoxLayout(how_box)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(6)

        how_title = QLabel("Como o tracking funciona")
        how_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #7B8194;"
                                " letter-spacing: 0.8px;")
        hl.addWidget(how_title)
        hl.addSpacing(3)

        for icon, text in [
            ("\u25b6", "Epis\u00f3dio registrado ap\u00f3s 30s assistidos"),
            ("\u21bb", "Stats atualizados ap\u00f3s fechar o player"),
            ("\u2605", "Progresso importado ao abrir esta tela"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(10)
            ic = QLabel(icon)
            ic.setFixedWidth(14)
            ic.setStyleSheet("color: #D44242; font-size: 12px;")
            lb = QLabel(text)
            lb.setStyleSheet("font-size: 12px; color: #9DA3B4;")
            row.addWidget(ic)
            row.addWidget(lb, 1)
            hl.addLayout(row)

        co.addWidget(how_box)
        co.addSpacing(14)

        _subtle_btn = (
            "QPushButton { color: #6B7280; background: transparent;"
            " border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; font-size: 12px; }"
            "QPushButton:hover { color: #E57373;"
            " border-color: rgba(229,115,115,0.35); background: rgba(229,115,115,0.06); }"
            "QPushButton:disabled { color: #3B3E4A;"
            " border-color: rgba(255,255,255,0.04); }"
        )

        # Action buttons side by side
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._refresh_btn = AnimatedButton("\u21bb  Atualizar")
        self._refresh_btn.setFixedHeight(36)
        self._refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._refresh_btn.setStyleSheet(_subtle_btn)
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        btn_row.addWidget(self._refresh_btn)

        self._disconnect_btn = AnimatedButton("Desconectar")
        self._disconnect_btn.setFixedHeight(36)
        self._disconnect_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._disconnect_btn.setStyleSheet(_subtle_btn)
        self._disconnect_btn.clicked.connect(self.disconnect_clicked.emit)
        btn_row.addWidget(self._disconnect_btn)

        co.addLayout(btn_row)

        self._cooldown_remaining = 0
        self._cooldown_ticker = QTimer(self)
        self._cooldown_ticker.setInterval(1000)
        self._cooldown_ticker.timeout.connect(self._tick_cooldown)

        card_layout.addWidget(self._connected)

        self._not_connected.setVisible(True)
        self._connected.setVisible(False)

        cards_row.addWidget(self._card, 0, Qt.AlignmentFlag.AlignTop)

        # ── Discord card ──────────────────────────────────────────────
        self._discord_card = QFrame()
        self._discord_card.setObjectName("GlassPanel")
        self._discord_card.setFixedWidth(320)
        dc = QVBoxLayout(self._discord_card)
        dc.setContentsMargins(24, 24, 24, 24)
        dc.setSpacing(14)

        # Header row
        hdr = QHBoxLayout()
        hdr.setSpacing(10)
        dc_icon = QLabel("\u2665")
        dc_icon.setStyleSheet("font-size: 16px; color: #5865F2;")
        hdr.addWidget(dc_icon)
        dc_title = QLabel("Discord")
        dc_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #F2F3F5;")
        hdr.addWidget(dc_title, 1)
        self._discord_toggle = AnimatedButton("Ativar")
        self._discord_toggle.setCheckable(True)
        self._discord_toggle.setFixedSize(68, 28)
        self._discord_toggle.setStyleSheet(
            "QPushButton { font-size: 11px; font-weight: 600; color: #6B7280;"
            " background: rgba(255,255,255,0.05);"
            " border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; }"
            "QPushButton:checked { color: #3DD68C;"
            " background: rgba(61,214,140,0.1);"
            " border-color: rgba(61,214,140,0.3); }"
            "QPushButton:hover { border-color: rgba(255,255,255,0.2); }"
        )
        self._discord_toggle.clicked.connect(self._on_discord_toggle_clicked)
        hdr.addWidget(self._discord_toggle)
        dc.addLayout(hdr)

        dc_sub = QLabel("Mostra o anime que você está assistindo no seu perfil do Discord em tempo real.")
        dc_sub.setWordWrap(True)
        dc_sub.setStyleSheet("font-size: 11px; color: #4B5160;")
        dc.addWidget(dc_sub)

        # Divider
        dc_div = QFrame()
        dc_div.setFrameShape(QFrame.Shape.HLine)
        dc_div.setStyleSheet("color: rgba(255,255,255,0.06);")
        dc.addWidget(dc_div)

        # Status
        self._discord_status = QLabel("\u25cf  Desconectado")
        self._discord_status.setStyleSheet("font-size: 11px; color: #4B5160;")
        dc.addWidget(self._discord_status)

        # Setup checklist
        setup_box = QFrame()
        setup_box.setObjectName("DiscordSetupBox")
        setup_box.setStyleSheet(
            "QFrame#DiscordSetupBox { background: rgba(255,255,255,0.03);"
            " border: 1px solid rgba(255,255,255,0.07); border-radius: 8px; }"
        )
        sbl = QVBoxLayout(setup_box)
        sbl.setContentsMargins(12, 10, 12, 10)
        sbl.setSpacing(7)

        setup_title = QLabel("Para funcionar:")
        setup_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #7B8194; letter-spacing: 0.5px;")
        sbl.addWidget(setup_title)

        for num, text in [
            ("1", "Abra o Discord → Configurações"),
            ("2", "Privacidade de Atividade"),
            ("3", "Ative \u201cExibir atividade atual\u201d"),
        ]:
            step_row = QHBoxLayout()
            step_row.setSpacing(8)
            step_num = QLabel(num)
            step_num.setFixedSize(16, 16)
            step_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step_num.setStyleSheet(
                "background: rgba(88,101,242,0.25); border-radius: 8px;"
                " font-size: 9px; font-weight: 700; color: #8891F2;"
            )
            step_lbl = QLabel(text)
            step_lbl.setStyleSheet("font-size: 11px; color: #6B7280;")
            step_row.addWidget(step_num)
            step_row.addWidget(step_lbl, 1)
            sbl.addLayout(step_row)

        dc.addWidget(setup_box)

        # Preview
        preview_box = QFrame()
        preview_box.setObjectName("DiscordPreviewBox")
        preview_box.setStyleSheet(
            "QFrame#DiscordPreviewBox { background: rgba(88,101,242,0.06);"
            " border: 1px solid rgba(88,101,242,0.12); border-radius: 8px; }"
        )
        pbl = QVBoxLayout(preview_box)
        pbl.setContentsMargins(12, 9, 12, 9)
        pbl.setSpacing(3)
        pb_title = QLabel("Aparece assim no Discord:")
        pb_title.setStyleSheet("font-size: 10px; color: #5865F2; font-weight: 600;")
        pbl.addWidget(pb_title)
        pb_ex1 = QLabel("\u25b6  One Piece")
        pb_ex1.setStyleSheet("font-size: 11px; color: #9DA3B4;")
        pbl.addWidget(pb_ex1)
        pb_ex2 = QLabel("    Ep 3 de 24 \u00b7 h\u00e1 2 min")
        pb_ex2.setStyleSheet("font-size: 10px; color: #4B5160;")
        pbl.addWidget(pb_ex2)
        dc.addWidget(preview_box)

        dc.addStretch()

        cards_row.addWidget(self._discord_card, 0, Qt.AlignmentFlag.AlignTop)

        outer.addLayout(cards_row)
        outer.addStretch()

    def _on_discord_toggle_clicked(self) -> None:
        enabled = self._discord_toggle.isChecked()
        self._discord_toggle.setText("Ativado" if enabled else "Ativar")
        self.discord_toggled.emit(enabled)

    def set_discord_state(self, enabled: bool, connected: bool) -> None:
        self._discord_toggle.setChecked(enabled)
        self._discord_toggle.setText("Ativado" if enabled else "Ativar")
        if connected:
            self._discord_status.setText("\u25cf  Conectado ao Discord")
            self._discord_status.setStyleSheet("font-size: 11px; color: #3DD68C;")
        else:
            self._discord_status.setText("\u25cf  Desconectado")
            self._discord_status.setStyleSheet("font-size: 11px; color: #4B5160;")

    _COOLDOWN_SECS = 300  # 5 minutes

    def _on_refresh_clicked(self) -> None:
        self.refresh_clicked.emit()
        self._cooldown_remaining = self._COOLDOWN_SECS
        self._refresh_btn.setEnabled(False)
        self._cooldown_ticker.start()
        self._update_cooldown_label()

    def _tick_cooldown(self) -> None:
        self._cooldown_remaining -= 1
        if self._cooldown_remaining <= 0:
            self._cooldown_ticker.stop()
            self._refresh_btn.setEnabled(True)
            self._refresh_btn.setText("\u21bb  Atualizar")
        else:
            self._update_cooldown_label()

    def _update_cooldown_label(self) -> None:
        m, s = divmod(self._cooldown_remaining, 60)
        self._refresh_btn.setText(f"\u21bb  Aguarde {m}:{s:02d}")

    def set_authenticated(self, user: dict | None) -> None:
        if user:
            self._not_connected.setVisible(False)
            self._connected.setVisible(True)
            self._username_label.setText(user.get("username") or "")
            self._stat_labels["animes"].setText(str(user.get("anime_count", 0)))
            self._stat_labels["episodes"].setText(str(user.get("episodes_watched", 0)))
            total_mins = user.get("minutes_watched") or 0
            h, m = divmod(total_mins, 60)
            hours_text = f"{h}h {m}m" if m else f"{h}h"
            self._stat_labels["hours"].setText(hours_text)
        else:
            self._not_connected.setVisible(True)
            self._connected.setVisible(False)
            self._avatar_label.setStyleSheet(
                "background: rgba(255,255,255,0.08); border-radius: 28px;"
            )
            self._connect_btn.setEnabled(True)
            self._connect_btn.setText("Conectar com AniList")

    def set_avatar_pixmap(self, pixmap: QPixmap) -> None:
        w, h = 56, 56
        scaled = pixmap.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (scaled.width() - w) // 2
        y = (scaled.height() - h) // 2
        cropped = scaled.copy(x, y, w, h)
        rounded = QPixmap(w, h)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addEllipse(0, 0, w, h)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self._avatar_label.setPixmap(rounded)
        self._avatar_label.setStyleSheet("")

    def set_connecting(self, connecting: bool) -> None:
        self._connect_btn.setEnabled(not connecting)
        self._connect_btn.setText("Aguardando..." if connecting else "Conectar com AniList")


# ═══════════════════════════════════════════════════════════════════
#  DOWNLOADS VIEW
# ═══════════════════════════════════════════════════════════════════

_COVER_W, _COVER_H = 56, 80   # small portrait — card height driven by content
_MAX_VISIBLE_EPS = 2           # episodes shown before collapse


class _DownloadRow(QFrame):
    play_clicked   = Signal(object)
    delete_clicked = Signal(object)

    def __init__(self, entry: DownloadEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self.setObjectName("DownloadRow")
        self.setStyleSheet(
            "QFrame#DownloadRow { background: transparent; border-radius: 4px; }"
            "QFrame#DownloadRow:hover { background: rgba(255,255,255,0.04); }"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(10)

        ep_lbl = QLabel(f"EP {entry.episode_num:02d}")
        ep_lbl.setFixedWidth(42)
        ep_lbl.setFixedHeight(18)
        ep_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ep_lbl.setStyleSheet(
            "background: rgba(255,255,255,0.07); border-radius: 3px;"
            "color: #9CA3AF; font-size: 10px; font-weight: 700;"
        )
        row.addWidget(ep_lbl)

        title_lbl = QLabel(f"Epis\u00f3dio {entry.episode_num}")
        title_lbl.setStyleSheet("font-size: 12px; color: #C9CBD0;")
        row.addWidget(title_lbl, 1)

        size_lbl = QLabel(entry.size_str)
        size_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        size_lbl.setStyleSheet("font-size: 11px; color: #6B7280; min-width: 48px;")
        row.addWidget(size_lbl)

        play_btn = QPushButton("\u25b6\u2009Assistir")
        play_btn.setObjectName("PrimaryButton")
        play_btn.setFixedHeight(24)
        play_btn.setStyleSheet("QPushButton#PrimaryButton { font-size: 11px; padding: 0 10px; }")
        play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        play_btn.clicked.connect(lambda checked=False, e=entry: self.play_clicked.emit(e))
        row.addWidget(play_btn)

        del_btn = QPushButton("\u2715")
        del_btn.setFixedSize(24, 24)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setToolTip("Remover")
        del_btn.setStyleSheet(
            "QPushButton { color: #4B5563; background: transparent;"
            " border: 1px solid rgba(255,255,255,0.06); border-radius: 4px; font-size: 10px; }"
            "QPushButton:hover { color: #E57373; border-color: rgba(229,115,115,0.35);"
            " background: rgba(229,115,115,0.06); }"
        )
        del_btn.clicked.connect(lambda checked=False, e=entry: self.delete_clicked.emit(e))
        row.addWidget(del_btn)


class _AnimeGroupCard(QFrame):
    play_clicked   = Signal(object)
    delete_clicked = Signal(object)

    def __init__(
        self,
        anime: str,
        entries: list,
        cover_path: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GlassPanel")
        self._anime = anime
        self._extra_rows: list[_DownloadRow] = []
        self._expanded = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 10)
        outer.setSpacing(14)

        # ── Cover (anchored top, no stretch) ─────────────────────
        self._cover_lbl = QLabel()
        self._cover_lbl.setFixedSize(_COVER_W, _COVER_H)
        self._cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if cover_path:
            self._apply_cover(cover_path)
        else:
            self._cover_lbl.setPixmap(generate_dynamic_cover(anime, _COVER_W, _COVER_H, radius=6))
        outer.addWidget(self._cover_lbl, 0, Qt.AlignmentFlag.AlignTop)

        # ── Content (fills remaining width, no stretch at bottom) ─
        content = QVBoxLayout()
        content.setContentsMargins(0, 1, 0, 0)
        content.setSpacing(0)

        title_lbl = QLabel(anime)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #F2F3F5;")
        title_lbl.setWordWrap(True)
        content.addWidget(title_lbl)
        content.addSpacing(2)

        ep_count = len(entries)
        total_mb = sum(e.file_size for e in entries) / (1024 * 1024)
        size_str = f"{total_mb / 1024:.1f} GB" if total_mb >= 1024 else f"{total_mb:.0f} MB"
        meta_lbl = QLabel(
            f"{ep_count}\u00a0epis\u00f3dio{'s' if ep_count > 1 else ''}  \u00b7  {size_str}"
        )
        meta_lbl.setStyleSheet("font-size: 11px; color: #6B7280;")
        content.addWidget(meta_lbl)
        content.addSpacing(8)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(255,255,255,0.06);")
        content.addWidget(div)
        content.addSpacing(1)

        sorted_entries = sorted(entries, key=lambda e: e.episode_num)
        for i, entry in enumerate(sorted_entries):
            r = _DownloadRow(entry)
            r.play_clicked.connect(self.play_clicked.emit)
            r.delete_clicked.connect(self.delete_clicked.emit)
            content.addWidget(r)
            if i >= _MAX_VISIBLE_EPS:
                r.setVisible(False)
                self._extra_rows.append(r)

        if self._extra_rows:
            n = len(self._extra_rows)
            self._expand_btn = QPushButton(f"\u25be  {n} epis\u00f3dio{'s' if n > 1 else ''} a mais")
            self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._expand_btn.setStyleSheet(
                "QPushButton { color: #6B7280; background: transparent; border: none;"
                " font-size: 11px; text-align: left; padding: 4px 4px 0 4px; }"
                "QPushButton:hover { color: #A7ACB5; }"
            )
            self._expand_btn.clicked.connect(self._toggle_expand)
            content.addWidget(self._expand_btn)

        outer.addLayout(content, 1)

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        for r in self._extra_rows:
            r.setVisible(self._expanded)
        n = len(self._extra_rows)
        if self._expanded:
            self._expand_btn.setText("\u25b4  Recolher")
        else:
            self._expand_btn.setText(f"\u25be  {n} epis\u00f3dio{'s' if n > 1 else ''} a mais")

    def set_cover(self, path: str) -> None:
        self._apply_cover(path)

    def _apply_cover(self, path: str) -> None:
        pm = QPixmap(path)
        if pm.isNull():
            return
        w, h = _COVER_W, _COVER_H
        scaled = pm.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (scaled.width() - w) // 2
        y = (scaled.height() - h) // 2
        cropped = scaled.copy(x, y, w, h)
        rounded = QPixmap(w, h)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, 6, 6)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self._cover_lbl.setPixmap(rounded)
        self._cover_lbl.setStyleSheet("")


# ── Manga download rows ──────────────────────────────────────────────


class _MangaChapterRow(QFrame):
    delete_clicked = Signal(object)
    open_clicked   = Signal(object)

    def __init__(self, entry: MangaDownloadEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self.setObjectName("DownloadRow")
        self.setStyleSheet(
            "QFrame#DownloadRow { background: transparent; border-radius: 4px; }"
            "QFrame#DownloadRow:hover { background: rgba(255,255,255,0.04); }"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(10)

        ch_lbl = QLabel(entry.chapter_label)
        ch_lbl.setStyleSheet("font-size: 12px; color: #C9CBD0;")
        row.addWidget(ch_lbl, 1)

        if entry.page_count:
            pg_lbl = QLabel(f"{entry.page_count}p")
            pg_lbl.setStyleSheet("font-size: 11px; color: #6B7280;")
            row.addWidget(pg_lbl)

        size_lbl = QLabel(entry.size_str)
        size_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        size_lbl.setStyleSheet("font-size: 11px; color: #6B7280; min-width: 52px;")
        row.addWidget(size_lbl)

        cbz_badge = QLabel("CBZ")
        cbz_badge.setStyleSheet(
            "background: rgba(100,160,255,0.12); color: #7EB3FF;"
            " border: 1px solid rgba(100,160,255,0.25); border-radius: 3px;"
            " padding: 1px 5px; font-size: 9px; font-weight: 700;"
        )
        row.addWidget(cbz_badge)

        read_btn = QPushButton("Ler")
        read_btn.setFixedHeight(26)
        read_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        read_btn.setStyleSheet(
            "QPushButton { color: #7EB3FF; background: rgba(100,160,255,0.10);"
            " border: 1px solid rgba(100,160,255,0.25); border-radius: 4px;"
            " font-size: 11px; padding: 0 10px; }"
            "QPushButton:hover { background: rgba(100,160,255,0.22); border-color: rgba(100,160,255,0.5); }"
        )
        read_btn.clicked.connect(lambda checked=False, e=entry: self.open_clicked.emit(e))
        row.addWidget(read_btn)

        del_btn = QPushButton("Remover")
        del_btn.setFixedHeight(26)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            "QPushButton { color: #B06060; background: rgba(180,60,60,0.08);"
            " border: 1px solid rgba(180,60,60,0.22); border-radius: 4px;"
            " font-size: 11px; padding: 0 10px; }"
            "QPushButton:hover { color: #E57373; border-color: rgba(229,115,115,0.5);"
            " background: rgba(229,115,115,0.15); }"
        )
        del_btn.clicked.connect(lambda checked=False, e=entry: self.delete_clicked.emit(e))
        row.addWidget(del_btn)


class _MangaGroupCard(QFrame):
    delete_clicked = Signal(object)
    open_clicked   = Signal(object)

    def __init__(
        self,
        manga_title: str,
        entries: list,
        cover_path: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GlassPanel")
        self._manga_title = manga_title
        self._extra_rows: list[_MangaChapterRow] = []
        self._expanded = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 10)
        outer.setSpacing(14)

        self._cover_lbl = QLabel()
        self._cover_lbl.setFixedSize(_COVER_W, _COVER_H)
        self._cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if cover_path:
            self._apply_cover(cover_path)
        else:
            self._cover_lbl.setPixmap(generate_dynamic_cover(manga_title, _COVER_W, _COVER_H, radius=6))
        outer.addWidget(self._cover_lbl, 0, Qt.AlignmentFlag.AlignTop)

        content = QVBoxLayout()
        content.setContentsMargins(0, 1, 0, 0)
        content.setSpacing(0)

        title_lbl = QLabel(manga_title)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #F2F3F5;")
        title_lbl.setWordWrap(True)
        content.addWidget(title_lbl)
        content.addSpacing(2)

        ch_count = len(entries)
        total_mb = sum(e.file_size for e in entries) / (1024 * 1024)
        size_str = f"{total_mb / 1024:.1f} GB" if total_mb >= 1024 else f"{total_mb:.0f} MB"
        meta_lbl = QLabel(
            f"{ch_count}\u00a0cap\u00edtulo{'s' if ch_count > 1 else ''}  \u00b7  {size_str}"
        )
        meta_lbl.setStyleSheet("font-size: 11px; color: #6B7280;")
        content.addWidget(meta_lbl)
        content.addSpacing(8)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(255,255,255,0.06);")
        content.addWidget(div)
        content.addSpacing(1)

        for i, entry in enumerate(entries):
            r = _MangaChapterRow(entry)
            r.delete_clicked.connect(self.delete_clicked.emit)
            r.open_clicked.connect(self.open_clicked.emit)
            content.addWidget(r)
            if i >= _MAX_VISIBLE_EPS:
                r.setVisible(False)
                self._extra_rows.append(r)

        if self._extra_rows:
            n = len(self._extra_rows)
            self._expand_btn = QPushButton(f"\u25be  {n} cap\u00edtulo{'s' if n > 1 else ''} a mais")
            self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._expand_btn.setStyleSheet(
                "QPushButton { color: #6B7280; background: transparent; border: none;"
                " font-size: 11px; text-align: left; padding: 4px 4px 0 4px; }"
                "QPushButton:hover { color: #A7ACB5; }"
            )
            self._expand_btn.clicked.connect(self._toggle_expand)
            content.addWidget(self._expand_btn)

        outer.addLayout(content, 1)

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        for r in self._extra_rows:
            r.setVisible(self._expanded)
        n = len(self._extra_rows)
        if self._expanded:
            self._expand_btn.setText("\u25b4  Recolher")
        else:
            self._expand_btn.setText(f"\u25be  {n} cap\u00edtulo{'s' if n > 1 else ''} a mais")

    def set_cover(self, path: str) -> None:
        self._apply_cover(path)

    def _apply_cover(self, path: str) -> None:
        pm = QPixmap(path)
        if pm.isNull():
            return
        w, h = _COVER_W, _COVER_H
        scaled = pm.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (scaled.width() - w) // 2
        y = (scaled.height() - h) // 2
        cropped = scaled.copy(x, y, w, h)
        rounded = QPixmap(w, h)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, 6, 6)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        self._cover_lbl.setPixmap(rounded)
        self._cover_lbl.setStyleSheet("")


# ── Tab button helper ──────────────────────────────────────────────────

_TAB_ACTIVE = (
    "QPushButton { color: #F2F3F5; background: rgba(255,255,255,0.08);"
    " border: none; border-bottom: 2px solid #D44242; border-radius: 0;"
    " font-size: 13px; font-weight: 600; padding: 0 20px; }"
)
_TAB_IDLE = (
    "QPushButton { color: #6B7280; background: transparent;"
    " border: none; border-bottom: 2px solid transparent; border-radius: 0;"
    " font-size: 13px; padding: 0 20px; }"
    "QPushButton:hover { color: #A7ACB5; }"
)


def _make_scroll_panel() -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    body = QWidget()
    body.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(body)
    layout.setContentsMargins(28, 12, 28, 28)
    layout.setSpacing(10)
    scroll.setWidget(body)
    return scroll, body, layout


class DownloadsView(QWidget):
    """Offline library — Anime and Manga tabs."""

    play_clicked         = Signal(object)
    delete_clicked       = Signal(object)
    open_folder_clicked  = Signal()
    manga_delete_clicked = Signal(object)
    manga_open_clicked   = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Fixed header ──────────────────────────────────────────
        header_widget = QWidget()
        header_widget.setStyleSheet("background: transparent;")
        hv = QVBoxLayout(header_widget)
        hv.setContentsMargins(28, 20, 28, 0)
        hv.setSpacing(0)

        title_row = QHBoxLayout()
        title_lbl = QLabel("Downloads")
        title_lbl.setObjectName("SectionTitleLarge")
        title_row.addWidget(title_lbl)
        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet("font-size: 12px; color: #6B7280; padding-top: 5px;")
        title_row.addWidget(self._stats_lbl)
        title_row.addStretch()
        self._open_btn = QPushButton("  Abrir Pasta")
        self._open_btn.setIcon(QIcon(icon_folder(13, "#A7ACB5")))
        self._open_btn.setFixedHeight(30)
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.setStyleSheet(
            "QPushButton { color: #A7ACB5; background: rgba(255,255,255,0.05);"
            " border: 1px solid rgba(255,255,255,0.09); border-radius: 6px;"
            " font-size: 12px; padding: 0 12px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.09); color: #F2F3F5; }"
        )
        self._open_btn.clicked.connect(self.open_folder_clicked.emit)
        title_row.addWidget(self._open_btn)
        hv.addLayout(title_row)
        hv.addSpacing(14)

        # Tab bar
        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(0)
        self._tab_anime = QPushButton("Anime")
        self._tab_anime.setFixedHeight(36)
        self._tab_anime.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_manga = QPushButton("Manga")
        self._tab_manga.setFixedHeight(36)
        self._tab_manga.setCursor(Qt.CursorShape.PointingHandCursor)
        tab_row.addWidget(self._tab_anime)
        tab_row.addWidget(self._tab_manga)
        tab_row.addStretch()
        hv.addLayout(tab_row)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(255,255,255,0.06); margin: 0;")
        hv.addWidget(div)

        root.addWidget(header_widget)

        # ── Scrollable panels ────────────────────────────────────
        self._anime_scroll, _, self._anime_layout = _make_scroll_panel()
        self._manga_scroll, _, self._manga_layout = _make_scroll_panel()

        root.addWidget(self._anime_scroll, 1)
        root.addWidget(self._manga_scroll, 1)

        # ── Empty states ─────────────────────────────────────────
        self._anime_empty = self._make_empty("Nenhum download encontrado",
                                              "Baixe epis\u00f3dios na tela de detalhes\npara assistir offline")
        self._manga_empty = self._make_empty("Nenhum mangá baixado",
                                              "Baixe capítulos na tela de detalhes do mangá\npara ler offline (.cbz)")
        self._anime_layout.addWidget(self._anime_empty)
        self._manga_layout.addWidget(self._manga_empty)

        self._anime_cards: dict[str, _AnimeGroupCard] = {}
        self._manga_cards: dict[str, _MangaGroupCard] = {}

        self._tab_anime.clicked.connect(lambda: self._switch_tab("anime"))
        self._tab_manga.clicked.connect(lambda: self._switch_tab("manga"))
        self._switch_tab("anime")

    # ── Tab switching ─────────────────────────────────────────────

    def _switch_tab(self, tab: str) -> None:
        self._active_tab = tab
        anime_on = (tab == "anime")
        self._anime_scroll.setVisible(anime_on)
        self._manga_scroll.setVisible(not anime_on)
        self._tab_anime.setStyleSheet(_TAB_ACTIVE if anime_on else _TAB_IDLE)
        self._tab_manga.setStyleSheet(_TAB_ACTIVE if not anime_on else _TAB_IDLE)
        self._stats_lbl.setText(self._anime_stats if anime_on else self._manga_stats)
        self._open_btn.setVisible(anime_on)

    # ── Anime tab ────────────────────────────────────────────────

    _anime_stats: str = ""
    _manga_stats: str = ""

    def set_downloads(self, groups: dict, cover_cache: dict | None = None) -> None:
        for card in self._anime_cards.values():
            card.setParent(None)
            card.deleteLater()
        self._anime_cards.clear()
        while self._anime_layout.count() > 0:
            item = self._anime_layout.takeAt(0)
            w = item.widget()
            if w and w is not self._anime_empty:
                w.setParent(None)
                w.deleteLater()

        if not groups:
            self._anime_stats = ""
            self._anime_layout.addWidget(self._anime_empty)
            self._anime_empty.show()
            if getattr(self, "_active_tab", "anime") == "anime":
                self._stats_lbl.setText("")
            return

        self._anime_empty.hide()
        total_eps = sum(len(eps) for eps in groups.values())
        total_mb = sum(e.file_size for eps in groups.values() for e in eps) / (1024 * 1024)
        size_disp = f"{total_mb / 1024:.1f} GB" if total_mb >= 1024 else f"{total_mb:.0f} MB"
        count = len(groups)
        self._anime_stats = (
            f"{count}\u00a0anime{'s' if count > 1 else ''}  \u00b7  "
            f"{total_eps}\u00a0ep{'s' if total_eps > 1 else ''}  \u00b7  {size_disp}"
        )
        if getattr(self, "_active_tab", "anime") == "anime":
            self._stats_lbl.setText(self._anime_stats)

        for anime, entries in sorted(groups.items(), key=lambda x: x[0].lower()):
            cover = (cover_cache or {}).get(anime)
            card = _AnimeGroupCard(anime, entries, cover)
            card.play_clicked.connect(self.play_clicked.emit)
            card.delete_clicked.connect(self.delete_clicked.emit)
            self._anime_cards[anime] = card
            self._anime_layout.addWidget(card)
        self._anime_layout.addStretch()

    def update_cover(self, anime: str, cover_path: str) -> None:
        if anime in self._anime_cards:
            self._anime_cards[anime].set_cover(cover_path)

    # ── Manga tab ────────────────────────────────────────────────

    def set_manga_downloads(self, groups: dict, cover_cache: dict | None = None) -> None:
        for card in self._manga_cards.values():
            card.setParent(None)
            card.deleteLater()
        self._manga_cards.clear()
        while self._manga_layout.count() > 0:
            item = self._manga_layout.takeAt(0)
            w = item.widget()
            if w and w is not self._manga_empty:
                w.setParent(None)
                w.deleteLater()

        if not groups:
            self._manga_stats = ""
            self._manga_layout.addWidget(self._manga_empty)
            self._manga_empty.show()
            if getattr(self, "_active_tab", "anime") == "manga":
                self._stats_lbl.setText("")
            return

        self._manga_empty.hide()
        total_ch = sum(len(chs) for chs in groups.values())
        total_mb = sum(e.file_size for chs in groups.values() for e in chs) / (1024 * 1024)
        size_disp = f"{total_mb / 1024:.1f} GB" if total_mb >= 1024 else f"{total_mb:.0f} MB"
        count = len(groups)
        self._manga_stats = (
            f"{count}\u00a0manga{'s' if count > 1 else ''}  \u00b7  "
            f"{total_ch}\u00a0cap\u00edtulo{'s' if total_ch > 1 else ''}  \u00b7  {size_disp}"
        )
        if getattr(self, "_active_tab", "anime") == "manga":
            self._stats_lbl.setText(self._manga_stats)

        for manga_title, entries in sorted(groups.items(), key=lambda x: x[0].lower()):
            cover = (cover_cache or {}).get(manga_title)
            card = _MangaGroupCard(manga_title, entries, cover)
            card.delete_clicked.connect(self.manga_delete_clicked.emit)
            card.open_clicked.connect(self.manga_open_clicked.emit)
            self._manga_cards[manga_title] = card
            self._manga_layout.addWidget(card)
        self._manga_layout.addStretch()

    def update_manga_cover(self, manga_title: str, path: str) -> None:
        if manga_title in self._manga_cards:
            self._manga_cards[manga_title].set_cover(path)

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _make_empty(title: str, subtitle: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 60, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        lay.setSpacing(10)
        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setPixmap(icon_folder(48, "#2E3040"))
        lay.addWidget(icon_lbl)
        et = QLabel(title)
        et.setAlignment(Qt.AlignmentFlag.AlignCenter)
        et.setStyleSheet("font-size: 15px; font-weight: 600; color: #3E4255;")
        lay.addWidget(et)
        es = QLabel(subtitle)
        es.setAlignment(Qt.AlignmentFlag.AlignCenter)
        es.setStyleSheet("font-size: 12px; color: #2E3040; line-height: 1.6;")
        lay.addWidget(es)
        return w
