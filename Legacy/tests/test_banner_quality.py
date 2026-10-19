"""
Correcao sugerida: aumentar a qualidade dos banners da tela de inicio.

Duas causas somadas:
1. As tres queries GraphQL do AniList so pediam coverImage { large }
   (~230x345px). Quando bannerImage e null, o card cai no cover como fundo
   do spotlight, e esse cover pequeno e ampliado para preencher a largura
   inteira da tela (~1300px) — um upscale de 5,6x.
2. _build_bg() escalava para o tamanho LOGICO do widget, ignorando o
   devicePixelRatio da tela — num monitor HiDPI o resultado e desenhado
   maior do que os pixels fisicos que realmente tem, piorando ainda mais
   com o zoom da interface (QT_SCALE_FACTOR, ver scaling.py).
"""
from __future__ import annotations

import inspect
import uuid

from animecaos.services.anilist_service import AniListService


def _unique_app_name() -> str:
    # Um nome deterministico (por teste) leva ao mesmo problema de
    # vazamento entre execucoes ja corrigido em tests/conftest.py para o
    # ConfigService/WatchlistService — AniListService tambem persiste cache
    # num %APPDATA% real, entao usa uuid aqui pela mesma razao.
    return f"animecaos-test-{uuid.uuid4().hex}"


# ── Queries GraphQL ──────────────────────────────────────────────


def test_query_fetch_anime_info_contem_extra_large():
    svc = AniListService(app_name=_unique_app_name())
    assert "extraLarge" in svc._query_template


def test_query_fetch_trending_contem_extra_large():
    source = inspect.getsource(AniListService.fetch_trending)
    assert "extraLarge" in source


def test_query_fetch_seasonal_contem_extra_large():
    source = inspect.getsource(AniListService.fetch_seasonal)
    assert "extraLarge" in source


# ── _media_to_card ───────────────────────────────────────────────


def test_media_to_card_prefere_extra_large(monkeypatch):
    svc = AniListService(app_name=_unique_app_name())
    monkeypatch.setattr(svc, "_download_cover_url", lambda url: f"/cache/{url.split('/')[-1]}")

    media = {
        "id": 1,
        "title": {"english": "One Piece"},
        "coverImage": {"large": "https://x/large.jpg", "extraLarge": "https://x/xl.jpg"},
        "bannerImage": None,
        "averageScore": 90,
        "episodes": 1000,
    }
    card = svc._media_to_card(media)

    assert card["cover_path"] == "/cache/xl.jpg"


def test_media_to_card_cai_em_large_quando_extra_large_e_nulo(monkeypatch):
    svc = AniListService(app_name=_unique_app_name())
    monkeypatch.setattr(svc, "_download_cover_url", lambda url: f"/cache/{url.split('/')[-1]}")

    media = {
        "id": 1,
        "title": {"english": "One Piece"},
        "coverImage": {"large": "https://x/large.jpg", "extraLarge": None},
        "bannerImage": None,
        "averageScore": 90,
        "episodes": 1000,
    }
    card = svc._media_to_card(media)

    assert card["cover_path"] == "/cache/large.jpg"


def test_media_to_card_sem_banner_url_e_none(monkeypatch):
    """Card sem banner de verdade — o consumidor (SpotlightBanner) usa isso
    pra saber que a imagem de fundo veio de um cover e precisa de blur."""
    svc = AniListService(app_name=_unique_app_name())
    monkeypatch.setattr(svc, "_download_cover_url", lambda url: "/cache/x.jpg")

    media = {
        "id": 1,
        "title": {"english": "One Piece"},
        "coverImage": {"large": "https://x/large.jpg"},
        "bannerImage": None,
        "averageScore": 90,
        "episodes": 1000,
    }
    card = svc._media_to_card(media)

    assert card["banner_url"] is None
