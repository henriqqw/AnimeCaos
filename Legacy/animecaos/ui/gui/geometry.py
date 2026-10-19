"""Persistencia da posicao/tamanho da janela principal.

MainWindow.saveGeometry()/restoreGeometry() ja lidam com o QByteArray em si;
o que falta e serializa-lo para o config.json (JSON nao tem tipo binario, daí
base64) e um filtro de sanidade: se a geometria salva ficou fora de qualquer
tela conectada — por exemplo o usuario fechou o app com um monitor externo
que depois foi desconectado — restaurar cegamente deixaria a janela
inacessivel. geometry_is_on_screen() decide isso antes de restaurar.
"""
from __future__ import annotations

import base64
import binascii

from PySide6.QtCore import QByteArray, QRect

WINDOW_GEOMETRY_KEY = "window_geometry"

# Fracao minima da area da janela que precisa estar sobre alguma tela para a
# geometria salva ser considerada utilizavel.
_MIN_VISIBLE_FRACTION = 0.25


def encode_geometry(geometry: QByteArray) -> str:
    return base64.b64encode(bytes(geometry.data())).decode("ascii")


def decode_geometry(text: str | None) -> QByteArray | None:
    if not text:
        return None
    try:
        raw = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        return None
    return QByteArray(raw)


def geometry_is_on_screen(window_rect: QRect, screen_rects: list[QRect]) -> bool:
    """True se pelo menos _MIN_VISIBLE_FRACTION da area de `window_rect`
    estiver sobreposta a alguma tela em `screen_rects`."""
    window_area = window_rect.width() * window_rect.height()
    if window_area <= 0 or not screen_rects:
        return False
    for screen in screen_rects:
        overlap = window_rect.intersected(screen)
        if overlap.width() * overlap.height() >= window_area * _MIN_VISIBLE_FRACTION:
            return True
    return False
