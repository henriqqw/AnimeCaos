from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from animecaos.ui.gui.icons import icon_trash, icon_user
from animecaos.ui.gui.widgets.animated_button import AnimatedButton
from animecaos.ui.gui.widgets.anime_card import AnimeCard
from animecaos.ui.gui.widgets.empty_state import EmptyState


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


