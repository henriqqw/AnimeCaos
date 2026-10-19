"""Dimensionamento (zoom) da interface — acessibilidade.

Qt le a variavel de ambiente QT_SCALE_FACTOR apenas na construcao do
QApplication, entao a escala salva no config.json precisa ser aplicada ANTES
disso e o app precisa reiniciar para uma escala nova entrar em vigor. Este
modulo e deliberadamente livre de PySide6 para ser testavel sem QApplication;
quem chama passa um objeto "config" com .get/.set (ConfigService real ou um
fake em teste) e um "environ" (os.environ real ou um dict em teste).
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
from typing import Any, Callable, Sequence

UI_SCALE_KEY = "ui_scale"
MIN_SCALE = 1.0
# Capped at 150%: beyond that, several hand-painted/fixed-size widgets
# (overlays, the spotlight banner) start clipping instead of reflowing —
# 100-150% covers the accessibility use case without a full layout audit.
MAX_SCALE = 1.5
DEFAULT_SCALE = 1.0


def resolve_ui_scale(config: Any) -> float:
    """Le a escala salva, tolerando config.json corrompido/editado a mao —
    um valor invalido nunca deve impedir o app de iniciar."""
    raw = config.get(UI_SCALE_KEY, DEFAULT_SCALE)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_SCALE
    if math.isnan(value) or math.isinf(value):
        return DEFAULT_SCALE
    return min(MAX_SCALE, max(MIN_SCALE, value))


def apply_ui_scale(config: Any, environ: dict) -> float:
    """Escreve QT_SCALE_FACTOR em `environ` a partir do config, a menos que
    o usuario ja tenha definido a variavel manualmente (essa tem prioridade)
    ou a escala seja 1.0 (nada a escalar — deixar de fora evita interferir
    na deteccao automatica de DPI do proprio Qt)."""
    scale = resolve_ui_scale(config)
    if "QT_SCALE_FACTOR" not in environ and scale != DEFAULT_SCALE:
        environ["QT_SCALE_FACTOR"] = str(scale)
    return scale


def build_restart_argv(executable: str, argv: Sequence[str], frozen: bool) -> list[str]:
    """Monta o argv do processo relancado.

    Em modo congelado (PyInstaller), sys.argv[0] ja E o executavel — repassa-
    lo de novo faria o app tentar se abrir como se fosse um argumento de
    arquivo. Em modo dev, sys.executable e o interpretador Python e argv[0]
    e o script (main.py), que precisa ser passado explicitamente.
    """
    if frozen:
        return list(argv)
    return [executable, *argv]


def restart_app(
    spawn: Callable[[Sequence[str]], object] = lambda argv: subprocess.Popen(argv),
    quit_fn: Callable[[], None] | None = None,
) -> None:
    """Relanca o processo atual e encerra o corrente.

    Se o relancamento falhar, o app atual NAO e encerrado — melhor continuar
    aberto na escala antiga do que fechar e nao reabrir.
    """
    argv = build_restart_argv(sys.executable, sys.argv, getattr(sys, "frozen", False))
    try:
        spawn(argv)
    except OSError:
        return
    if quit_fn is not None:
        quit_fn()
