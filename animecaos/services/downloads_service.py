from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DOWNLOAD_DIR = Path.home() / "Downloads" / "AnimeCaos"
_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".m4v", ".avi", ".ts", ".mov"}
_META_SUFFIX = ".meta.json"


def sanitize_anime_filename(anime: str) -> str:
    """Filesystem-safe version of an anime title, used for both the video
    filename and its metadata sidecar. Must stay in sync between writing
    (main_window's download flow) and reading (scan()/write_metadata()
    below) — both go through this one function so they can't drift apart."""
    return "".join(c for c in anime if c.isalnum() or c in " -_").strip()


@dataclass
class DownloadEntry:
    anime: str
    episode_num: int
    file_path: str
    file_size: int
    cover_path: str | None = None

    @property
    def size_str(self) -> str:
        mb = self.file_size / (1024 * 1024)
        return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb:.0f} MB"


class DownloadsService:
    def __init__(self, download_dir: Path | None = None) -> None:
        self._dir = download_dir or DOWNLOAD_DIR

    def get_dir(self) -> Path:
        return self._dir

    def write_metadata(self, anime: str, cover_path: str | None = None) -> None:
        """Persist the real anime title (and a known-good cover path) next to
        its downloads, keyed by the sanitized name used in the video
        filename. scan() reads this back instead of re-deriving the title
        from the filename, which is lossy (parentheses, colons, etc. are
        stripped to make a safe filename) and breaks the cover lookup for
        any anime whose title uses such characters."""
        safe_anime = sanitize_anime_filename(anime)
        if not safe_anime:
            return
        self._dir.mkdir(parents=True, exist_ok=True)
        sidecar = self._dir / f"{safe_anime}{_META_SUFFIX}"
        try:
            sidecar.write_text(
                json.dumps({"anime": anime, "cover_path": cover_path}),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _read_metadata(self, safe_anime: str) -> dict:
        sidecar = self._dir / f"{safe_anime}{_META_SUFFIX}"
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

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
            safe_anime = m.group(1).strip()
            meta = self._read_metadata(safe_anime)
            entries.append(DownloadEntry(
                anime=str(meta.get("anime") or safe_anime),
                episode_num=int(m.group(2)),
                file_path=str(f),
                file_size=size,
                cover_path=meta.get("cover_path"),
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
