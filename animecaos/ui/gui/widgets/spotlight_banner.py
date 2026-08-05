from __future__ import annotations

import os

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Property,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from animecaos.ui.gui.icons import icon_arrow_left, icon_arrow_right

# Minimum number of spotlight cards required for the carousel to auto-advance
# and show navigation chrome (arrows + dots). A single card just displays
# statically, same as before this became a carousel.
AUTO_ADVANCE_MS = 10_000
_FADE_MS = 450

_TITLE_MAX_LINES = 2
_TITLE_PIXEL_SIZE = 38
_TITLE_WEIGHT = QFont.Weight.ExtraBold  # matches the "font-weight: 800" in the title's stylesheet

# Matches _MetaBadge's stylesheet ("padding: 4px 14px; font-size: 12px") so
# width estimates line up with what actually gets painted.
_BADGE_FONT_PX = 12
_BADGE_H_PADDING = 14 * 2
_BADGE_SPACING = 8
_BADGE_ROW_SPACING = 6


def layout_badges_into_rows(
    tags: list[str], metrics: QFontMetrics, max_width: int
) -> list[list[str]]:
    """Greedily wrap badge tags into as many rows as needed so the total
    width of any row never exceeds `max_width`. Most cards only produce 4
    badges (format/duration/score/"HD"), which fit on one row, but a card
    with BOTH a known score AND episode count gets a 5th ("N eps") that can
    overflow — this is what turns that into a second row instead of content
    getting clipped past the hero's visible edge."""
    if not tags:
        return []

    rows: list[list[str]] = []
    current_row: list[str] = []
    current_width = 0.0
    for tag in tags:
        badge_width = metrics.horizontalAdvance(tag) + _BADGE_H_PADDING
        needed = badge_width if not current_row else current_width + _BADGE_SPACING + badge_width
        if current_row and needed > max_width:
            rows.append(current_row)
            current_row = [tag]
            current_width = badge_width
        else:
            current_row.append(tag)
            current_width = needed
    if current_row:
        rows.append(current_row)
    return rows


def wrap_and_elide_lines(
    text: str, metrics: QFontMetrics, max_width: int, max_lines: int
) -> list[str]:
    """Word-wrap `text` to at most `max_lines` lines that each fit within
    `max_width`. If the text doesn't fit, the last line is elided with "…"
    instead of overflowing — a title can be arbitrarily long and this will
    never return more than `max_lines` lines, so callers can size the
    surrounding layout for a fixed, predictable height."""
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    i = 0
    while i < len(words) and len(lines) < max_lines:
        line = words[i]
        i += 1
        if metrics.horizontalAdvance(line) > max_width:
            # Even a single word is wider than the box — elide it on its own
            # rather than let it overflow untouched.
            line = metrics.elidedText(line, Qt.TextElideMode.ElideRight, max_width)
        else:
            while i < len(words):
                candidate = f"{line} {words[i]}"
                if metrics.horizontalAdvance(candidate) <= max_width:
                    line = candidate
                    i += 1
                else:
                    break
        lines.append(line)

    if i < len(words) and lines:
        # Text remains beyond what fit in max_lines — elide the last line
        # (plus whatever leftover words) down to one ellipsized line.
        leftover = lines[-1] + " " + " ".join(words[i:])
        lines[-1] = metrics.elidedText(leftover, Qt.TextElideMode.ElideRight, max_width)

    return lines


class _MetaBadge(QLabel):
    """Dark pill badge for metadata (TV, 24m, HD…)."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(
            "QLabel { background: rgba(255,255,255,0.12); color: #E8E9EC; border-radius: 14px;"
            " padding: 4px 14px; font-size: 12px; font-weight: 500; }"
        )
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class _NavArrow(QPushButton):
    """Circular, semi-transparent prev/next button — full opacity on hover."""

    def __init__(self, direction: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._direction = direction
        icon_fn = icon_arrow_left if direction == "left" else icon_arrow_right
        self.setIcon(QIcon(icon_fn(20, "#FFFFFF")))
        self.setFixedSize(40, 40)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet(
            "QPushButton { background: rgba(10,10,14,0.35); border: 1px solid rgba(255,255,255,0.12);"
            " border-radius: 20px; }"
            " QPushButton:hover { background: rgba(10,10,14,0.65); border-color: rgba(255,255,255,0.28); }"
            " QPushButton:pressed { background: rgba(10,10,14,0.85); }"
        )


class _DotsNav(QWidget):
    """Bottom-left carousel position indicator — click a dot to jump to it."""

    dot_clicked = Signal(int)

    _DOT_D = 7.0
    _GAP = 8.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._count = 0
        self._current = 0
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(int(self._DOT_D) + 2)
        self._recalc_width()

    def set_count(self, count: int, current: int = 0) -> None:
        self._count = max(0, count)
        self._current = current
        self._recalc_width()
        self.update()

    def set_current(self, index: int) -> None:
        self._current = index
        self.update()

    def _recalc_width(self) -> None:
        if self._count <= 0:
            self.setFixedWidth(0)
            return
        width = self._count * self._DOT_D + (self._count - 1) * self._GAP
        self.setFixedWidth(int(width) + 2)

    def _dot_rect(self, index: int) -> QRectF:
        x = index * (self._DOT_D + self._GAP)
        return QRectF(x, 1, self._DOT_D, self._DOT_D)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position() if hasattr(event, "position") else event.localPos()
        for i in range(self._count):
            if self._dot_rect(i).adjusted(-4, -4, 4, 4).contains(pos):
                self.dot_clicked.emit(i)
                return

    def paintEvent(self, event) -> None:
        if self._count <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(self._count):
            rect = self._dot_rect(i)
            if i == self._current:
                p.setBrush(QColor(212, 66, 66, 240))
            else:
                p.setBrush(QColor(255, 255, 255, 90))
            p.drawEllipse(rect)
        p.end()


class SpotlightBanner(QWidget):
    """
    Hero spotlight carousel — full-width, Crunchyroll-style:
      • Up to N anime artworks fill the ENTIRE widget as background, one at
        a time, crossfading between them.
      • Auto-advances every 10s; prev/next arrows and bottom-left dots let
        the user navigate manually (which resets the auto-advance timer).
      • A horizontal gradient overlay darkens the left half so text is readable.
    """

    watch_clicked = Signal(dict)
    anilist_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SpotlightBanner")
        self.setFixedHeight(420)
        self._cards: list[dict] = []
        self._index = 0
        self._raw_pixmap: QPixmap | None = None
        self._bg_pixmap: QPixmap | None = None
        self._prev_bg_pixmap: QPixmap | None = None
        self._meta_badges: list[_MetaBadge] = []
        self._meta_row_widgets: list[QWidget] = []
        self._current_tags: list[str] = []
        self._fade = 1.0

        content_widget = QWidget(self)
        content_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        content_widget.setStyleSheet("background: transparent;")
        self._content_opacity = QGraphicsOpacityEffect(content_widget)
        self._content_opacity.setOpacity(1.0)
        content_widget.setGraphicsEffect(self._content_opacity)

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

        title_font = QFont("Segoe UI")
        title_font.setPixelSize(_TITLE_PIXEL_SIZE)
        title_font.setWeight(_TITLE_WEIGHT)
        self._title_metrics = QFontMetrics(title_font)
        self._current_title = ""

        self._title_lbl = QLabel()
        # Lines are pre-wrapped/elided by _update_title_display() — never
        # more than _TITLE_MAX_LINES, so this gets a fixed height and can
        # never push/overlap the content below it, no matter how long the
        # anime's title is.
        self._title_lbl.setWordWrap(False)
        self._title_lbl.setMaximumWidth(520)
        self._title_lbl.setFixedHeight(int(self._title_metrics.lineSpacing() * _TITLE_MAX_LINES) + 4)
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._title_lbl.setStyleSheet(
            "QLabel { color: #FFFFFF; font-size: 38px; font-weight: 800;"
            " background: transparent; }"
        )
        self._title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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

        # Badge rows are rebuilt per-card (see _layout_meta_badges): a plain
        # single-row QHBoxLayout let a card with 5 badges (format/duration/
        # score/episodes/"HD") overflow past the hero's visible width and
        # get clipped mid-glyph by the crossfade's QGraphicsOpacityEffect.
        self._meta_container = QWidget()
        self._meta_container.setStyleSheet("background: transparent;")
        self._meta_rows_layout = QVBoxLayout(self._meta_container)
        self._meta_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._meta_rows_layout.setSpacing(_BADGE_ROW_SPACING)
        content.addWidget(self._meta_container)
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
        self._watch_btn.clicked.connect(self._on_watch_clicked)

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

        # ── Carousel chrome: prev/next arrows + bottom-left dots ──
        self._prev_arrow = _NavArrow("left", self)
        self._next_arrow = _NavArrow("right", self)
        self._prev_arrow.clicked.connect(self.go_prev)
        self._next_arrow.clicked.connect(self.go_next)
        self._prev_arrow.hide()
        self._next_arrow.hide()

        self._dots = _DotsNav(self)
        self._dots.dot_clicked.connect(self._on_dot_clicked)
        self._dots.hide()

        # ── Auto-advance ──
        self._timer = QTimer(self)
        self._timer.setInterval(AUTO_ADVANCE_MS)
        self._timer.timeout.connect(self.go_next)

        # ── Crossfade animation ──
        self._fade_anim = QPropertyAnimation(self, b"fade", self)
        self._fade_anim.setDuration(_FADE_MS)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.valueChanged.connect(self._on_fade_value_changed)

    # ── Qt property (crossfade progress: 0 = old image, 1 = new image) ──
    def _get_fade(self) -> float:
        return self._fade

    def _set_fade(self, v: float) -> None:
        self._fade = v
        self.update()

    fade = Property(float, _get_fade, _set_fade)

    def _on_fade_value_changed(self, value: float) -> None:
        self._content_opacity.setOpacity(value)

    # ── Layout ──
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        cw = max(380, min(600, w // 2))
        self._content_widget.setGeometry(0, 0, cw, h)
        if self._raw_pixmap:
            self._build_bg()
        self._update_title_display()
        self._layout_meta_badges()

        arrow_y = h // 2 - 20
        self._prev_arrow.move(16, arrow_y)
        self._next_arrow.move(w - 16 - 40, arrow_y)

        self._dots.move(40, h - 28)

        self.update()

    def _update_title_display(self) -> None:
        """Re-wrap/elide the current title for the label's *actual* current
        width — called on every resize so long titles stay correctly
        truncated instead of overflowing when the window is resized."""
        if not self._current_title:
            self._title_lbl.setText("")
            return
        available = max(100, self._content_widget.width() - 40)
        max_width = min(available, self._title_lbl.maximumWidth())
        lines = wrap_and_elide_lines(
            self._current_title, self._title_metrics, max_width, _TITLE_MAX_LINES
        )
        self._title_lbl.setText("\n".join(lines))

    # ── Public API ──
    def set_cards(self, cards: list[dict]) -> None:
        """Replace the carousel's cards and show the first one. Auto-advance
        and navigation chrome only appear once there's more than one card."""
        self._timer.stop()
        self._cards = list(cards)
        self._index = 0

        if not self._cards:
            self.hide()
            self._dots.hide()
            self._prev_arrow.hide()
            self._next_arrow.hide()
            return

        multi = len(self._cards) > 1
        self._prev_arrow.setVisible(multi)
        self._next_arrow.setVisible(multi)
        self._dots.setVisible(multi)
        self._dots.set_count(len(self._cards), current=0)

        self._apply_card(self._cards[0], animate=False)
        self.show()
        if multi:
            self._timer.start()

    def go_next(self) -> None:
        if len(self._cards) < 2:
            return
        self._navigate((self._index + 1) % len(self._cards))

    def go_prev(self) -> None:
        if len(self._cards) < 2:
            return
        self._navigate((self._index - 1) % len(self._cards))

    def current_card(self) -> dict:
        if 0 <= self._index < len(self._cards):
            return self._cards[self._index]
        return {}

    # Legacy single-card API — kept for late-arriving image updates on the
    # card currently on screen (e.g. a banner that finishes downloading
    # after the carousel already started).
    def set_banner(self, path: str) -> None:
        if os.path.exists(path):
            self._load_image(path, animate=False)

    def set_cover(self, path: str) -> None:
        if os.path.exists(path) and self._raw_pixmap is None:
            self._load_image(path, animate=False)

    # ── Internal navigation ──
    def _on_dot_clicked(self, index: int) -> None:
        self._navigate(index)

    def _navigate(self, new_index: int) -> None:
        if not self._cards or new_index == self._index or not (0 <= new_index < len(self._cards)):
            return
        self._index = new_index
        self._apply_card(self._cards[new_index], animate=True)
        self._dots.set_current(new_index)
        if len(self._cards) > 1:
            self._timer.start()  # manual nav resets the auto-advance countdown

    def _on_watch_clicked(self) -> None:
        self.watch_clicked.emit(self.current_card())

    def _apply_card(self, card: dict, animate: bool) -> None:
        rank = card.get("_rank", self._index + 1)
        self._rank_badge.setText(f"★  #{rank} DESTAQUE DA TEMPORADA")
        self._current_title = card.get("title", "")
        self._update_title_display()
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
            self._load_image(str(img_path), animate=animate)
        elif animate:
            self._run_fade()

    def _on_list_btn_clicked(self) -> None:
        anilist_id = self.current_card().get("anilist_id")
        if anilist_id:
            self.anilist_clicked.emit(int(anilist_id))

    def _rebuild_meta_badges(self, card: dict) -> None:
        self._current_tags = self._compute_meta_tags(card)
        self._layout_meta_badges()

    @staticmethod
    def _compute_meta_tags(card: dict) -> list[str]:
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
        return tags

    def _layout_meta_badges(self) -> None:
        for row_widget in self._meta_row_widgets:
            row_widget.setParent(None)
            row_widget.deleteLater()
        self._meta_row_widgets.clear()
        self._meta_badges.clear()

        if not self._current_tags:
            return

        font = QFont("Segoe UI")
        font.setPixelSize(_BADGE_FONT_PX)
        metrics = QFontMetrics(font)
        max_width = max(100, self._content_widget.width() - 40)
        rows = layout_badges_into_rows(self._current_tags, metrics, max_width)

        for row_tags in rows:
            row_widget = QWidget()
            row_widget.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(_BADGE_SPACING)
            for tag in row_tags:
                badge = _MetaBadge(tag)
                row_layout.addWidget(badge)
                self._meta_badges.append(badge)
            row_layout.addStretch()
            self._meta_rows_layout.addWidget(row_widget)
            self._meta_row_widgets.append(row_widget)

    def _load_image(self, path: str, animate: bool) -> None:
        raw = QPixmap(path)
        if raw.isNull():
            return
        self._raw_pixmap = raw
        self._build_bg()
        if animate:
            self._run_fade()
        else:
            self.update()

    def _run_fade(self) -> None:
        # _build_bg() already stashed the outgoing image in _prev_bg_pixmap —
        # just animate the crossfade progress from 0 (old) to 1 (new).
        self._fade_anim.stop()
        self._fade = 0.0
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def _build_bg(self) -> None:
        if not self._raw_pixmap:
            return
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        # Keep the outgoing image around so _run_fade() can crossfade from it.
        self._prev_bg_pixmap = self._bg_pixmap
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

        if self._prev_bg_pixmap and self._fade < 1.0:
            painter.drawPixmap(0, 0, self._prev_bg_pixmap)
        if self._bg_pixmap:
            painter.setOpacity(self._fade)
            painter.drawPixmap(0, 0, self._bg_pixmap)
            painter.setOpacity(1.0)

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
