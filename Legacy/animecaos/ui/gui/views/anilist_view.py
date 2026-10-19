from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from animecaos.ui.gui import theme
from animecaos.ui.gui.icons import icon_trash
from animecaos.ui.gui.widgets.animated_button import AnimatedButton
from animecaos.ui.gui.widgets.anime_card import AnimeCard
from animecaos.ui.gui.widgets.empty_state import EmptyState
from animecaos.ui.gui.widgets.tracker_card import TrackerCard


class AccountView(QWidget):
    """Integrations page — progress trackers (AniList, MyAnimeList) plus
    presence integrations (Discord)."""

    connect_clicked = Signal()
    disconnect_clicked = Signal()
    refresh_clicked = Signal()
    mal_connect_clicked = Signal()
    mal_disconnect_clicked = Signal()
    mal_refresh_clicked = Signal()
    discord_toggled = Signal(bool)

    _TRACKER_ROW_WIDTH = 360 * 2 + (theme.SP_XL - 4)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(0)

        # ─── Page header ─────────────────────────────────────────────
        page_title = QLabel("Integrações")
        page_title.setStyleSheet("font-size: 22px; font-weight: 700; color: #F2F3F5;")
        outer.addWidget(page_title)
        outer.addSpacing(theme.SP_XS)

        page_sub = QLabel("Conecte suas contas para sincronizar progresso e atividade automaticamente.")
        page_sub.setStyleSheet("font-size: 13px; color: #6B7280;")
        outer.addWidget(page_sub)
        outer.addSpacing(theme.SP_XL)

        # ─── Section: Rastreamento de progresso ─────────────────────
        outer.addWidget(self._eyebrow("RASTREAMENTO DE PROGRESSO"))
        outer.addSpacing(theme.SP_MD)

        tracker_row = QHBoxLayout()
        tracker_row.setSpacing(theme.SP_XL - 4)

        self._anilist_card = TrackerCard(
            service_name="AniList",
            monogram="AL",
            accent_color="#02A9FF",
            description="Conecte sua conta para sincronizar\nseu progresso automaticamente.",
            benefits=[
                "Tracking automático de episódios assistidos",
                "Stats importados da sua conta AniList",
                "Lista atualizada em tempo real após cada ep",
            ],
            connect_label="Conectar com AniList",
        )
        self._anilist_card.connect_clicked.connect(self.connect_clicked.emit)
        self._anilist_card.disconnect_clicked.connect(self.disconnect_clicked.emit)
        self._anilist_card.refresh_clicked.connect(self.refresh_clicked.emit)
        tracker_row.addWidget(self._anilist_card, 0, Qt.AlignmentFlag.AlignTop)

        self._mal_card = TrackerCard(
            service_name="MyAnimeList",
            monogram="MAL",
            accent_color="#2E51A2",
            description="Conecte sua conta para sincronizar\nseu progresso automaticamente.",
            benefits=[
                "Tracking automático de episódios assistidos",
                "Sincroniza com sua lista MyAnimeList",
                "Progresso atualizado após cada episódio",
            ],
            connect_label="Conectar com MyAnimeList",
        )
        self._mal_card.connect_clicked.connect(self.mal_connect_clicked.emit)
        self._mal_card.disconnect_clicked.connect(self.mal_disconnect_clicked.emit)
        self._mal_card.refresh_clicked.connect(self.mal_refresh_clicked.emit)
        tracker_row.addWidget(self._mal_card, 0, Qt.AlignmentFlag.AlignTop)

        tracker_row.addStretch()
        outer.addLayout(tracker_row)
        outer.addSpacing(theme.SP_LG + 2)

        # How tracking works — one shared explanation for every tracker,
        # since the 30s-watched / stats-refresh / progress-import rules are
        # app behavior, not something that differs per service.
        how_box = QFrame()
        how_box.setObjectName("HowBox")
        how_box.setFixedWidth(self._TRACKER_ROW_WIDTH)
        how_box.setStyleSheet(
            "QFrame#HowBox { background: rgba(255,255,255,0.03);"
            " border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; }"
        )
        hl = QVBoxLayout(how_box)
        hl.setContentsMargins(theme.SP_MD + 2, theme.SP_SM + 2, theme.SP_MD + 2, theme.SP_SM + 2)
        hl.setSpacing(theme.SP_SM - 2)

        how_title = QLabel("Como o tracking funciona")
        how_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #7B8194;"
                                " letter-spacing: 0.8px;")
        hl.addWidget(how_title)
        hl.addSpacing(3)

        for icon, text in [
            ("▶", "Episódio registrado após 30s assistidos"),
            ("↻", "Stats atualizados após fechar o player"),
            ("★", "Progresso importado ao abrir esta tela"),
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

        outer.addWidget(how_box)
        outer.addSpacing(theme.SP_2XL)

        # ─── Section: Atividade ──────────────────────────────────────
        outer.addWidget(self._eyebrow("ATIVIDADE"))
        outer.addSpacing(theme.SP_MD)

        # ── Discord card ──────────────────────────────────────────────
        self._discord_card = QFrame()
        self._discord_card.setObjectName("GlassPanel")
        self._discord_card.setFixedWidth(360)
        dc = QVBoxLayout(self._discord_card)
        dc.setContentsMargins(theme.SP_XL, theme.SP_XL, theme.SP_XL, theme.SP_XL)
        dc.setSpacing(theme.SP_MD + 2)

        # Header row
        hdr = QHBoxLayout()
        hdr.setSpacing(10)
        dc_icon = QLabel("♥")
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
        self._discord_status = QLabel("●  Desconectado")
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
            ("3", "Ative “Exibir atividade atual”"),
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
        pb_ex1 = QLabel("▶  One Piece")
        pb_ex1.setStyleSheet("font-size: 11px; color: #9DA3B4;")
        pbl.addWidget(pb_ex1)
        pb_ex2 = QLabel("    Ep 3 de 24 · há 2 min")
        pb_ex2.setStyleSheet("font-size: 10px; color: #4B5160;")
        pbl.addWidget(pb_ex2)
        dc.addWidget(preview_box)

        dc.addStretch()

        outer.addWidget(self._discord_card)
        outer.addStretch()

        scroll.setWidget(inner)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    def _eyebrow(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #7B8194; letter-spacing: 0.8px;"
        )
        return lbl

    def _on_discord_toggle_clicked(self) -> None:
        enabled = self._discord_toggle.isChecked()
        self._discord_toggle.setText("Ativado" if enabled else "Ativar")
        self.discord_toggled.emit(enabled)

    def set_discord_state(self, enabled: bool, connected: bool) -> None:
        self._discord_toggle.setChecked(enabled)
        self._discord_toggle.setText("Ativado" if enabled else "Ativar")
        if connected:
            self._discord_status.setText("●  Conectado ao Discord")
            self._discord_status.setStyleSheet("font-size: 11px; color: #3DD68C;")
        else:
            self._discord_status.setText("●  Desconectado")
            self._discord_status.setStyleSheet("font-size: 11px; color: #4B5160;")

    # ── AniList tracker ─────────────────────────────────────────────

    def set_authenticated(self, user: dict | None) -> None:
        self._anilist_card.set_authenticated(user)

    def set_avatar_pixmap(self, pixmap: QPixmap) -> None:
        self._anilist_card.set_avatar_pixmap(pixmap)

    def set_connecting(self, connecting: bool) -> None:
        self._anilist_card.set_connecting(connecting)

    # ── MyAnimeList tracker ──────────────────────────────────────────

    def set_mal_authenticated(self, user: dict | None) -> None:
        self._mal_card.set_authenticated(user)

    def set_mal_avatar_pixmap(self, pixmap: QPixmap) -> None:
        self._mal_card.set_avatar_pixmap(pixmap)

    def set_mal_connecting(self, connecting: bool) -> None:
        self._mal_card.set_connecting(connecting)


# ═══════════════════════════════════════════════════════════════════
#  DOWNLOADS VIEW
# ═══════════════════════════════════════════════════════════════════

_COVER_W, _COVER_H = 56, 80   # small portrait — card height driven by content
_MAX_VISIBLE_EPS = 2           # episodes shown before collapse
