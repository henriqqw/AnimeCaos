from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QPushButton


class AnimatedButton(QPushButton):
    """QPushButton with a smooth opacity fade on press/release."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._effect: QGraphicsOpacityEffect | None = None
        self._anim: QPropertyAnimation | None = None

    def _ensure_effect(self) -> QGraphicsOpacityEffect:
        if self._effect is None or not self._effect.parent():
            self._effect = QGraphicsOpacityEffect(self)
            self._effect.setOpacity(1.0)
            self.setGraphicsEffect(self._effect)
            self._anim = QPropertyAnimation(self._effect, b"opacity", self)
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.finished.connect(self._on_anim_finished)
        return self._effect

    def _on_anim_finished(self) -> None:
        if self._effect and self._effect.opacity() >= 1.0:
            self.setGraphicsEffect(None)
            self._effect = None
            self._anim = None

    def mousePressEvent(self, event):
        effect = self._ensure_effect()
        self._anim.stop()
        self._anim.setDuration(80)
        self._anim.setStartValue(effect.opacity())
        self._anim.setEndValue(0.55)
        self._anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        effect = self._ensure_effect()
        self._anim.stop()
        self._anim.setDuration(160)
        self._anim.setStartValue(effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().mouseReleaseEvent(event)
