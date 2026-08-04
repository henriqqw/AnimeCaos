from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, QTimer, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from animecaos.ui.gui.icons import icon_arrow_left, icon_arrow_right
from .anime_card import AnimeCard
from .empty_state import EmptyState

# ── Drag / kinetic constants ─────────────────────────────────────────
_DRAG_THRESHOLD = 6       # px of horizontal movement before drag is recognised
_KINETIC_FRICTION = 0.84  # velocity multiplier per tick (lower = stops sooner)
_KINETIC_INTERVAL = 16    # ms per tick (~60 fps)


class HorizontalCardScroll(QWidget):
    """Horizontal scrollable row of AnimeCard widgets with section header.

    Supports:
    - Mouse-wheel horizontal scroll
    - Click-and-drag scroll (like Netflix / streaming apps)
    - Kinetic (momentum) scroll after drag release
    - Left/Right navigation arrow buttons
    """

    card_clicked = Signal(object)
    card_double_clicked = Signal(object)

    def __init__(
        self,
        title: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        # ── Header bar with Section Title + Navigation Arrows ──
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        if title:
            lbl = QLabel(title)
            lbl.setObjectName("SectionTitle")
            header.addWidget(lbl)

        header.addStretch()

        # Left / Right Arrow Buttons
        self._btn_left = QPushButton()
        self._btn_left.setFixedSize(28, 28)
        self._btn_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_left.setIcon(QIcon(icon_arrow_left(14, "#A7ACB5")))
        self._btn_left.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.2); }"
            "QPushButton:pressed { background: rgba(255,255,255,0.18); }"
        )
        self._btn_left.clicked.connect(self._scroll_left)

        self._btn_right = QPushButton()
        self._btn_right.setFixedSize(28, 28)
        self._btn_right.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_right.setIcon(QIcon(icon_arrow_right(14, "#A7ACB5")))
        self._btn_right.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.2); }"
            "QPushButton:pressed { background: rgba(255,255,255,0.18); }"
        )
        self._btn_right.clicked.connect(self._scroll_right)

        header.addWidget(self._btn_left)
        header.addWidget(self._btn_right)
        outer.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(AnimeCard.CARD_HEIGHT + 14)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._row_layout = QHBoxLayout(self._container)
        self._row_layout.setContentsMargins(0, 0, 0, 0)
        self._row_layout.setSpacing(12)
        self._row_layout.addStretch()

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll)

        self._scroll.viewport().installEventFilter(self)
        self._container.installEventFilter(self)

        self._cards: list[AnimeCard] = []
        self._empty_state: EmptyState | None = None

        self._anim: QPropertyAnimation | None = None

        # ── Drag-scroll state ────────────────────────────────────────
        self._drag_active: bool = False
        self._drag_start_gx: float = 0.0
        self._drag_last_gx: float = 0.0
        self._drag_scroll_start: int = 0
        self._velocity: float = 0.0

        # Kinetic (momentum) animation after release
        self._kinetic_timer = QTimer(self)
        self._kinetic_timer.setInterval(_KINETIC_INTERVAL)
        self._kinetic_timer.timeout.connect(self._kinetic_step)

    # ── Event filter (handles wheel + drag on viewport, container AND cards) ──

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        t = event.type()

        # ── Wheel scroll ──────────────────────────────────────────────
        if t == QEvent.Type.Wheel:
            dx = event.angleDelta().x()
            dy = event.angleDelta().y()
            if abs(dy) >= abs(dx):
                return False
            delta = dx if dx != 0 else -dy
            bar = self._scroll.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
            return True

        # ── Mouse press: start tracking ───────────────────────────────
        if t == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._kinetic_timer.stop()
                self._velocity = 0.0
                self._drag_active = False
                gx = event.globalPosition().x()
                self._drag_start_gx = gx
                self._drag_last_gx = gx
                self._drag_scroll_start = self._scroll.horizontalScrollBar().value()
            return False

        # ── Mouse move: scroll if dragging ────────────────────────────
        if t == QEvent.Type.MouseMove:
            if event.buttons() & Qt.MouseButton.LeftButton:
                gx = event.globalPosition().x()
                dx = gx - self._drag_start_gx
                self._velocity = self._drag_last_gx - gx
                self._drag_last_gx = gx

                if not self._drag_active and abs(dx) > _DRAG_THRESHOLD:
                    self._drag_active = True

                if self._drag_active:
                    bar = self._scroll.horizontalScrollBar()
                    bar.setValue(self._drag_scroll_start - int(dx))
                    self._scroll.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
                    if isinstance(obj, AnimeCard):
                        obj.setCursor(Qt.CursorShape.ClosedHandCursor)
                    return True
            return False

        # ── Mouse release: launch kinetic or allow click ──────────────
        if t == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                self._scroll.viewport().unsetCursor()
                if isinstance(obj, AnimeCard):
                    obj.setCursor(Qt.CursorShape.PointingHandCursor)
                was_dragging = self._drag_active
                self._drag_active = False
                if was_dragging:
                    if abs(self._velocity) > 0.5:
                        self._kinetic_timer.start()
                    return True
            return False

        return super().eventFilter(obj, event)

    def _kinetic_step(self) -> None:
        """Apply decaying momentum after drag release."""
        self._velocity *= _KINETIC_FRICTION
        bar = self._scroll.horizontalScrollBar()
        bar.setValue(bar.value() + int(self._velocity))
        if abs(self._velocity) < 0.5:
            self._kinetic_timer.stop()

    def _scroll_left(self) -> None:
        bar = self._scroll.horizontalScrollBar()
        step = int(self._scroll.viewport().width() * 0.75)
        self._animate_scroll(bar.value() - step)

    def _scroll_right(self) -> None:
        bar = self._scroll.horizontalScrollBar()
        step = int(self._scroll.viewport().width() * 0.75)
        self._animate_scroll(bar.value() + step)

    def _animate_scroll(self, target_value: int) -> None:
        self._kinetic_timer.stop()
        bar = self._scroll.horizontalScrollBar()
        target = max(bar.minimum(), min(bar.maximum(), target_value))
        self._anim = QPropertyAnimation(bar, b"value")
        self._anim.setDuration(280)
        self._anim.setStartValue(bar.value())
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()


    def set_cards(self, items: list[dict[str, Any]]) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        if self._empty_state:
            self._empty_state.setParent(None)
            self._empty_state.deleteLater()
            self._empty_state = None

        while self._row_layout.count():
            self._row_layout.takeAt(0)

        if not items:
            return

        for data in items:
            card = AnimeCard(data)
            card.installEventFilter(self)
            card.clicked.connect(self.card_clicked.emit)
            card.double_clicked.connect(self.card_double_clicked.emit)
            self._cards.append(card)
            self._row_layout.addWidget(card)

        self._row_layout.addStretch()

    def set_empty(self, icon_pixmap: QPixmap | None, title: str, subtitle: str) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        while self._row_layout.count():
            self._row_layout.takeAt(0)

        if self._empty_state:
            self._empty_state.setParent(None)
            self._empty_state.deleteLater()

        self._empty_state = EmptyState(icon_pixmap, title, subtitle)
        self._empty_state.setFixedHeight(AnimeCard.CARD_HEIGHT)
        self._row_layout.addStretch()
        self._row_layout.addWidget(self._empty_state)
        self._row_layout.addStretch()

    def get_card(self, index: int) -> AnimeCard | None:
        if 0 <= index < len(self._cards):
            return self._cards[index]
        return None

    def card_count(self) -> int:
        return len(self._cards)

    def trim_to(self, max_cards: int) -> None:
        while len(self._cards) > max_cards:
            card = self._cards.pop()
            self._row_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()

    def remove_card(self, title: str) -> None:
        for card in list(self._cards):
            if card.data.get("title") == title:
                self._row_layout.removeWidget(card)
                card.setParent(None)
                card.deleteLater()
                self._cards.remove(card)
                break

    def update_card_cover(self, title: str, cover_path: str) -> None:
        for card in self._cards:
            if card.data.get("title") == title:
                card.set_cover_from_path(cover_path)
                break
