"""
Correcao sugerida: aumentar a qualidade dos banners da tela de inicio.

_build_bg() escalava a imagem de fundo do spotlight para o tamanho LOGICO
do widget, ignorando devicePixelRatio — num monitor HiDPI (ou com o zoom da
interface ligado, ver scaling.py) o resultado e desenhado maior do que os
pixels fisicos que realmente tem, ficando borrado. A correcao escala para
w*dpr x h*dpr e marca o pixmap resultante com setDevicePixelRatio(dpr), que
e como o Qt sabe desenhar um pixmap de alta resolucao em tamanho logico
correto (QPainter.drawPixmap ja leva isso em conta automaticamente).
"""
from __future__ import annotations

from PySide6.QtGui import QPixmap

from animecaos.ui.gui.widgets.spotlight_banner import SpotlightBanner


def _fake_pixmap(w: int, h: int) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill()
    return pm


def test_build_bg_em_dpr_1_produz_pixmap_no_tamanho_logico(qtbot):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.resize(800, 400)

    banner._raw_pixmap = _fake_pixmap(1600, 800)
    banner._build_bg()

    assert banner._bg_pixmap.devicePixelRatio() == 1.0
    assert banner._bg_pixmap.width() == banner.width()
    assert banner._bg_pixmap.height() == banner.height()


def test_build_bg_em_dpr_2_produz_pixmap_com_o_dobro_de_pixels(qtbot, monkeypatch):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.resize(800, 400)
    monkeypatch.setattr(banner, "devicePixelRatioF", lambda: 2.0)

    banner._raw_pixmap = _fake_pixmap(3200, 1600)
    banner._build_bg()

    assert banner._bg_pixmap.devicePixelRatio() == 2.0
    # Tamanho FISICO em pixels e o dobro; o tamanho LOGICO (o que o layout
    # ve) continua batendo com o widget, porque devicePixelRatio() e quem
    # faz essa conversao para quem consome o pixmap.
    assert banner._bg_pixmap.width() == banner.width() * 2
    assert banner._bg_pixmap.height() == banner.height() * 2
    assert banner._bg_pixmap.deviceIndependentSize().toSize() == banner.size()


# ── Fallback de cover marca a origem (para o blur ser aplicado) ─────


def test_card_sem_banner_marca_origem_como_cover(qtbot, tmp_path):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)

    cover_file = tmp_path / "cover.jpg"
    _fake_pixmap(200, 300).save(str(cover_file))

    banner._apply_card({"title": "X", "cover_path": str(cover_file), "banner_path": None}, animate=False)

    assert banner._bg_is_cover_fallback is True


def test_card_com_banner_nao_marca_origem_como_cover(qtbot, tmp_path):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)

    banner_file = tmp_path / "banner.jpg"
    _fake_pixmap(1600, 400).save(str(banner_file))

    banner._apply_card({"title": "X", "cover_path": None, "banner_path": str(banner_file)}, animate=False)

    assert banner._bg_is_cover_fallback is False


# ── Crop centralizado (nao ancorado numa borda) ──────────────────


def _half_and_half_pixmap(w: int, h: int) -> QPixmap:
    """Metade esquerda vermelha, metade direita azul — usado para provar
    de onde exatamente o crop horizontal esta tirando a fatia."""
    from PySide6.QtGui import QColor, QPainter

    pm = QPixmap(w, h)
    painter = QPainter(pm)
    painter.fillRect(0, 0, w // 2, h, QColor("red"))
    painter.fillRect(w // 2, 0, w - w // 2, h, QColor("blue"))
    painter.end()
    return pm


def test_build_bg_centraliza_o_crop_horizontal_em_vez_de_ancorar_na_borda(qtbot):
    """Bug real: o crop vertical ja era centralizado ((altura-alvo)//2), mas
    o horizontal pegava sempre a fatia mais a direita da imagem
    (largura_escalada - largura_alvo, sem dividir por 2) — qualquer banner
    mais largo que a proporcao do widget mostrava só a ponta direita da
    arte, cortando tudo que estava mais a esquerda."""
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.resize(100, 50)

    # Apos KeepAspectRatioByExpanding, uma imagem de 400x50 escala para
    # 400x50 (a altura ja bate, a largura sobra 300px) contra um alvo de
    # 100x50 — sobra exatamente o cenario onde o bug de ancoragem aparece.
    banner._raw_pixmap = _half_and_half_pixmap(400, 50)
    banner._build_bg()

    image = banner._bg_pixmap.toImage()
    left_color = image.pixelColor(0, image.height() // 2)
    right_color = image.pixelColor(image.width() - 1, image.height() // 2)

    # Um crop centralizado cai bem em cima da fronteira vermelho/azul —
    # a ponta esquerda do recorte ainda esta no lado vermelho, a direita
    # ja esta no azul. O bug anterior mostrava azul dos dois lados.
    assert left_color.red() > left_color.blue()
    assert right_color.blue() > right_color.red()
