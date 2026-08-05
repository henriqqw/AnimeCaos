from __future__ import annotations

import os
import time
from typing import Any

from PySide6.QtCore import QPoint, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from animecaos.ui.gui.icons import icon_bookmark, icon_play
from animecaos.ui.gui.widgets.spotlight_banner import wrap_and_elide_lines

_PREVIEW_SYNOPSIS_MAX_H = 60
_TITLE_MAX_LINES = 2

# How long to refuse to re-open a hover preview after something moved the
# cards out from under the cursor. Must comfortably outlast
# AnimatedStackedWidget.DURATION_MS (the page cross-fade), during which the
# outgoing page — and the card the cursor is sitting on — is still visible.
_PREVIEW_SUPPRESS_MS = 350


def _elided_title(
    title: str, max_width: int, pixel_size: int, weight: QFont.Weight, max_lines: int = _TITLE_MAX_LINES
) -> tuple[str, int]:
    """Pre-wrap a title to at most `max_lines` lines, eliding the last one
    with "…" instead of overflowing. Using QLabel's own wordWrap+maximumHeight
    for this clips mid-character whenever a long title wraps to exactly
    `max_lines` (the last line's bottom half gets cut off) — computing the
    exact line breaks up front avoids that entirely. Returns (text, height)
    so the label can be sized exactly, with no clipping possible."""
    font = QFont()
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    metrics = QFontMetrics(font)
    lines = wrap_and_elide_lines(title, metrics, max_width, max_lines)
    height = metrics.lineSpacing() * max_lines + 4
    return "\n".join(lines), height


def _title_hue(title: str) -> int:
    """Deterministic hue (0-359) from title string."""
    h = 0
    for ch in title:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % 360


def generate_dynamic_cover(title: str, width: int, height: int, radius: int = 8) -> QPixmap:
    """Create a gradient cover with the anime title when no image is available."""
    hue = _title_hue(title)
    c1 = QColor.fromHsl(hue, 140, 45)
    c2 = QColor.fromHsl((hue + 40) % 360, 120, 30)

    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    clip = QPainterPath()
    clip.addRoundedRect(0, 0, width, height, radius, radius)
    painter.setClipPath(clip)

    grad = QLinearGradient(0, 0, width * 0.3, height)
    grad.setColorAt(0.0, c1)
    grad.setColorAt(1.0, c2)
    painter.fillRect(0, 0, width, height, grad)

    overlay = QLinearGradient(0, 0, 0, height)
    overlay.setColorAt(0.0, QColor(0, 0, 0, 0))
    overlay.setColorAt(1.0, QColor(0, 0, 0, 80))
    painter.fillRect(0, 0, width, height, overlay)

    font = QFont("Segoe UI", 1)
    font.setWeight(QFont.Weight.Bold)
    font.setPixelSize(max(14, width // 7))
    painter.setFont(font)
    painter.setPen(QPen(QColor(255, 255, 255, 230)))

    margin = int(width * 0.1)
    text_rect = pixmap.rect().adjusted(margin, height // 3, -margin, -margin)
    painter.drawText(
        text_rect,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom | Qt.TextFlag.TextWordWrap,
        title.upper(),
    )

    painter.end()
    return pixmap


def _route_wheel_event(card: QWidget, event) -> None:
    """Deliver a wheel event as if it had landed on `card` directly.

    The expanded preview panel is reparented onto the top-level window (see
    AnimeCard._show_preview) so it can escape QScrollArea clipping, which
    means it — not the card underneath — is what the cursor is actually
    over while hovering. A wheel scroll would otherwise go nowhere: Qt only
    auto-bubbles ignored wheel events up the parent chain for genuine
    (spontaneous) hardware events, not ones we construct and dispatch
    ourselves, so a fabricated event sent straight to the card is silently
    swallowed. Walking the card's real ancestry and driving each scroll
    area's bar directly reproduces the natural behaviour instead.
    """
    from animecaos.ui.gui.widgets.card_scroll import HorizontalCardScroll

    widget = card.parentWidget()
    while widget is not None:
        if isinstance(widget, HorizontalCardScroll):
            if widget.eventFilter(card, event):
                return
        elif isinstance(widget, QScrollArea):
            bar = widget.verticalScrollBar()
            if bar.maximum() > 0:
                dy = event.angleDelta().y()
                dx = event.angleDelta().x()
                delta = dy if dy != 0 else dx
                bar.setValue(bar.value() - delta)
                return
        widget = widget.parentWidget()


class _PreviewPanel(QFrame):
    """Hover-expanded card backdrop: the anime's own cover art (not a solid
    color) with a dark gradient scrim over it — transparent near the top so
    the art shows through, solid near the bottom so the text stays legible.

    Reparented to the top-level window while shown (see AnimeCard._show_preview),
    so it's a separate widget layered on top of — not a descendant of — the
    original small card. Once it's shown, the mouse can be over either widget
    depending on exact pixel position; hovered() lets AnimeCard treat both as
    one continuous hover region instead of flickering every time the cursor
    crosses from one widget's hit-region into the other's.
    """

    hovered = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._art: QPixmap | None = None
        self._owner_card: QWidget | None = None

    def enterEvent(self, event) -> None:
        self.hovered.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered.emit(False)
        super().leaveEvent(event)

    def wheelEvent(self, event) -> None:
        if self._owner_card is not None:
            _route_wheel_event(self._owner_card, event)
            return
        super().wheelEvent(event)

    def set_art(self, pixmap: QPixmap | None) -> None:
        self._art = pixmap
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(rect), 10, 10)
        painter.setClipPath(clip)

        if self._art and not self._art.isNull():
            scaled = self._art.scaled(
                rect.width(), rect.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - rect.width()) // 2
            painter.drawPixmap(-x, 0, scaled)
        else:
            painter.fillRect(rect, QColor("#16171F"))

        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0.0, QColor(6, 6, 10, 90))
        gradient.setColorAt(0.3, QColor(6, 6, 10, 170))
        gradient.setColorAt(0.55, QColor(6, 6, 10, 225))
        gradient.setColorAt(1.0, QColor(6, 6, 10, 252))
        painter.fillRect(rect, gradient)

        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.drawRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        painter.end()


class AnimeCard(QFrame):
    """Visual card with cover thumbnail, title, and optional badge."""

    clicked = Signal(object)
    double_clicked = Signal(object)
    remove_clicked = Signal(object)
    list_toggle_clicked = Signal(object)
    preview_requested = Signal(object)

    CARD_WIDTH = 150
    COVER_HEIGHT = 210
    CARD_HEIGHT = 280

    # Tracks whichever card currently has its (reparented, top-level) preview
    # panel shown, so a page/view switch can force it closed even if the
    # mouse never moved off of it (see hide_all_previews).
    _active_preview_card: "AnimeCard | None" = None

    # monotonic() deadline before which no preview may open — see
    # suppress_previews().
    _suppressed_until: float = 0.0

    def __init__(self, data: dict[str, Any], parent: QWidget | None = None, removable: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("AnimeCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.data = data
        self.removable = removable
        self._preview_data_requested = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 8)
        layout.setSpacing(6)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(self.CARD_WIDTH - 12, self.COVER_HEIGHT)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet(
            "background: rgba(255,255,255,0.05); border-radius: 8px;"
        )
        self.cover_label.setText("")

        cover_path = data.get("cover_path")
        if cover_path and os.path.exists(str(cover_path)):
            self._set_cover(str(cover_path))
        else:
            title = data.get("title", "")
            if title:
                self.cover_label.setPixmap(
                    generate_dynamic_cover(title, self.CARD_WIDTH - 12, self.COVER_HEIGHT)
                )
        layout.addWidget(self.cover_label)

        self._remove_btn: QPushButton | None = None
        if removable:
            self._remove_btn = QPushButton("✕", self.cover_label)
            self._remove_btn.setObjectName("CardRemoveButton")
            self._remove_btn.setFixedSize(22, 22)
            self._remove_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._remove_btn.setToolTip("Remover da lista")
            self._remove_btn.setStyleSheet(
                "QPushButton#CardRemoveButton { color: #E6E7EA; background: rgba(20,20,26,0.75);"
                " border: 1px solid rgba(255,255,255,0.15); border-radius: 11px; font-size: 11px; }"
                "QPushButton#CardRemoveButton:hover { color: #FFFFFF; background: rgba(212,66,66,0.85);"
                " border-color: rgba(212,66,66,0.9); }"
            )
            self._remove_btn.move(self.cover_label.width() - 22 - 5, 5)
            self._remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.data))
            self._remove_btn.raise_()

        title_text, title_height = _elided_title(
            data.get("title", ""), self.CARD_WIDTH - 12, pixel_size=12, weight=QFont.Weight.Medium
        )
        self.title_label = QLabel(title_text)
        self.title_label.setWordWrap(False)
        self.title_label.setFixedHeight(title_height)
        self.title_label.setStyleSheet(
            "font-size: 12px; font-weight: 500; color: #E6E7EA;"
        )
        layout.addWidget(self.title_label)

        badge_text = data.get("badge", "")
        if badge_text:
            badge = QLabel(badge_text)
            badge.setObjectName("Caption")
            layout.addWidget(badge)

        layout.addStretch()

        self._build_preview_panel()

    # ── Hover preview (Crunchyroll-style expanded card) ─────────────

    def _build_preview_panel(self) -> None:
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(150)
        self._hide_timer.timeout.connect(self._hide_preview)

        self._preview_panel = _PreviewPanel(self)
        self._preview_panel.setObjectName("CardPreviewPanel")
        self._preview_panel._owner_card = self
        # Once shown, the panel is reparented onto the top-level window (see
        # _show_preview) and never reparented back — its Qt parent stops
        # being this card. Destroying the card would otherwise leave it as
        # an orphaned floating widget, still fully visible.
        self.destroyed.connect(self._preview_panel.deleteLater)
        # Same footprint as the card itself — no taller — so the expanded
        # panel never overlaps whatever sits in the row/grid below it.
        self._preview_panel.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self._preview_panel.set_art(self.cover_label.pixmap())
        self._preview_panel.setVisible(False)
        self._preview_panel.hovered.connect(self._on_preview_hover_changed)

        pv = QVBoxLayout(self._preview_panel)
        pv.setContentsMargins(10, 10, 10, 10)
        pv.setSpacing(4)

        preview_title_text, preview_title_height = _elided_title(
            self.data.get("title", ""), self.CARD_WIDTH - 20, pixel_size=13, weight=QFont.Weight.ExtraBold
        )
        self._preview_title = QLabel(preview_title_text)
        self._preview_title.setWordWrap(False)
        self._preview_title.setFixedHeight(preview_title_height)
        self._preview_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #FFFFFF;")
        pv.addWidget(self._preview_title)

        self._preview_score = QLabel("")
        self._preview_score.setStyleSheet("font-size: 12px; color: #FFC978; font-weight: 700;")
        self._preview_score.setVisible(False)
        pv.addWidget(self._preview_score)

        season_lbl = QLabel("1 Temporada")
        season_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #D7D9DD;")
        pv.addWidget(season_lbl)

        self._preview_episodes = QLabel("")
        self._preview_episodes.setStyleSheet("font-size: 11px; font-weight: 600; color: #D7D9DD;")
        self._preview_episodes.setVisible(False)
        pv.addWidget(self._preview_episodes)

        pv.addSpacing(4)

        self._preview_synopsis = QLabel("")
        self._preview_synopsis.setWordWrap(True)
        self._preview_synopsis.setMaximumHeight(_PREVIEW_SYNOPSIS_MAX_H)
        self._preview_synopsis.setStyleSheet("font-size: 11px; font-weight: 500; color: #E4E5E8;")
        self._preview_synopsis.setAlignment(Qt.AlignmentFlag.AlignTop)
        pv.addWidget(self._preview_synopsis)
        pv.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._preview_play_btn = QPushButton()
        self._preview_play_btn.setFixedSize(28, 28)
        self._preview_play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._preview_play_btn.setToolTip("Ver detalhes")
        self._preview_play_btn.setIcon(QIcon(icon_play(14, "#16171F")))
        self._preview_play_btn.setStyleSheet(
            "QPushButton { background: #F2F3F5; border: none; border-radius: 14px; }"
            "QPushButton:hover { background: #FFFFFF; }"
        )
        self._preview_play_btn.clicked.connect(lambda: self.clicked.emit(self.data))
        btn_row.addWidget(self._preview_play_btn)

        self._preview_list_btn = QPushButton()
        self._preview_list_btn.setFixedSize(28, 28)
        self._preview_list_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._preview_list_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.16);"
            " border-radius: 14px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.16); }"
        )
        self._preview_list_btn.clicked.connect(lambda: self.list_toggle_clicked.emit(self.data))
        btn_row.addWidget(self._preview_list_btn)
        btn_row.addStretch()
        pv.addLayout(btn_row)

        self._refresh_preview_content()

    def _refresh_preview_content(self) -> None:
        score = self.data.get("score")
        if score:
            self._preview_score.setText(f"★ {score / 10:.1f}")
            self._preview_score.setVisible(True)
        else:
            self._preview_score.setVisible(False)

        episodes = self.data.get("episodes")
        if episodes:
            self._preview_episodes.setText(f"{episodes} Episódios")
            self._preview_episodes.setVisible(True)
        else:
            self._preview_episodes.setVisible(False)

        self._preview_synopsis.setText(self.data.get("description") or "Carregando sinopse...")

        in_list = bool(self.data.get("in_list"))
        icon_color = "#D44242" if in_list else "#E6E7EA"
        self._preview_list_btn.setIcon(QIcon(icon_bookmark(14, icon_color, filled=in_list)))
        self._preview_list_btn.setToolTip("Remover da lista" if in_list else "Adicionar à lista")

    def set_preview_data(
        self,
        score: float | None = None,
        episodes: int | None = None,
        description: str | None = None,
    ) -> None:
        if score is not None:
            self.data["score"] = score
        if episodes is not None:
            self.data["episodes"] = episodes
        if description is not None:
            self.data["description"] = description
        self._refresh_preview_content()

    def set_in_list(self, in_list: bool) -> None:
        self.data["in_list"] = in_list
        self._refresh_preview_content()

    def enterEvent(self, event) -> None:
        self._hide_timer.stop()
        self._show_preview()
        # Fetch the synopsis (score/episodes may already be known) lazily,
        # on first hover only — not eagerly for every card on screen. A
        # discover row alone can hold ~50 cards; firing one AniList request
        # per card up front is what tripped AniList's per-IP rate limit and
        # knocked out an unrelated call (login) sharing that same budget.
        if not self._preview_data_requested and "description" not in self.data:
            self._preview_data_requested = True
            self.preview_requested.emit(self.data)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        # Don't hide immediately — the cursor is very likely about to enter
        # the (separately-parented) preview panel it's currently sitting on
        # top of. A short delay, cancelled by either widget's enter, means
        # the panel stays put while the mouse is anywhere over the hovered
        # area instead of flickering every time the cursor crosses from one
        # widget's hit-region into the other's.
        self._hide_timer.start()
        super().leaveEvent(event)

    def _on_preview_hover_changed(self, hovering: bool) -> None:
        if hovering:
            self._hide_timer.stop()
        else:
            self._hide_timer.start()

    def _hide_preview(self) -> None:
        self._preview_panel.setVisible(False)
        if AnimeCard._active_preview_card is self:
            AnimeCard._active_preview_card = None

    def _show_preview(self) -> None:
        if time.monotonic() < AnimeCard._suppressed_until:
            return
        # Reparent to the top-level window so the expanded panel escapes any
        # QScrollArea viewport clipping it up (horizontal discover rows fix
        # their viewport height to a single card, which would otherwise cut
        # the expanded panel off entirely).
        top = self.window()
        if self._preview_panel.parent() is not top:
            self._preview_panel.setParent(top)
        origin = self.mapTo(top, QPoint(0, 0))
        self._preview_panel.move(origin)
        self._preview_panel.setVisible(True)
        self._preview_panel.raise_()
        AnimeCard._active_preview_card = self

    @classmethod
    def suppress_previews(cls) -> None:
        """Close the shown preview *and* refuse to reopen one for a moment.

        Merely hiding is not enough. The panel sits under the cursor, so
        hiding it makes Qt hand the cursor to whatever is beneath — which is
        the very card that owns it — firing enterEvent and reopening the
        panel instantly. That reopened panel then outlives whatever caused
        the hide: it is parented to the top-level window, not to the page,
        so when a page switch finally hides the card the panel keeps
        floating over the new page (the reported "capa vem junto" after
        clicking Play).

        So anything that moves cards out from under the cursor — scrolling,
        switching pages, rebuilding a grid — must suppress rather than hide.
        The cursor stays put, so nothing reopens until the user actually
        moves the mouse again, which is also how Crunchyroll/Netflix behave.
        """
        if cls._active_preview_card is None:
            # Nothing is open, so there is no cursor-under-panel situation to
            # guard against — don't arm a cooldown that would swallow a
            # legitimate hover right afterwards.
            return
        cls._suppressed_until = time.monotonic() + _PREVIEW_SUPPRESS_MS / 1000.0
        cls.hide_all_previews()

    @classmethod
    def hide_all_previews(cls) -> None:
        """Force-close whichever card's preview panel is currently shown.

        The panel lives on top of the whole window, not inside the page that
        spawned it, so switching pages/views doesn't hide it on its own — if
        the mouse happens to sit still over where the card used to be, the
        panel would otherwise keep floating there after navigating away.
        Call this whenever the visible page/view changes.
        """
        active = cls._active_preview_card
        if active is None:
            return
        try:
            active._hide_timer.stop()
            active._hide_preview()
        except RuntimeError:
            # The card (and its C++-backed QTimer) was already torn down —
            # e.g. its window closed without the mouse ever leaving it —
            # so there's nothing left to hide.
            cls._active_preview_card = None

    def _set_cover(self, path: str) -> None:
        w = self.CARD_WIDTH - 12
        h = self.COVER_HEIGHT
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
        clip.addRoundedRect(0, 0, w, h, 8, 8)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()

        self.cover_label.setPixmap(rounded)
        if hasattr(self, "_preview_panel"):
            self._preview_panel.set_art(rounded)

    def set_cover_from_path(self, path: str) -> None:
        # Guard: if the file is unreadable or corrupted, QPixmap will be null.
        # In that case keep whatever is currently shown (the dynamic gradient
        # fallback) rather than wiping the cover label blank.
        from PySide6.QtGui import QPixmap as _QPixmap
        if not path or _QPixmap(path).isNull():
            return
        self._set_cover(path)


    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and hasattr(self, "_press_pos"):
            delta = (event.position() - self._press_pos).manhattanLength()
            if delta < 6 and self.rect().contains(event.position().toPoint()):
                self.clicked.emit(self.data)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.data)
        super().mouseDoubleClickEvent(event)

