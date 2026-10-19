"""
Reusable "progress tracker" integration card — AniList and MyAnimeList are
the same concept (connect an account, see its stats, watch progress sync
automatically) so this widget carries the shared anatomy/behavior for both,
rather than duplicating ~230 lines of near-identical layout code per service.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from animecaos.ui.gui import theme
from animecaos.ui.gui.widgets.animated_button import AnimatedButton

_AVATAR_SIZE = 56
_COOLDOWN_SECS = 300  # 5 minutes

_SUBTLE_BTN_QSS = (
    "QPushButton { color: #6B7280; background: transparent;"
    " border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; font-size: 12px; }"
    "QPushButton:hover { color: #E57373;"
    " border-color: rgba(229,115,115,0.35); background: rgba(229,115,115,0.06); }"
    "QPushButton:disabled { color: #3B3E4A;"
    " border-color: rgba(255,255,255,0.04); }"
)


class TrackerCard(QFrame):
    """One GlassPanel card for a single progress-tracking integration
    (AniList, MyAnimeList, ...). Not-connected state shows a pitch + connect
    button; connected state shows the account's avatar, name, and stats."""

    connect_clicked = Signal()
    disconnect_clicked = Signal()
    refresh_clicked = Signal()

    def __init__(
        self,
        service_name: str,
        monogram: str,
        accent_color: str,
        description: str,
        benefits: list[str],
        connect_label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._accent_color = accent_color
        self._service_name = service_name

        self.setObjectName("GlassPanel")
        self.setFixedWidth(360)
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(theme.SP_XL, theme.SP_XL, theme.SP_XL, theme.SP_XL)
        card_layout.setSpacing(0)

        # ─── Not connected ───────────────────────────────────────────
        self._not_connected = QWidget()
        nc = QVBoxLayout(self._not_connected)
        nc.setContentsMargins(0, 0, 0, 0)
        nc.setSpacing(0)
        nc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge_lbl = QLabel()
        badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_lbl.setPixmap(self._make_badge_pixmap(monogram))
        badge_lbl.setToolTip(f"{service_name} — rastreamento de anime")
        nc.addWidget(badge_lbl, 0, Qt.AlignmentFlag.AlignHCenter)
        nc.addSpacing(theme.SP_LG + 2)

        nc_title = QLabel(service_name)
        nc_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nc_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #F2F3F5;")
        nc.addWidget(nc_title)
        nc.addSpacing(theme.SP_XS + 2)

        nc_sub = QLabel(description)
        nc_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nc_sub.setWordWrap(True)
        nc_sub.setStyleSheet("font-size: 12px; color: #6B7280;")
        nc.addWidget(nc_sub)
        nc.addSpacing(theme.SP_LG + 2)

        benefits_box = QFrame()
        benefits_box.setObjectName("BenefitsBox")
        benefits_box.setStyleSheet(
            "QFrame#BenefitsBox { background: rgba(255,255,255,0.03);"
            " border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; }"
        )
        bl = QVBoxLayout(benefits_box)
        bl.setContentsMargins(theme.SP_MD + 2, theme.SP_SM + 2, theme.SP_MD + 2, theme.SP_SM + 2)
        bl.setSpacing(theme.SP_SM - 2)
        for text in benefits:
            row = QHBoxLayout()
            row.setSpacing(theme.SP_SM)
            dot = QLabel("✓")
            dot.setFixedWidth(14)
            dot.setStyleSheet("color: #3DD68C; font-size: 11px; font-weight: 700;")
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 11px; color: #6B7280;")
            row.addWidget(dot)
            row.addWidget(lbl, 1)
            bl.addLayout(row)
        nc.addWidget(benefits_box)
        nc.addSpacing(theme.SP_LG + 2)

        self._connect_btn = AnimatedButton(connect_label)
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

        profile_row = QHBoxLayout()
        profile_row.setSpacing(theme.SP_MD + 2)
        profile_row.setContentsMargins(0, 0, 0, 0)

        self._avatar_label = QLabel()
        self._avatar_label.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar_label.setPixmap(self._make_badge_pixmap(monogram))
        self._avatar_label.setToolTip(f"{service_name} — rastreamento de anime")
        profile_row.addWidget(self._avatar_label, 0, Qt.AlignmentFlag.AlignVCenter)

        name_col = QVBoxLayout()
        name_col.setSpacing(3)
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._username_label = QLabel("")
        self._username_label.setStyleSheet("font-size: 17px; font-weight: 700; color: #F2F3F5;")
        name_col.addWidget(self._username_label)

        ok_badge = QLabel(f"●  Conectado ao {service_name}")
        ok_badge.setStyleSheet("color: #3DD68C; font-size: 11px; font-weight: 600; letter-spacing: 0.4px;")
        name_col.addWidget(ok_badge)

        profile_row.addLayout(name_col, 1)
        co.addLayout(profile_row)
        co.addSpacing(theme.SP_XL - 4)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(255,255,255,0.07);")
        co.addWidget(div)
        co.addSpacing(theme.SP_LG + 2)

        stats_frame = QFrame()
        stats_frame.setObjectName("StatsFrame")
        stats_frame.setStyleSheet("QFrame#StatsFrame { background: rgba(255,255,255,0.04); border-radius: 10px; }")
        stats_row = QHBoxLayout(stats_frame)
        stats_row.setContentsMargins(0, theme.SP_LG, 0, theme.SP_LG)
        stats_row.setSpacing(0)

        self._stat_labels: dict[str, QLabel] = {}
        for i, (key, label_text) in enumerate([
            ("animes", "ANIMES"),
            ("episodes", "EPISÓDIOS"),
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

            val = QLabel("—")
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
        co.addSpacing(theme.SP_SM - 2)

        # #5B5F6B on #0B0C0F clears WCAG AA for small text; the original
        # #3B3E4A did not — kept "quietest tier" but legible.
        src_caption = QLabel(f"⬤  Dados do {service_name} · Sincronizado automaticamente")
        src_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        src_caption.setStyleSheet("font-size: 10px; color: #5B5F6B; letter-spacing: 0.3px;")
        co.addWidget(src_caption, 0, Qt.AlignmentFlag.AlignHCenter)
        co.addSpacing(theme.SP_LG)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(theme.SP_SM)

        self._refresh_btn = AnimatedButton("↻  Atualizar")
        self._refresh_btn.setFixedHeight(36)
        self._refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._refresh_btn.setStyleSheet(_SUBTLE_BTN_QSS)
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        btn_row.addWidget(self._refresh_btn)

        self._disconnect_btn = AnimatedButton("Desconectar")
        self._disconnect_btn.setFixedHeight(36)
        self._disconnect_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._disconnect_btn.setStyleSheet(_SUBTLE_BTN_QSS)
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

        self._connect_label = connect_label
        self._monogram = monogram

    # ── Badge rendering ─────────────────────────────────────────────

    def _make_badge_pixmap(self, monogram: str) -> QPixmap:
        pm = QPixmap(_AVATAR_SIZE, _AVATAR_SIZE)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill_color = QColor(self._accent_color)
        fill_color.setAlpha(38)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill_color)
        painter.drawEllipse(0, 0, _AVATAR_SIZE, _AVATAR_SIZE)
        painter.setPen(QPen(QColor(self._accent_color), 1.5))
        painter.drawEllipse(1, 1, _AVATAR_SIZE - 2, _AVATAR_SIZE - 2)
        font = painter.font()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, monogram)
        painter.end()
        return pm

    # ── Public API ───────────────────────────────────────────────────

    def _on_refresh_clicked(self) -> None:
        self.refresh_clicked.emit()
        self._cooldown_remaining = _COOLDOWN_SECS
        self._refresh_btn.setEnabled(False)
        self._cooldown_ticker.start()
        self._update_cooldown_label()

    def _tick_cooldown(self) -> None:
        self._cooldown_remaining -= 1
        if self._cooldown_remaining <= 0:
            self._cooldown_ticker.stop()
            self._refresh_btn.setEnabled(True)
            self._refresh_btn.setText("↻  Atualizar")
        else:
            self._update_cooldown_label()

    def _update_cooldown_label(self) -> None:
        m, s = divmod(self._cooldown_remaining, 60)
        self._refresh_btn.setText(f"↻  Aguarde {m}:{s:02d}")

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
            self._avatar_label.setPixmap(self._make_badge_pixmap(self._monogram))
            self._connect_btn.setEnabled(True)
            self._connect_btn.setText(self._connect_label)

    def set_avatar_pixmap(self, pixmap: QPixmap) -> None:
        w, h = _AVATAR_SIZE, _AVATAR_SIZE
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

    def set_connecting(self, connecting: bool) -> None:
        self._connect_btn.setEnabled(not connecting)
        self._connect_btn.setText("Aguardando..." if connecting else self._connect_label)
