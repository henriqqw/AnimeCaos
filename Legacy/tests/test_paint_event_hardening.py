"""
Bug reportado ao vivo: rolar a tela inicial as vezes "quebra" o layout
inteiro (header/sidebar somem, cards se sobrepoem), e o terminal mostra
"QPainter::begin: A paint device can only be painted by one painter at a
time." — o app ja teve esse EXATO tipo de bug antes (ver CHANGELOG v2.0.0:
"Vazamento de memoria/crash por conflito de QPainter em AnimatedButton").

Nao consegui reproduzir o gatilho exato (rodei duas simulacoes automatizadas
de scroll+resize+hover+troca de carousel sem conseguir disparar o aviso),
mas encontrei a causa estrutural: SpotlightBanner.paintEvent() e
_PreviewPanel.paintEvent() (o backdrop do hover, reparentado na janela
principal — o candidato mais provavel, ja que um QPainter preso nele
vazaria visualmente pra fora da area de scroll) criavam QPainter(self) e so
chamavam painter.end() na ULTIMA linha do metodo, sem try/finally. Se
qualquer desenho no meio lancar uma excecao, o painter fica aberto — e o
PROXIMO repaint desse widget colide com ele, produzindo exatamente esse
aviso e travando a atualizacao visual dali pra frente.
"""
from __future__ import annotations

import pytest
from PySide6.QtGui import QPainter, QPixmap

from animecaos.ui.gui.widgets.anime_card import _PreviewPanel
from animecaos.ui.gui.widgets.spotlight_banner import SpotlightBanner


def _fake_pixmap(w: int, h: int) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill()
    return pm


class _FakePaintEvent:
    """Standing in for a real QPaintEvent — paintEvent() only calls
    super().paintEvent(event) with it, which doesn't need a real one."""


def _spy_on_painter_end(monkeypatch) -> list:
    calls: list = []
    original_end = QPainter.end

    def spy(self_painter):
        calls.append(1)
        return original_end(self_painter)

    monkeypatch.setattr(QPainter, "end", spy)
    return calls


def test_spotlight_banner_paint_event_closes_the_painter_even_if_drawing_raises(qtbot, monkeypatch):
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.resize(200, 100)
    banner._bg_pixmap = _fake_pixmap(200, 100)

    end_calls = _spy_on_painter_end(monkeypatch)
    monkeypatch.setattr(banner, "rect", lambda: (_ for _ in ()).throw(RuntimeError("simulated paint failure")))

    with pytest.raises(RuntimeError):
        banner.paintEvent(_FakePaintEvent())

    assert end_calls, "painter.end() precisa rodar mesmo quando o paintEvent lanca uma excecao"


def test_spotlight_banner_repaints_normally_after_a_failed_paint(qtbot, monkeypatch):
    """A prova real do fix: depois de uma falha, o widget ainda consegue
    pintar de novo sem o Qt reclamar de painter duplicado."""
    banner = SpotlightBanner()
    qtbot.addWidget(banner)
    banner.resize(200, 100)
    banner._bg_pixmap = _fake_pixmap(200, 100)

    original_rect = banner.rect
    monkeypatch.setattr(banner, "rect", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        banner.paintEvent(_FakePaintEvent())
    monkeypatch.setattr(banner, "rect", original_rect)

    # repaint() passa por um ciclo real do Qt (com um QPaintEvent de
    # verdade) — se o painter anterior tivesse ficado aberto, este repaint
    # colidiria com ele.
    banner.repaint()


def test_preview_panel_paint_event_closes_the_painter_even_if_drawing_raises(qtbot, monkeypatch):
    panel = _PreviewPanel()
    qtbot.addWidget(panel)
    panel.resize(150, 210)
    panel.set_art(_fake_pixmap(150, 210))

    end_calls = _spy_on_painter_end(monkeypatch)
    monkeypatch.setattr(panel, "rect", lambda: (_ for _ in ()).throw(RuntimeError("simulated paint failure")))

    with pytest.raises(RuntimeError):
        panel.paintEvent(_FakePaintEvent())

    assert end_calls, "painter.end() precisa rodar mesmo quando o paintEvent lanca uma excecao"


def test_preview_panel_repaints_normally_after_a_failed_paint(qtbot, monkeypatch):
    panel = _PreviewPanel()
    qtbot.addWidget(panel)
    panel.resize(150, 210)
    panel.set_art(_fake_pixmap(150, 210))

    original_rect = panel.rect
    monkeypatch.setattr(panel, "rect", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        panel.paintEvent(_FakePaintEvent())
    monkeypatch.setattr(panel, "rect", original_rect)

    panel.repaint()
