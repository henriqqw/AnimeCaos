"""
TDD: the hover-preview card (Crunchyroll-style "Novidades" reference) needs
a rating and episode count for animes reached via fetch_anime_info() (search
results, list view, discover synopsis) — previously only description and
cover were fetched. AniList's Media query and result dict must carry
averageScore/episodes through as "score"/"episodes".
"""
from __future__ import annotations

from animecaos.services.anilist_service import AniListService


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


def test_fetch_anime_info_includes_score_and_episodes(monkeypatch, tmp_path):
    service = AniListService(app_name=f"animecaos-test-{tmp_path.name}")

    media = {
        "id": 1,
        "title": {"romaji": "One Piece", "english": "One Piece"},
        "description": "A pirate adventure.",
        "coverImage": {"large": None},
        "averageScore": 87,
        "episodes": 1172,
    }

    def fake_post(url, json=None, timeout=None):
        assert "averageScore" in json["query"]
        assert "episodes" in json["query"]
        return _FakeResponse({"data": {"Media": media}})

    monkeypatch.setattr("animecaos.services.anilist_service.requests.post", fake_post)
    monkeypatch.setattr(service, "_translate_to_ptbr", lambda text: None)

    info = service.fetch_anime_info("One Piece")

    assert info["score"] == 87
    assert info["episodes"] == 1172


def test_fetch_anime_info_returns_none_score_and_episodes_when_media_not_found(monkeypatch, tmp_path):
    service = AniListService(app_name=f"animecaos-test-{tmp_path.name}")

    def fake_post(url, json=None, timeout=None):
        return _FakeResponse({"data": {"Media": None}})

    monkeypatch.setattr("animecaos.services.anilist_service.requests.post", fake_post)

    info = service.fetch_anime_info("Anime Inexistente")

    assert info["score"] is None
    assert info["episodes"] is None
