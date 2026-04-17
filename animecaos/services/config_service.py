from __future__ import annotations

import json
import threading
from typing import Any

from animecaos.services.watchlist_service import _watchlist_dir

_APP_NAME = "AnimeCaos"


class ConfigService:
    def __init__(self, app_name: str = _APP_NAME) -> None:
        self._path = _watchlist_dir(app_name) / "config.json"
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text("utf-8"))
        except Exception:
            self._data = {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2), "utf-8")
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._save()

    def clear_anilist(self) -> None:
        with self._lock:
            for k in (
                "anilist_access_token",
                "anilist_user_id",
                "anilist_username",
                "anilist_avatar_url",
                "anilist_anime_count",
                "anilist_episodes_watched",
                "anilist_minutes_watched",
            ):
                self._data.pop(k, None)
            self._save()
