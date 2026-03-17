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
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QTextEdit,
    QGridLayout,
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
    icon_monitor,
    icon_search,
    icon_search_x,
)
from .loading_overlay import LoadingOverlay


# ═══════════════════════════════════════════════════════════════════
#  HOME VIEW
# ═══════════════════════════════════════════════════════════════════

class HomeView(QWidget):
    """Landing view with Continue Watching section."""

    history_clicked = Signal(object)

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
