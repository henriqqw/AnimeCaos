"""Disk-backed cache for resolved player URLs.

Avoids repeating the full Selenium scrape when the same episode is opened
again. TTL is 4 hours — CDN tokens typically stay valid for at least that long.

Storage now goes through the shared SQLite cache instead of a standalone
JSON file. The behaviour callers see is identical; what changes is that
entries are actually evicted when they expire (the JSON version kept every
entry it had ever written, forever, and reparsed + rewrote the whole file
on every single lookup and store).
"""

import logging

from animecaos.services.cache_store import get_store, ttl_for

log = logging.getLogger(__name__)

_NAMESPACE = "player_url"


def _key(plugin: str, episode_url: str) -> str:
    return f"{_NAMESPACE}:{plugin}:{episode_url}"


def get_cached_player_url(plugin: str, episode_url: str) -> str | None:
    try:
        # allow_stale=False: an expired CDN token is worse than useless, so
        # unlike metadata this must never serve past its TTL.
        hit = get_store().get(_key(plugin, episode_url), allow_stale=False)
    except Exception as exc:
        log.debug("player_cache: read failed: %s", exc)
        return None
    if hit is None or hit.is_negative:
        return None
    return hit.value or None


def cache_player_url(plugin: str, episode_url: str, url: str) -> None:
    if not url:
        return
    soft, hard = ttl_for(_NAMESPACE)
    try:
        get_store().put(
            _key(plugin, episode_url), _NAMESPACE, url, soft_ttl=soft, hard_ttl=hard
        )
    except Exception as exc:
        log.debug("player_cache: write failed: %s", exc)
