from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DOWNLOAD_DIR = Path.home() / "Downloads" / "AnimeCaos"
_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".m4v", ".avi", ".ts", ".mov"}


@dataclass
class DownloadEntry:
    anime: str
    episode_num: int
    file_path: str
    file_size: int

    @property
    def size_str(self) -> str:
        mb = self.file_size / (1024 * 1024)
        return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb:.0f} MB"


class DownloadsService:
    def __init__(self, download_dir: Path | None = None) -> None:
        self._dir = download_dir or DOWNLOAD_DIR

    def get_dir(self) -> Path:
        return self._dir

    def scan(self) -> list[DownloadEntry]:
        if not self._dir.exists():
            return []
        entries: list[DownloadEntry] = []
        for f in sorted(self._dir.iterdir()):
            if f.suffix.lower() not in _VIDEO_EXTS:
                continue
            m = re.match(r"^(.+?)\s*-\s*EP(\d+)\.", f.name, re.IGNORECASE)
            if not m:
                continue
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            entries.append(DownloadEntry(
                anime=m.group(1).strip(),
                episode_num=int(m.group(2)),
                file_path=str(f),
                file_size=size,
            ))
        return sorted(entries, key=lambda e: (e.anime.lower(), e.episode_num))

    def group_by_anime(self) -> dict[str, list[DownloadEntry]]:
        groups: dict[str, list[DownloadEntry]] = {}
        for e in self.scan():
            groups.setdefault(e.anime, []).append(e)
        return groups

    def total_size(self) -> int:
        return sum(e.file_size for e in self.scan())

    def delete(self, entry: DownloadEntry) -> bool:
        try:
            Path(entry.file_path).unlink(missing_ok=True)
            return True
        except Exception:
            return False
