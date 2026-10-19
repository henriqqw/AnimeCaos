from __future__ import annotations

import os
from dataclasses import dataclass
from json import JSONDecodeError, dump, load
from pathlib import Path

from animecaos.core.paths import user_data_dir


APP_NAME = "AnimeCaos"
LEGACY_APP_NAMES = ["animecaos"]


@dataclass(frozen=True)
class HistoryEntry:
    anime: str
    episode_index: int
    episode_sources: list[tuple[list[str], str]]

    @property
    def label(self) -> str:
        return f"{self.anime} (ultimo episodio {self.episode_index + 1})"


def _history_dir(app_name: str) -> Path:
    # Single definition lives in core.paths; this alias is kept so the
    # existing importers of this module keep working unchanged.
    return user_data_dir(app_name)


class HistoryService:
    """Persistence service for continue-watching data."""

    def __init__(
        self,
        app_name: str = APP_NAME,
        legacy_app_names: list[str] = LEGACY_APP_NAMES,
    ) -> None:
        self._history_file = _history_dir(app_name) / "history.json"
        
        self._legacy_history_files = [
            _history_dir(legacy) / "history.json" for legacy in legacy_app_names
        ]

    def load_entries(self) -> list[HistoryEntry]:
        data = self._read_data()
        entries: list[HistoryEntry] = []

        for anime, payload in data.items():
            parsed = self._parse_entry(payload)
            if parsed is None:
                continue

            episode_sources, episode_index = parsed
            entries.append(
                HistoryEntry(
                    anime=anime,
                    episode_index=episode_index,
                    episode_sources=episode_sources,
                )
            )

        entries.sort(key=lambda entry: entry.anime.lower())
        return entries

    def save_entry(
        self,
        anime: str,
        episode_index: int,
        episode_sources: list[tuple[list[str], str]],
    ) -> None:
        if not anime or episode_index < 0 or not episode_sources:
            return

        data = self._read_data(ignore_errors=True)
        data[anime] = [self._serialize_sources(episode_sources), episode_index]

        self._history_file.parent.mkdir(parents=True, exist_ok=True)
        with self._history_file.open("w", encoding="utf-8") as history_fp:
            dump(data, history_fp, ensure_ascii=False, indent=2)

    def _resolve_read_path(self) -> Path:
        if self._history_file.exists():
            return self._history_file
        
        for legacy_file in self._legacy_history_files:
            if legacy_file.exists():
                return legacy_file
                
        return self._history_file

    def _read_data(self, ignore_errors: bool = False) -> dict:
        path = self._resolve_read_path()
        try:
            with path.open("r", encoding="utf-8") as history_fp:
                data = load(history_fp)
        except FileNotFoundError:
            return {}
        except (PermissionError, JSONDecodeError):
            if ignore_errors:
                return {}
            raise

        return data if isinstance(data, dict) else {}

    def _parse_entry(
        self,
        payload: object,
    ) -> tuple[list[tuple[list[str], str]], int] | None:
        if not isinstance(payload, list) or len(payload) != 2:
            return None

        raw_sources, raw_episode_index = payload
        if not isinstance(raw_episode_index, int) or raw_episode_index < 0:
            return None

        episode_sources = self._parse_sources(raw_sources)
        if not episode_sources:
            return None

        return episode_sources, raw_episode_index

    def _parse_sources(self, raw_sources: object) -> list[tuple[list[str], str]]:
        parsed: list[tuple[list[str], str]] = []
        if not isinstance(raw_sources, list):
            return parsed

        for item in raw_sources:
            if not isinstance(item, list) or len(item) != 2:
                continue

            urls_obj, source_obj = item
            if not isinstance(urls_obj, list) or not isinstance(source_obj, str):
                continue

            urls = [url for url in urls_obj if isinstance(url, str) and url]
            if not urls:
                continue

            parsed.append((urls, source_obj))

        return parsed

    def _serialize_sources(self, episode_sources: list[tuple[list[str], str]]) -> list[list[object]]:
        serializable: list[list[object]] = []
        for urls, source in episode_sources:
            if not urls or not source:
                continue
            serializable.append([list(urls), source])
        return serializable
