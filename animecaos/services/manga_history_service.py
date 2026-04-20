from __future__ import annotations

import os
from dataclasses import dataclass
from json import JSONDecodeError, dump, load
from pathlib import Path
from typing import Optional

APP_NAME = "AnimeCaos"


def _history_dir() -> Path:
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME
    return Path.home() / ".local" / "state" / APP_NAME


@dataclass(frozen=True)
class MangaHistoryEntry:
    manga_id: str
    manga_title: str
    chapter_id: str
    chapter_label: str
    page: int
    cover_path: Optional[str] = None

    @property
    def label(self) -> str:
        return f"{self.manga_title} ({self.chapter_label})"


class MangaHistoryService:
    def __init__(self) -> None:
        self._file = _history_dir() / "manga_history.json"

    def load_entries(self) -> list[MangaHistoryEntry]:
        data = self._read(ignore_errors=True)
        return [
            MangaHistoryEntry(
                manga_id=mid,
                manga_title=v.get("title", mid),
                chapter_id=v.get("chapter_id", ""),
                chapter_label=v.get("chapter_label", ""),
                page=v.get("page", 0),
                cover_path=v.get("cover_path"),
            )
            for mid, v in data.items()
            if isinstance(v, dict)
        ]

    def save_entry(
        self,
        manga_id: str,
        manga_title: str,
        chapter_id: str,
        chapter_label: str,
        page: int,
        cover_path: Optional[str] = None,
    ) -> None:
        data = self._read(ignore_errors=True)
        data[manga_id] = {
            "title": manga_title,
            "chapter_id": chapter_id,
            "chapter_label": chapter_label,
            "page": page,
            "cover_path": cover_path,
        }
        self._file.parent.mkdir(parents=True, exist_ok=True)
        with self._file.open("w", encoding="utf-8") as fp:
            dump(data, fp, ensure_ascii=False, indent=2)

    def _read(self, ignore_errors: bool = False) -> dict:
        try:
            with self._file.open("r", encoding="utf-8") as fp:
                d = load(fp)
        except FileNotFoundError:
            return {}
        except (PermissionError, JSONDecodeError):
            if ignore_errors:
                return {}
            raise
        return d if isinstance(d, dict) else {}
