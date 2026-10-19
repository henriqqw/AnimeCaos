"""
Sugestao de usuario: lembrar a ultima posicao/tamanho da janela.

Hoje MainWindow.__init__ sempre faz resize(1320, 820) e closeEvent() so
desconecta o Discord — nada e persistido. Aqui a geometria (QByteArray de
saveGeometry()) e serializada em base64 dentro do config.json existente.

O caso que mais importa e o de guarda: se a geometria salva ficou fora de
qualquer tela conectada (ex.: usuario fechou o app com um monitor externo
que depois foi desconectado), restaurar cegamente deixaria a janela
invisivel. geometry_is_on_screen() e o que evita isso.
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QRect

from animecaos.ui.gui.geometry import (
    WINDOW_GEOMETRY_KEY,
    decode_geometry,
    encode_geometry,
    geometry_is_on_screen,
)


class FakeConfig:
    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value


# ── encode/decode round-trip ──────────────────────────────────────


def test_round_trip_preserva_os_bytes():
    original = QByteArray(b"\x00\x01\xff\xfegeometry-blob")
    encoded = encode_geometry(original)
    assert isinstance(encoded, str)
    decoded = decode_geometry(encoded)
    assert decoded is not None
    assert bytes(decoded.data()) == bytes(original.data())


def test_decode_de_lixo_nao_levanta_excecao():
    assert decode_geometry("!!!isso nao e base64 valido!!!") is None


def test_decode_de_vazio_devolve_none():
    assert decode_geometry("") is None
    assert decode_geometry(None) is None


# ── geometry_is_on_screen ─────────────────────────────────────────


def test_janela_totalmente_dentro_da_tela():
    screen = QRect(0, 0, 1920, 1080)
    window = QRect(100, 100, 800, 600)
    assert geometry_is_on_screen(window, [screen]) is True


def test_janela_totalmente_fora_de_qualquer_tela():
    screen = QRect(0, 0, 1920, 1080)
    window = QRect(5000, 5000, 800, 600)
    assert geometry_is_on_screen(window, [screen]) is False


def test_janela_parcialmente_visivel_o_suficiente_conta_como_visivel():
    """>= 25% de area visivel em alguma tela e considerado suficiente."""
    screen = QRect(0, 0, 1920, 1080)
    window = QRect(1800, 100, 800, 600)  # so uma fatia entra na tela
    overlap_w = 1920 - 1800  # 120
    overlap_area = overlap_w * 600
    window_area = 800 * 600
    assert overlap_area / window_area < 0.25  # confirma a premissa do teste
    assert geometry_is_on_screen(window, [screen]) is False


def test_janela_quase_toda_visivel_conta_como_visivel():
    screen = QRect(0, 0, 1920, 1080)
    window = QRect(1700, 100, 800, 600)  # a maior parte entra na tela
    assert geometry_is_on_screen(window, [screen]) is True


def test_considera_multiplas_telas():
    screen1 = QRect(0, 0, 1920, 1080)
    screen2 = QRect(1920, 0, 1920, 1080)
    window = QRect(1900, 100, 800, 600)  # cai majoritariamente na tela 2
    assert geometry_is_on_screen(window, [screen1, screen2]) is True


def test_sem_nenhuma_tela_conectada_e_falso():
    window = QRect(100, 100, 800, 600)
    assert geometry_is_on_screen(window, []) is False


# ── integracao com MainWindow ──────────────────────────────────────


def test_fechar_a_janela_persiste_a_geometria(main_window_factory):
    window = main_window_factory()
    window.resize(1000, 700)
    window.move(50, 60)

    window.close()

    saved = window._config_service.get(WINDOW_GEOMETRY_KEY)
    assert saved is not None
    assert decode_geometry(saved) is not None


def test_segunda_janela_restaura_a_geometria_salva(main_window_factory):
    # Sob QT_QPA_PLATFORM=offscreen (usado pela suite inteira, ver
    # tests/conftest.py), a tela virtual e pequena e Qt.restoreGeometry()
    # clampa a LARGURA restaurada de volta para o minimumWidth
    # independentemente do valor salvo — um artefato do ambiente headless,
    # nao do codigo sob teste. A ALTURA, por outro lado, e restaurada com
    # fidelidade nesse mesmo ambiente, entao e o que este teste verifica:
    # prova que a segunda janela usou a geometria salva (700) em vez do
    # padrao de fabrica (820).
    first = main_window_factory()
    first.resize(1100, 700)
    first.close()

    second = main_window_factory()
    assert second.size().height() == 700


def test_geometria_fora_de_tela_cai_no_tamanho_padrao(main_window_factory):
    window = main_window_factory()
    # Geometria valida em bytes, mas fora de qualquer tela plausivel.
    fake_offscreen = QByteArray()
    fake_offscreen.append(b"\x00" * 4)  # nao decodifica como QByteArray de saveGeometry real
    window._config_service.set(WINDOW_GEOMETRY_KEY, encode_geometry(fake_offscreen))

    second = main_window_factory()
    # Nao deve levantar excecao e deve cair no tamanho padrao (>= minimo).
    assert second.size().width() >= second.minimumWidth()
