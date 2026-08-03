"""
Animated QStackedWidget with smooth fade transitions between views.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QParallelAnimationGroup,
    Qt,
    Property,
)
from PySide6.QtWidgets import QStackedWidget, QGraphicsOpacityEffect, QWidget


class AnimatedStackedWidget(QStackedWidget):
    """QStackedWidget with cross-fade transitions between views."""

    DURATION_MS = 200

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._animating = False

    def _ensure_effect(self, index: int) -> QGraphicsOpacityEffect:
        """Attach a fresh QGraphicsOpacityEffect to the widget at *index*."""
        widget = self.widget(index)
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        return effect

    def slide_to(self, index: int) -> None:
        """Animate transition to the view at *index*."""
        if index == self.currentIndex() or self._animating:
            return
        if index < 0 or index >= self.count():
            return

        self._animating = True
        old_idx = self.currentIndex()

        # Create fresh effects for both widgets
        old_effect = self._ensure_effect(old_idx)
        new_effect = self._ensure_effect(index)

        old_effect.setOpacity(1.0)
        new_effect.setOpacity(0.0)
        self.widget(index).show()
        self.widget(index).raise_()

        group = QParallelAnimationGroup(self)

        # Fade out old
        fade_out = QPropertyAnimation(old_effect, b"opacity", group)
        fade_out.setDuration(self.DURATION_MS)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Fade in new
        fade_in = QPropertyAnimation(new_effect, b"opacity", group)
        fade_in.setDuration(self.DURATION_MS)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.InCubic)

        group.addAnimation(fade_out)
        group.addAnimation(fade_in)

        def _on_finished() -> None:
            self.setCurrentIndex(index)
            # Remove graphics effects to avoid QPainter conflicts with child
            # widgets that paint directly (PlayOverlay, SkeletonCanvas, etc.)
            self.widget(index).setGraphicsEffect(None)
            self.widget(old_idx).setGraphicsEffect(None)
            self._animating = False

        group.finished.connect(_on_finished)
        group.start()

    def slide_to_widget(self, widget: QWidget) -> None:
        """Animate transition to a specific widget."""
        idx = self.indexOf(widget)
        if idx >= 0:
            self.slide_to(idx)
