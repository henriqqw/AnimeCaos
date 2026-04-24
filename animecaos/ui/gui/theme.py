from __future__ import annotations


# ── Design Tokens ────────────────────────────────────────────────
# Centralized so every widget draws from the same palette.

ACCENT = "#D44242"
ACCENT_HOVER = "#E05252"
ACCENT_PRESSED = "#B63838"
ACCENT_DIM = "rgba(212, 66, 66, 0.22)"
ACCENT_DIM_HOVER = "rgba(224, 82, 82, 0.30)"
ACCENT_DIM_PRESSED = "rgba(182, 56, 56, 0.34)"
ACCENT_BORDER = "rgba(212, 66, 66, 0.40)"

BG_DARK = "#0B0C0F"
BG_MID = "#101218"
BG_CARD = "rgba(255, 255, 255, 0.06)"
BG_CARD_HOVER = "rgba(255, 255, 255, 0.10)"
BG_CARD_ACTIVE = "rgba(255, 255, 255, 0.04)"
BG_INPUT = "rgba(255, 255, 255, 0.07)"
BG_GLASS = "rgba(255, 255, 255, 0.08)"
BG_OVERLAY = "rgba(11, 12, 15, 200)"

BORDER_SUBTLE = "rgba(255, 255, 255, 0.12)"
BORDER_DEFAULT = "rgba(255, 255, 255, 0.16)"
BORDER_STRONG = "rgba(255, 255, 255, 0.20)"
BORDER_FOCUS = ACCENT

TEXT_PRIMARY = "#F2F3F5"
TEXT_SECONDARY = "#E6E7EA"
TEXT_MUTED = "#A7ACB5"
TEXT_DISABLED = "#7F848D"

FONT_FAMILY = '"Segoe UI", "Helvetica Neue", sans-serif'

# Spacing scale (4px grid)
SP_XS = 4
SP_SM = 8
SP_MD = 12
SP_LG = 16
SP_XL = 24
SP_2XL = 32


def build_stylesheet() -> str:
    return f"""
    /* ── Base ─────────────────────────────────────────────── */
    QWidget {{
        background: transparent;
        color: {TEXT_PRIMARY};
        font-family: {FONT_FAMILY};
        font-size: 13px;
    }}

    QWidget#RootContainer {{
        background: qlineargradient(
            x1: 0, y1: 0, x2: 0, y2: 1,
            stop: 0 {BG_MID},
            stop: 1 {BG_DARK}
        );
    }}

    /* ── Panels ───────────────────────────────────────────── */
    QFrame#GlassPanel {{
        background-color: {BG_GLASS};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 12px;
    }}

    QFrame#GlassPanelFlat {{
        background-color: {BG_GLASS};
        border: none;
        border-radius: 12px;
    }}

    /* ── Labels ───────────────────────────────────────────── */
    QLabel {{
        background: transparent;
    }}

    QLabel#AppTitle {{
        font-size: 22px;
        font-weight: 600;
        color: {TEXT_PRIMARY};
    }}

    QLabel#ViewTitle {{
        font-size: 28px;
        font-weight: 700;
        color: {TEXT_PRIMARY};
    }}

    QLabel#SectionTitle {{
        font-size: 16px;
        font-weight: 600;
        color: {TEXT_SECONDARY};
    }}

    QLabel#SectionTitleLarge {{
        font-size: 20px;
        font-weight: 600;
        color: {TEXT_SECONDARY};
    }}

    QLabel#MutedText, QTextEdit#MutedText {{
        color: {TEXT_MUTED};
        font-size: 12px;
    }}

    QTextEdit#MutedText {{
        background: transparent;
        border: none;
    }}

    QLabel#Caption {{
        color: {TEXT_MUTED};
        font-size: 11px;
    }}

    QLabel#Badge {{
        font-size: 11px;
        font-weight: 600;
        color: {ACCENT};
        background-color: {ACCENT_DIM};
        border: 1px solid {ACCENT_BORDER};
        border-radius: 4px;
        padding: 2px 8px;
    }}

    QLabel#BadgeWatched {{
        font-size: 11px;
        font-weight: 600;
        color: #81C784;
        background-color: rgba(76, 175, 80, 0.25);
        border-radius: 4px;
        padding: 2px 8px;
    }}

    QLabel#Breadcrumb {{
        color: {TEXT_MUTED};
        font-size: 13px;
    }}

    QLabel#EmptyStateTitle {{
        font-size: 16px;
        font-weight: 600;
        color: {TEXT_SECONDARY};
    }}

    QLabel#EmptyStateSubtitle {{
        font-size: 13px;
        color: {TEXT_MUTED};
    }}

    /* ── Inputs ───────────────────────────────────────────── */
    QLineEdit, QPlainTextEdit, QListWidget {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: 10px;
        padding: 8px;
        selection-background-color: rgba(212, 66, 66, 0.65);
        selection-color: {TEXT_PRIMARY};
    }}

    QLineEdit:focus, QPlainTextEdit:focus, QListWidget:focus {{
        border: 1px solid {ACCENT};
    }}

    QListWidget::item {{
        padding: 7px 8px;
        border-radius: 6px;
    }}

    QListWidget::item:selected {{
        background-color: rgba(212, 66, 66, 0.55);
    }}

    QListWidget::item:hover:!selected {{
        background-color: rgba(255, 255, 255, 0.06);
    }}

    /* ── Buttons ──────────────────────────────────────────── */
    QPushButton {{
        background-color: rgba(255, 255, 255, 0.10);
        border: 1px solid {BORDER_STRONG};
        border-radius: 10px;
        padding: 8px 14px;
        font-weight: 500;
    }}

    QPushButton:hover {{
        background-color: rgba(255, 255, 255, 0.14);
    }}

    QPushButton:pressed {{
        background-color: rgba(255, 255, 255, 0.08);
    }}

    QPushButton:disabled {{
        color: {TEXT_DISABLED};
        background-color: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.10);
    }}

    QPushButton#PrimaryButton {{
        border: 1px solid {ACCENT};
        background-color: {ACCENT_DIM};
        font-weight: 600;
    }}

    QPushButton#PrimaryButton:hover {{
        background-color: {ACCENT_DIM_HOVER};
        border: 1px solid {ACCENT_HOVER};
    }}

    QPushButton#PrimaryButton:pressed {{
        background-color: {ACCENT_DIM_PRESSED};
        border: 1px solid {ACCENT_PRESSED};
    }}

    QPushButton#IconButton {{
        background: transparent;
        border: none;
        border-radius: 8px;
        padding: 6px;
        min-width: 32px;
        min-height: 32px;
    }}

    QPushButton#IconButton:hover {{
        background-color: rgba(255, 255, 255, 0.10);
    }}

    QPushButton#IconButton:pressed {{
        background-color: rgba(255, 255, 255, 0.06);
    }}

    /* Sidebar navigation buttons — circular highlight */
    QPushButton#NavButton {{
        background: transparent;
        border: none;
        border-radius: 20px;
        padding: 0px;
        min-width: 40px;
        min-height: 40px;
        max-width: 40px;
        max-height: 40px;
    }}

    QPushButton#NavButton:hover {{
        background-color: rgba(255, 255, 255, 0.10);
    }}

    QPushButton#NavButton:checked {{
        background-color: rgba(255, 255, 255, 0.16);
        border: none;
    }}

    QPushButton#NavButton:checked:hover {{
        background-color: rgba(255, 255, 255, 0.22);
    }}

    /* ── Sidebar floating pill ───────────────────────────── */
    QFrame#Sidebar {{
        background-color: rgba(20, 22, 28, 0.92);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 18px;
    }}

    /* ── Mini Player ─────────────────────────────────────── */
    QFrame#MiniPlayer {{
        background-color: rgba(16, 18, 24, 0.95);
        border-top: 1px solid {BORDER_SUBTLE};
        border-radius: 0px;
    }}

    /* ── Anime Card ───────────────────────────────────────── */
    QFrame#AnimeCard {{
        background-color: {BG_CARD};
        border: 1px solid transparent;
        border-radius: 10px;
    }}

    QFrame#AnimeCard:hover {{
        background-color: {BG_CARD_HOVER};
        border: 1px solid {ACCENT_BORDER};
    }}

    /* ── Episode Row ──────────────────────────────────────── */
    QFrame#EpisodeRow {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 4px;
    }}

    QFrame#EpisodeRow:hover {{
        background-color: rgba(255, 255, 255, 0.05);
    }}

    /* ── Scroll Areas ─────────────────────────────────────── */
    QScrollArea {{
        background: transparent;
        border: none;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: rgba(255, 255, 255, 0.15);
        border-radius: 3px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: rgba(255, 255, 255, 0.25);
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
        margin: 0px;
    }}

    QScrollBar::handle:horizontal {{
        background: rgba(255, 255, 255, 0.15);
        border-radius: 3px;
        min-width: 30px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background: rgba(255, 255, 255, 0.25);
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    /* ── Progress Bar ─────────────────────────────────────── */
    QProgressBar {{
        border: 1px solid {BORDER_DEFAULT};
        border-radius: 8px;
        text-align: center;
        background-color: rgba(255, 255, 255, 0.06);
    }}

    QProgressBar::chunk {{
        background-color: {ACCENT};
        border-radius: 7px;
    }}

    /* ── Checkbox ─────────────────────────────────────────── */
    QCheckBox {{
        spacing: 6px;
        font-size: 13px;
    }}

    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid {BORDER_STRONG};
        background-color: rgba(255, 255, 255, 0.06);
    }}

    QCheckBox::indicator:checked {{
        background-color: {ACCENT};
        border: 1px solid {ACCENT};
    }}

    /* ── Tooltip ──────────────────────────────────────────── */
    QToolTip {{
        background-color: #1A1C22;
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
    }}

    /* ── Splitter ─────────────────────────────────────────── */
    QSplitter::handle {{
        background-color: rgba(255, 255, 255, 0.08);
    }}

    /* ── Update Dialog ────────────────────────────────────── */
    QDialog#UpdateDialog {{
        background-color: {BG_DARK};
        border: 1px solid rgba(255, 255, 255, 0.15);
    }}
    """
