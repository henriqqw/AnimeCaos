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
    icon_clock,
    icon_folder,
    icon_loader,
    icon_monitor,
    icon_search,
    icon_search_x,
    icon_user,
)
from animecaos.services.downloads_service import DownloadEntry
from .loading_overlay import LoadingOverlay


# ═══════════════════════════════════════════════════════════════════
#  ANIMATED BUTTON
# ═══════════════════════════════════════════════════════════════════

class AnimatedButton(QPushButton):
    """QPushButton with a smooth opacity fade on press/release."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def mousePressEvent(self, event):
        self._anim.stop()
        self._anim.setDuration(80)
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.55)
        self._anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._anim.stop()
        self._anim.setDuration(160)
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().mouseReleaseEvent(event)


# ═══════════════════════════════════════════════════════════════════
#  HOME VIEW
# ═══════════════════════════════════════════════════════════════════

class HomeView(QWidget):
    """Landing view with Continue Watching section."""

    history_clicked = Signal(object)
    discover_clicked = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._content = QVBoxLayout(container)
        self._content.setContentsMargins(24, 16, 24, 24)
        self._content.setSpacing(28)

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
        self.seasonal_section = HorizontalCardScroll("Temporada Atual")
        self.seasonal_section.card_clicked.connect(self.discover_clicked.emit)
        self.seasonal_section.set_empty(
            icon_loader(36, "rgba(255,255,255,0.15)"),
            "Carregando...",
            "",
        )
        self._content.addWidget(self.seasonal_section)

        self._content.addStretch()

        self._scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

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

    def update_discover_cover(self, title: str, cover_path: str) -> None:
        self.trending_section.update_card_cover(title, cover_path)
        self.seasonal_section.update_card_cover(title, cover_path)


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


class DownloadsView(QWidget):
    """Offline library — shows downloaded episodes grouped by anime."""

    play_clicked        = Signal(object)
    delete_clicked      = Signal(object)
    open_folder_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Scrollable body ──────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(28, 20, 28, 28)
        body_layout.setSpacing(0)

        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        title_lbl = QLabel("Downloads")
        title_lbl.setObjectName("SectionTitleLarge")
        header_row.addWidget(title_lbl)

        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet(
            "font-size: 12px; color: #6B7280; padding-top: 5px;"
        )
        header_row.addWidget(self._stats_lbl)
        header_row.addStretch()

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
        header_row.addWidget(self._open_btn)

        body_layout.addLayout(header_row)
        body_layout.addSpacing(16)

        # Cards container
        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(10)
        body_layout.addWidget(self._content)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Empty state (injected into content layout)
        self._empty = QWidget()
        self._empty.setStyleSheet("background: transparent;")
        empty_lay = QVBoxLayout(self._empty)
        empty_lay.setContentsMargins(0, 80, 0, 0)
        empty_lay.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        empty_lay.setSpacing(10)
        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setPixmap(icon_folder(48, "#2E3040"))
        empty_lay.addWidget(icon_lbl)
        et = QLabel("Nenhum download encontrado")
        et.setAlignment(Qt.AlignmentFlag.AlignCenter)
        et.setStyleSheet("font-size: 15px; font-weight: 600; color: #3E4255;")
        empty_lay.addWidget(et)
        es = QLabel("Baixe epis\u00f3dios na tela de detalhes\npara assistir offline")
        es.setAlignment(Qt.AlignmentFlag.AlignCenter)
        es.setStyleSheet("font-size: 12px; color: #2E3040; line-height: 1.6;")
        empty_lay.addWidget(es)

        self._content_layout.addWidget(self._empty)

        self._cards: dict[str, _AnimeGroupCard] = {}

    def set_downloads(
        self,
        groups: dict,
        cover_cache: dict | None = None,
    ) -> None:
        for card in self._cards.values():
            self._content_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        # Remove all items except the persistent _empty widget
        while self._content_layout.count() > 0:
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w and w is not self._empty:
                w.setParent(None)
                w.deleteLater()

        if not groups:
            self._stats_lbl.setText("")
            self._content_layout.addWidget(self._empty)
            self._empty.show()
            return

        self._empty.hide()

        total_eps = sum(len(eps) for eps in groups.values())
        total_mb = sum(e.file_size for eps in groups.values() for e in eps) / (1024 * 1024)
        size_disp = f"{total_mb / 1024:.1f} GB" if total_mb >= 1024 else f"{total_mb:.0f} MB"
        count = len(groups)
        self._stats_lbl.setText(
            f"{count}\u00a0anime{'s' if count > 1 else ''}  \u00b7  "
            f"{total_eps}\u00a0ep{'s' if total_eps > 1 else ''}  \u00b7  {size_disp}"
        )

        for anime, entries in sorted(groups.items(), key=lambda x: x[0].lower()):
            cover = (cover_cache or {}).get(anime)
            card = _AnimeGroupCard(anime, entries, cover)
            card.play_clicked.connect(self.play_clicked.emit)
            card.delete_clicked.connect(self.delete_clicked.emit)
            self._cards[anime] = card
            self._content_layout.addWidget(card)

        self._content_layout.addStretch()

    def update_cover(self, anime: str, cover_path: str) -> None:
        if anime in self._cards:
            self._cards[anime].set_cover(cover_path)
