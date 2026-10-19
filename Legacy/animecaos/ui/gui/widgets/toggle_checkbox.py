"""
Hand-painted checkbox used anywhere a QCheckBox would otherwise be shown.

A plain QCheckBox was used originally, but the app's global QSS only fills
the checked indicator with a solid accent color and draws no checkmark
glyph on top — so it visually reads as a decorative colored square rather
than a checkbox (this is what mini_player.py's autoplay toggle ran into
first, then settings_view.py's auto-close toggle hit the exact same thing).
This draws an explicit check instead, and is shared by both.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal, QPointF, QRectF, QSize
from PySide6.QtGui import QColor, QCursor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class ToggleCheckbox(QWidget):
    """Small hand-painted checkbox with a text label."""

    toggled = Signal(bool)

    _BOX = 16
    _GAP = 8
    _RIGHT_PAD = 3  # safety margin so minor metric/render rounding can't clip the label

    def __init__(self, text: str, parent: QWidget | None = None, checked: bool = True) -> None:
        super().__init__(parent)
        self._text = text
        self._checked = checked
        self._hover = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # Width is NOT computed here: at construction time the widget isn't
        # parented yet, so self.font() is still the pre-QSS default font,
        # not the "Segoe UI" font the app's global stylesheet applies once
        # mounted — measuring now under-sized the box and clipped the label.
        # sizeHint() (below) always measures the *current* font instead.

    def sizeHint(self) -> QSize:
        text_width = QFontMetrics(self.font()).horizontalAdvance(self._text)
        return QSize(self._BOX + self._GAP + text_width + self._RIGHT_PAD, 24)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self.updateGeometry()

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        checked = bool(checked)
        if checked == self._checked:
            return
        self._checked = checked
        self.update()
        self.toggled.emit(self._checked)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self.font())

        box_rect = QRectF(0, (self.height() - self._BOX) / 2, self._BOX, self._BOX)
        box_path = QPainterPath()
        box_path.addRoundedRect(box_rect, 4, 4)

        if self._checked:
            p.fillPath(box_path, QColor(212, 66, 66, 255))
            p.setPen(QPen(QColor(212, 66, 66), 1.0))
        else:
            p.fillPath(box_path, QColor(255, 255, 255, 28 if self._hover else 15))
            p.setPen(QPen(QColor(255, 255, 255, 90), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(box_rect, 4, 4)

        if self._checked:
            check_pen = QPen(QColor(255, 255, 255), 2.0)
            check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            check_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(check_pen)
            x, y = box_rect.left(), box_rect.top()
            p.drawLine(QPointF(x + 3.5, y + 8.5), QPointF(x + 6.5, y + 11.5))
            p.drawLine(QPointF(x + 6.5, y + 11.5), QPointF(x + 12.5, y + 4.5))

        p.setPen(QColor(200, 203, 210, 235 if self._checked or self._hover else 190))
        text_rect = QRectF(self._BOX + self._GAP, 0, self.width() - self._BOX - self._GAP, self.height())
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._text)

        p.end()
