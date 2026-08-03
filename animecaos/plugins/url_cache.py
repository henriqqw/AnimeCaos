"""Disk-backed cache for resolved player URLs.

Avoids repeating the full Selenium scrape when the same episode is opened
again. TTL is 4 hours — CDN tokens typically stay valid for at least that long.
"""

import json
import logging
import threading
import time
from pathlib import Path

from animecaos.services.watchlist_service import _watchlist_dir

log = logging.getLogger(__name__)

_CACHE_TTL = 4 * 3600  # seconds
_lock = threading.RLock()


def _cache_path() -> Path:
    p = _watchlist_dir("AnimeCaos") / "cache" / "player_urls.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load() -> dict:
    try:
        return json.loads(_cache_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    try:
        _cache_path().write_text(json.dumps(data), encoding="utf-8")
    except Exception as exc:
        log.debug("player_cache: falha ao salvar: %s", exc)


def get_cached_player_url(plugin: str, episode_url: str) -> str | None:
    key = f"{plugin}:{episode_url}"
    with _lock:
        entry = _load().get(key)
        if entry and time.time() < entry.get("expires", 0):
            return entry["url"]
    return None


def cache_player_url(plugin: str, episode_url: str, url: str) -> None:
    key = f"{plugin}:{episode_url}"
    with _lock:
        data = _load()
        data[key] = {"url": url, "expires": time.time() + _CACHE_TTL}
        _save(data)
