"""
Lucide-style SVG icons rendered as QPixmap via QPainter.

Each icon is a function that returns a QPixmap at the requested size and color.
SVG paths are from the Lucide icon set (https://lucide.dev) — MIT licensed.
All icons use a 24x24 viewBox with stroke-based rendering.
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

# Stroke width used by Lucide (default 2px in 24x24 viewBox)
_STROKE_W = 2.0
_VIEWBOX = 24.0


def _make_pen(color: QColor, scale: float) -> QPen:
    pen = QPen(color, _STROKE_W * scale)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _begin(size: int, color: str) -> tuple[QPixmap, QPainter, float, QColor]:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / _VIEWBOX
    c = QColor(color)
    p.setPen(_make_pen(c, scale))
    p.setBrush(Qt.BrushStyle.NoBrush)
    return pm, p, scale, c


def _s(v: float, scale: float) -> float:
    return v * scale


# ── Icon: Home (house) ───────────────────────────────────────────
def icon_home(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    # Roof: M3 9l9-7 9 7
    path = QPainterPath()
    path.moveTo(_s(3, s), _s(9, s))
    path.lineTo(_s(12, s), _s(2, s))
    path.lineTo(_s(21, s), _s(9, s))
    p.drawPath(path)
    # House body
    path2 = QPainterPath()
    path2.moveTo(_s(9, s), _s(22, s))
    path2.lineTo(_s(9, s), _s(12, s))
    path2.lineTo(_s(15, s), _s(12, s))
    path2.lineTo(_s(15, s), _s(22, s))
    p.drawPath(path2)
    # Walls
    path3 = QPainterPath()
    path3.moveTo(_s(5, s), _s(8, s))
    path3.lineTo(_s(5, s), _s(22, s))
    path3.lineTo(_s(19, s), _s(22, s))
    path3.lineTo(_s(19, s), _s(8, s))
    p.drawPath(path3)
    p.end()
    return pm


# ── Icon: Search (magnifying glass) ──────────────────────────────
def icon_search(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    # Circle
    p.drawEllipse(QRectF(_s(2, s), _s(2, s), _s(16, s), _s(16, s)))
    # Handle: line from ~14.5,14.5 to 21,21  (adjusted for center 11,11 r=8)
    p.drawLine(QPointF(_s(15.5, s), _s(15.5, s)), QPointF(_s(21, s), _s(21, s)))
    p.end()
    return pm


# ── Icon: Play (triangle) ────────────────────────────────────────
def icon_play(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    p.setBrush(QColor(color))
    path = QPainterPath()
    path.moveTo(_s(6, s), _s(3, s))
    path.lineTo(_s(20, s), _s(12, s))
    path.lineTo(_s(6, s), _s(21, s))
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return pm


# ── Icon: Download (arrow down to tray) ──────────────────────────
def icon_download(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    # Arrow down
    p.drawLine(QPointF(_s(12, s), _s(3, s)), QPointF(_s(12, s), _s(15, s)))
    # Arrow head
    path = QPainterPath()
    path.moveTo(_s(8, s), _s(11, s))
    path.lineTo(_s(12, s), _s(15, s))
    path.lineTo(_s(16, s), _s(11, s))
    p.drawPath(path)
    # Tray
    path2 = QPainterPath()
    path2.moveTo(_s(21, s), _s(15, s))
    path2.lineTo(_s(21, s), _s(19, s))
    path2.lineTo(_s(21, s), _s(21, s))
    path2.lineTo(_s(3, s), _s(21, s))
    path2.lineTo(_s(3, s), _s(15, s))
    p.drawPath(path2)
    p.end()
    return pm


# ── Icon: Heart (favorite) ───────────────────────────────────────
def icon_heart(size: int = 20, color: str = "#A7ACB5", filled: bool = False) -> QPixmap:
    pm, p, s, c = _begin(size, color)
    if filled:
        p.setBrush(QColor(color))
    path = QPainterPath()
    # Approximate heart using cubic beziers
    path.moveTo(_s(12, s), _s(21, s))
    path.cubicTo(_s(2, s), _s(14, s), _s(2, s), _s(6, s), _s(7, s), _s(4, s))
    path.cubicTo(_s(9.5, s), _s(3, s), _s(12, s), _s(6, s), _s(12, s), _s(6, s))
    path.cubicTo(_s(12, s), _s(6, s), _s(14.5, s), _s(3, s), _s(17, s), _s(4, s))
    path.cubicTo(_s(22, s), _s(6, s), _s(22, s), _s(14, s), _s(12, s), _s(21, s))
    p.drawPath(path)
    p.end()
    return pm


# ── Icon: Skip Back (previous) ───────────────────────────────────
def icon_skip_back(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    # Left bar
    p.drawLine(QPointF(_s(5, s), _s(5, s)), QPointF(_s(5, s), _s(19, s)))
    # Triangle pointing left
    p.setBrush(QColor(color))
    path = QPainterPath()
    path.moveTo(_s(19, s), _s(5, s))
    path.lineTo(_s(9, s), _s(12, s))
    path.lineTo(_s(19, s), _s(19, s))
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return pm


# ── Icon: Skip Forward (next) ────────────────────────────────────
def icon_skip_forward(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    # Right bar
    p.drawLine(QPointF(_s(19, s), _s(5, s)), QPointF(_s(19, s), _s(19, s)))
    # Triangle pointing right
    p.setBrush(QColor(color))
    path = QPainterPath()
    path.moveTo(_s(5, s), _s(5, s))
    path.lineTo(_s(15, s), _s(12, s))
    path.lineTo(_s(5, s), _s(19, s))
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return pm


# ── Icon: X (close) ──────────────────────────────────────────────
def icon_x(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    p.drawLine(QPointF(_s(6, s), _s(6, s)), QPointF(_s(18, s), _s(18, s)))
    p.drawLine(QPointF(_s(18, s), _s(6, s)), QPointF(_s(6, s), _s(18, s)))
    p.end()
    return pm


# ── Icon: ArrowLeft (back) ───────────────────────────────────────
def icon_arrow_left(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    p.drawLine(QPointF(_s(19, s), _s(12, s)), QPointF(_s(5, s), _s(12, s)))
    path = QPainterPath()
    path.moveTo(_s(12, s), _s(5, s))
    path.lineTo(_s(5, s), _s(12, s))
    path.lineTo(_s(12, s), _s(19, s))
    p.drawPath(path)
    p.end()
    return pm


# ── Icon: Terminal (log/console) ──────────────────────────────────
def icon_terminal(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    # Prompt chevron
    path = QPainterPath()
    path.moveTo(_s(4, s), _s(17, s))
    path.lineTo(_s(10, s), _s(11, s))
    path.lineTo(_s(4, s), _s(5, s))
    p.drawPath(path)
    # Cursor line
    p.drawLine(QPointF(_s(12, s), _s(19, s)), QPointF(_s(20, s), _s(19, s)))
    p.end()
    return pm


# ── Icon: Clock (history) ────────────────────────────────────────
def icon_clock(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    p.drawEllipse(QRectF(_s(2, s), _s(2, s), _s(20, s), _s(20, s)))
    p.drawLine(QPointF(_s(12, s), _s(6, s)), QPointF(_s(12, s), _s(12, s)))
    p.drawLine(QPointF(_s(12, s), _s(12, s)), QPointF(_s(16, s), _s(14, s)))
    p.end()
    return pm


# ── Icon: Star (bookmark/favorite) ───────────────────────────────
def icon_star(size: int = 20, color: str = "#A7ACB5", filled: bool = False) -> QPixmap:
    pm, p, s, c = _begin(size, color)
    if filled:
        p.setBrush(QColor(color))
    import math
    path = QPainterPath()
    cx, cy = _s(12, s), _s(12, s)
    outer_r = _s(9.5, s)
    inner_r = _s(4.2, s)
    for i in range(5):
        angle_outer = math.radians(-90 + i * 72)
        angle_inner = math.radians(-90 + i * 72 + 36)
        ox = cx + outer_r * math.cos(angle_outer)
        oy = cy + outer_r * math.sin(angle_outer)
        ix = cx + inner_r * math.cos(angle_inner)
        iy = cy + inner_r * math.sin(angle_inner)
        if i == 0:
            path.moveTo(ox, oy)
        else:
            path.lineTo(ox, oy)
        path.lineTo(ix, iy)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return pm


# ── Icon: Monitor (TV/episodes) ──────────────────────────────────
def icon_monitor(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    p.drawRoundedRect(QRectF(_s(2, s), _s(3, s), _s(20, s), _s(14, s)), _s(2, s), _s(2, s))
    p.drawLine(QPointF(_s(8, s), _s(21, s)), QPointF(_s(16, s), _s(21, s)))
    p.drawLine(QPointF(_s(12, s), _s(17, s)), QPointF(_s(12, s), _s(21, s)))
    p.end()
    return pm


# ── Icon: Loader (spinning) ──────────────────────────────────────
def icon_loader(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    # Simple circle with gap (like a spinner)
    import math
    cx, cy = _s(12, s), _s(12, s)
    r = _s(8, s)
    # Draw arc segments with varying opacity
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + r * math.cos(angle)
        y1 = cy + r * math.sin(angle)
        x2 = cx + (r - _s(2, s)) * math.cos(angle)
        y2 = cy + (r - _s(2, s)) * math.sin(angle)
        alpha = int(255 * (i + 1) / 8)
        pen = QPen(QColor(c.red(), c.green(), c.blue(), alpha), _STROKE_W * s)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    p.end()
    return pm


# ── Icon: Search X (no results) ──────────────────────────────────
def icon_search_x(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    # Circle
    p.drawEllipse(QRectF(_s(2, s), _s(2, s), _s(16, s), _s(16, s)))
    # Handle
    p.drawLine(QPointF(_s(15.5, s), _s(15.5, s)), QPointF(_s(21, s), _s(21, s)))
    # X inside circle
    p.drawLine(QPointF(_s(7, s), _s(7, s)), QPointF(_s(13, s), _s(13, s)))
    p.drawLine(QPointF(_s(13, s), _s(7, s)), QPointF(_s(7, s), _s(13, s)))
    p.end()
    return pm


# ── Icon: User (profile) ─────────────────────────────────────────
def icon_user(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    # Head: circle cx=12, cy=8, r=5
    p.drawEllipse(QRectF(_s(7, s), _s(3, s), _s(10, s), _s(10, s)))
    # Shoulders: top arc of circle centered at (12,21) with r=8
    p.drawArc(
        QRectF(_s(4, s), _s(13, s), _s(16, s), _s(16, s)),
        0,
        180 * 16,
    )
    p.end()
    return pm


# ── Icon: Folder (downloads library) ────────────────────────────
def icon_folder(size: int = 20, color: str = "#A7ACB5") -> QPixmap:
    pm, p, s, c = _begin(size, color)
    # Tab: top-left bump
    tab = QPainterPath()
    tab.moveTo(_s(2, s), _s(10, s))
    tab.lineTo(_s(2, s), _s(8, s))
    tab.lineTo(_s(9, s), _s(8, s))
    tab.lineTo(_s(11, s), _s(6, s))
    tab.lineTo(_s(22, s), _s(6, s))
    tab.lineTo(_s(22, s), _s(10, s))
    tab.closeSubpath()
    p.drawPath(tab)
    # Body
    body = QPainterPath()
    body.addRoundedRect(
        QRectF(_s(2, s), _s(10, s), _s(20, s), _s(12, s)), _s(1.5, s), _s(1.5, s)
    )
    p.drawPath(body)
    p.end()
    return pm


# ── Utility: create QIcon from pixmap function ───────────────────
def make_icon(fn, size: int = 20, color: str = "#A7ACB5", **kwargs) -> QIcon:
    """Wrap an icon function into a QIcon."""
    return QIcon(fn(size=size, color=color, **kwargs))
