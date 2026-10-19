"""
Acessibilidade: o app precisa permitir aumentar o dimensionamento interno
(fonte + interface) para quem nao enxerga bem.

Como a UI tem 134 declaracoes `font-size: Npx` inline e dezenas de
setFixedSize(), reescalar apenas a folha de estilo global deixaria a
interface inconsistente. A abordagem e QT_SCALE_FACTOR, que escala a malha
logica de pixels inteira — mas o Qt so le essa variavel na construcao do
QApplication, entao ela precisa ser aplicada ANTES, a partir do config.json.

Este modulo e proposital-mente livre de Qt para poder ser testado sem um
QApplication.
"""
from __future__ import annotations

import sys

import pytest

from animecaos.ui.gui.scaling import (
    DEFAULT_SCALE,
    MAX_SCALE,
    MIN_SCALE,
    UI_SCALE_KEY,
    apply_ui_scale,
    build_restart_argv,
    resolve_ui_scale,
    restart_app,
)


class FakeConfig:
    """Stand-in para o ConfigService — dict em memoria, sem I/O."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value


# ── resolve_ui_scale ──────────────────────────────────────────────


def test_config_vazio_usa_escala_padrao():
    assert resolve_ui_scale(FakeConfig()) == DEFAULT_SCALE


def test_le_a_escala_gravada_no_config():
    assert resolve_ui_scale(FakeConfig({UI_SCALE_KEY: 1.25})) == 1.25


def test_escala_acima_do_maximo_e_limitada():
    assert resolve_ui_scale(FakeConfig({UI_SCALE_KEY: 2.5})) == MAX_SCALE


def test_escala_abaixo_do_minimo_e_limitada():
    assert resolve_ui_scale(FakeConfig({UI_SCALE_KEY: 0.1})) == MIN_SCALE


@pytest.mark.parametrize("lixo", ["abc", None, "", [], {}, float("nan")])
def test_valor_invalido_no_config_nao_quebra_o_startup(lixo):
    """config.json editado a mao (ou corrompido) nao pode impedir o app de abrir."""
    assert resolve_ui_scale(FakeConfig({UI_SCALE_KEY: lixo})) == DEFAULT_SCALE


def test_string_numerica_e_aceita():
    """json.load pode devolver string se a chave foi escrita a mao."""
    assert resolve_ui_scale(FakeConfig({UI_SCALE_KEY: "1.5"})) == 1.5


# ── apply_ui_scale ────────────────────────────────────────────────


def test_apply_grava_qt_scale_factor_no_ambiente():
    env: dict[str, str] = {}
    applied = apply_ui_scale(FakeConfig({UI_SCALE_KEY: 1.25}), env)
    assert applied == 1.25
    assert env["QT_SCALE_FACTOR"] == "1.25"


def test_apply_respeita_qt_scale_factor_ja_definido_pelo_usuario():
    """Quem exporta QT_SCALE_FACTOR no shell tem prioridade sobre o config."""
    env = {"QT_SCALE_FACTOR": "3"}
    apply_ui_scale(FakeConfig({UI_SCALE_KEY: 1.5}), env)
    assert env["QT_SCALE_FACTOR"] == "3"


def test_apply_com_escala_1_nao_polui_o_ambiente():
    """Em 100% nao ha nada para escalar — deixar a variavel de fora evita
    interferir na deteccao automatica de DPI do proprio Qt."""
    env: dict[str, str] = {}
    apply_ui_scale(FakeConfig({UI_SCALE_KEY: 1.0}), env)
    assert "QT_SCALE_FACTOR" not in env


# ── restart_app ───────────────────────────────────────────────────


def test_build_restart_argv_no_modo_dev_inclui_o_script():
    argv = build_restart_argv(executable="/usr/bin/python3", argv=["main.py", "--debug"], frozen=False)
    assert argv == ["/usr/bin/python3", "main.py", "--debug"]


def test_build_restart_argv_congelado_nao_repassa_o_script():
    """Num binario PyInstaller, sys.argv[0] ja e o proprio executavel —
    repassa-lo de novo faria o app tentar abrir a si mesmo como argumento."""
    argv = build_restart_argv(executable="/opt/AnimeCaos", argv=["/opt/AnimeCaos", "--debug"], frozen=True)
    assert argv == ["/opt/AnimeCaos", "--debug"]


def test_restart_app_relanca_e_encerra():
    spawned: list = []
    quit_calls: list = []

    restart_app(spawn=lambda a: spawned.append(a), quit_fn=lambda: quit_calls.append(1))

    assert len(spawned) == 1
    assert spawned[0][0] == sys.executable
    assert len(quit_calls) == 1


def test_restart_app_nao_encerra_se_o_relancamento_falhar():
    """Melhor manter o app aberto na escala antiga do que fechar sem reabrir."""
    def boom(_argv):
        raise OSError("nao foi possivel criar o processo")

    quit_calls: list = []
    restart_app(spawn=boom, quit_fn=lambda: quit_calls.append(1))

    assert quit_calls == []
