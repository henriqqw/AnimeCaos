from __future__ import annotations

import os
from json import JSONDecodeError, dump, load
from pathlib import Path

from animecaos.core.paths import user_data_dir

APP_NAME = "AnimeCaos"
LEGACY_APP_NAMES = ["animecaos"]


def _watchlist_dir(app_name: str) -> Path:
    # Single definition lives in core.paths; this alias is kept so the
    # existing importers of this module keep working unchanged.
    return user_data_dir(app_name)


class WatchlistService:
    """Persistence service for favorited animes (watchlist)."""

    def __init__(
        self,
        app_name: str = APP_NAME,
        legacy_app_names: list[str] = LEGACY_APP_NAMES,
    ) -> None:
        self._watchlist_file = _watchlist_dir(app_name) / "watchlist.json"
        
        self._legacy_watchlist_files = [
            _watchlist_dir(legacy) / "watchlist.json" for legacy in legacy_app_names
        ]

    def load_watchlist(self) -> list[str]:
        data = self._read_data()
        if not isinstance(data, list):
            return []
        
        animes = [str(item) for item in data if isinstance(item, str)]
        animes.sort(key=lambda a: a.lower())
        return animes

    def add_anime(self, anime: str) -> None:
        if not anime:
            return

        animes = set(self.load_watchlist())
        animes.add(anime)

        self._save_data(list(animes))

    def remove_anime(self, anime: str) -> None:
        if not anime:
            return

        animes = set(self.load_watchlist())
        animes.discard(anime)
        self._save_data(list(animes))

    def is_favorited(self, anime: str) -> bool:
        return anime in self.load_watchlist()

    def _read_data(self, ignore_errors: bool = False) -> list[str]:
        target_file = self._watchlist_file
        
        if not target_file.exists():
            for legacy_file in self._legacy_watchlist_files:
                if legacy_file.exists():
                    target_file = legacy_file
                    break
        
        if not target_file.exists():
            return []

        try:
            with target_file.open("r", encoding="utf-8") as file:
                data = load(file)
        except (PermissionError, JSONDecodeError):
            if ignore_errors:
                return []
            raise

        return data if isinstance(data, list) else []

    def _save_data(self, animes: list[str]) -> None:
        self._watchlist_file.parent.mkdir(parents=True, exist_ok=True)
        with self._watchlist_file.open("w", encoding="utf-8") as file:
            dump(animes, file, ensure_ascii=False, indent=2)
