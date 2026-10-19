from __future__ import annotations

import math
import os
import sys
from typing import Any

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QConicalGradient, QCursor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from animecaos.ui.gui.icons import icon_instagram, icon_search, icon_search_x, icon_x_logo
from animecaos.ui.gui.widgets.anime_card import AnimeCard
from animecaos.ui.gui.widgets.empty_state import EmptyState

INSTAGRAM_URL = "https://www.instagram.com/getanimecaos/"
X_URL = "https://x.com/getanimecaos"


class _FlowLayout(QVBoxLayout):
    """Grid-based flow layout for cards."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 14) -> None:
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
        # Destroy the old flow_widget+grid entirely so that QGridLayout does not
        # retain residual row/column structure (empty rows would keep taking up
        # vertical space and shift subsequent cards to wrong positions).
        if self._flow_widget is not None:
            super().removeWidget(self._flow_widget)
            self._flow_widget.setParent(None)
            self._flow_widget.deleteLater()

        # Create a completely fresh container + grid.
        self._flow_widget = QWidget()
        self._flow_widget.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._flow_widget)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(self._spacing)
        super().addWidget(self._flow_widget)

        self._widgets.clear()
        self._row = 0
        self._col = 0


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
    list_toggle_requested = Signal(object)
    preview_requested = Signal(object)

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
        # Scrolling the page moves cards out from under any shown hover-preview
        # panel (which is reparented onto the top-level window and doesn't
        # move with them), so it must close rather than float in place.
        self._scroll.verticalScrollBar().valueChanged.connect(lambda _: AnimeCard.suppress_previews())

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
            "Não encontramos esse anime nas nossas fontes.\n"
            "Solicite o anime desejado nas nossas redes sociais:",
            social_links=[
                (icon_instagram(16, "#E6E7EA"), "Instagram", INSTAGRAM_URL),
                (icon_x_logo(16, "#E6E7EA"), "X", X_URL),
            ],
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

    def stop_loading(self) -> None:
        """Stop the skeleton animation without touching results — used when a
        search fails, so the loading state doesn't spin forever. The error
        itself is surfaced elsewhere (status bar / error dialog)."""
        self._skeleton.stop()
        self._grid_container.setVisible(True)

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
            card.list_toggle_clicked.connect(self.list_toggle_requested.emit)
            card.preview_requested.connect(self.preview_requested.emit)
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

    def update_card_preview(
        self, title: str, score: float | None = None, episodes: int | None = None,
        description: str | None = None,
    ) -> None:
        for card in self._cards:
            if card.data.get("title") == title:
                card.set_preview_data(score=score, episodes=episodes, description=description)
                break

    def update_card_in_list(self, title: str, in_list: bool) -> None:
        for card in self._cards:
            if card.data.get("title") == title:
                card.set_in_list(in_list)
                break

    def _clear_cards(self) -> None:
        AnimeCard.suppress_previews()
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        # Reset grid counters AND recreate the internal QGridLayout so there are
        # no residual empty rows/columns that would offset the next search results.
        self._grid_layout.clear_all()


