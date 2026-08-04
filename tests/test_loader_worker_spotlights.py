"""
TDD: the splash-screen loader also builds the hero carousel data (so it's
ready the instant the main window appears). Its `trending` list is already
availability-filtered by the time _collect_spotlights() runs (see
_filter_section), so it just takes the first N and fetches their extras in
parallel — mirroring MainWindow._collect_spotlights() for the non-preloaded
fallback path.
"""
from __future__ import annotations

from animecaos.ui.gui.workers.loader_worker import LoaderWorker, _SPOTLIGHT_COUNT


class _FakeAniList:
    def __init__(self):
        self.calls: list[str] = []

    def fetch_spotlight_extras(self, card: dict) -> dict:
        self.calls.append(card["title"])
        return {**card, "description": f"desc for {card['title']}"}


def _trending(n: int) -> list[dict]:
    return [{"title": f"Anime {i}"} for i in range(n)]


def test_takes_the_first_n_and_ranks_them_in_order():
    fake_anilist = _FakeAniList()
    worker = LoaderWorker(anilist_service=fake_anilist, anime_service=None)

    spotlights = worker._collect_spotlights(_trending(8))

    assert len(spotlights) == _SPOTLIGHT_COUNT == 5
    assert [s["title"] for s in spotlights] == [f"Anime {i}" for i in range(5)]
    assert [s["_rank"] for s in spotlights] == [1, 2, 3, 4, 5]
    assert all(s["description"] for s in spotlights)


def test_fewer_than_five_trending_items_returns_all_of_them():
    fake_anilist = _FakeAniList()
    worker = LoaderWorker(anilist_service=fake_anilist, anime_service=None)

    spotlights = worker._collect_spotlights(_trending(2))

    assert [s["title"] for s in spotlights] == ["Anime 0", "Anime 1"]


def test_empty_trending_returns_empty_list():
    fake_anilist = _FakeAniList()
    worker = LoaderWorker(anilist_service=fake_anilist, anime_service=None)

    assert worker._collect_spotlights([]) == []


def test_a_candidate_whose_extras_fetch_fails_is_dropped_not_crashed():
    class _FlakyAniList:
        def fetch_spotlight_extras(self, card):
            if card["title"] == "Anime 1":
                raise RuntimeError("network blip")
            return dict(card)

    worker = LoaderWorker(anilist_service=_FlakyAniList(), anime_service=None)

    spotlights = worker._collect_spotlights(_trending(3))

    assert [s["title"] for s in spotlights] == ["Anime 0", "Anime 2"]
