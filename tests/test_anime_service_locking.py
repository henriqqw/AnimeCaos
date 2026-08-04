"""
Fase 1 (TDD): AnimeService.resolve_player_url / search_animes / fetch_episode_titles
must never block forever on the internal rep lock. Today _rep_lock is a plain
threading.Lock() acquired with `with self._rep_lock:` — no timeout — so a slow
network call (or a hung Selenium page load) inside one operation freezes every
other operation (search, play, download) indefinitely.

These tests hold the lock from a background thread (simulating a stuck
operation) and assert that a second call fails fast with OperationBusyError
instead of hanging.
"""
from __future__ import annotations

import threading
import time

import pytest

from animecaos.services.anime_service import AnimeService, OperationBusyError


@pytest.fixture
def service() -> AnimeService:
    svc = AnimeService(debug=True, rep_lock_timeout=0.3)
    svc._plugins_loaded = True  # skip real plugin loading
    return svc


def _hold_lock_for(svc: AnimeService, seconds: float) -> threading.Thread:
    def _hold():
        with svc._rep_lock:
            time.sleep(seconds)

    t = threading.Thread(target=_hold, daemon=True)
    t.start()
    # Give the thread a moment to actually acquire the lock before returning.
    while not svc._rep_lock.locked():
        time.sleep(0.005)
    return t


def test_resolve_player_url_raises_when_lock_held_too_long(service: AnimeService):
    holder = _hold_lock_for(service, seconds=1.0)
    started = time.monotonic()

    with pytest.raises(OperationBusyError):
        service.resolve_player_url("Some Anime", 0)

    elapsed = time.monotonic() - started
    assert elapsed < 0.8, f"resolve_player_url blocked for {elapsed:.2f}s instead of failing fast"
    holder.join(timeout=3)


def test_search_animes_raises_when_lock_held_too_long(service: AnimeService):
    holder = _hold_lock_for(service, seconds=1.0)
    started = time.monotonic()

    with pytest.raises(OperationBusyError):
        service.search_animes("one piece")

    elapsed = time.monotonic() - started
    assert elapsed < 0.8, f"search_animes blocked for {elapsed:.2f}s instead of failing fast"
    holder.join(timeout=3)


def test_resolve_player_url_still_works_when_lock_is_free(service: AnimeService, monkeypatch):
    from animecaos.core.repository import rep

    monkeypatch.setattr(rep, "anime_episodes_urls", {"Some Anime": [(["u"], "plugin")]})
    monkeypatch.setattr(rep, "search_player", lambda anime, ep: "https://example.com/video.mp4")

    url = service.resolve_player_url("Some Anime", 0)
    assert url == "https://example.com/video.mp4"


def test_resolve_player_url_does_not_self_deadlock_when_episodes_not_cached(
    service: AnimeService, monkeypatch
):
    """resolve_player_url() internally calls fetch_episode_titles() when the
    episode cache is empty (e.g. cleared by a fresh search while the user was
    still on a previously-viewed anime's detail page). Both methods acquire
    the same non-reentrant _rep_lock — calling one from inside the other on
    the same thread must not deadlock."""
    from animecaos.core.repository import rep

    monkeypatch.setattr(rep, "anime_episodes_urls", {})  # cache empty, as after reset_runtime_data()
    monkeypatch.setattr(rep, "anime_to_urls", {"Some Anime": "https://example.com/anime"})
    monkeypatch.setattr(rep, "search_episodes", lambda anime: None)
    monkeypatch.setattr(rep, "get_episode_list", lambda anime: ["Episodio 1"])
    monkeypatch.setattr(rep, "search_player", lambda anime, ep: "https://example.com/video.mp4")

    started = time.monotonic()
    url = service.resolve_player_url("Some Anime", 0)
    elapsed = time.monotonic() - started

    assert url == "https://example.com/video.mp4"
    assert elapsed < 0.8, f"resolve_player_url self-deadlocked for {elapsed:.2f}s"
