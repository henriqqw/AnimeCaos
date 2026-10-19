from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DOWNLOAD_DIR = Path.home() / "Downloads" / "AnimeCaos"
_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".m4v", ".avi", ".ts", ".mov"}
_META_SUFFIX = ".meta.json"
_EPISODE_RE = re.compile(r"^(.+?)\s*-\s*EP(\d+)\.", re.IGNORECASE)


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

    def anime_dir(self, anime: str) -> Path:
        """Per-anime subfolder new downloads and their sidecar live in —
        groups an anime's episodes together instead of leaving everything
        loose in one big folder."""
        return self._dir / sanitize_anime_filename(anime)

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
        target_dir = self.anime_dir(anime)
        target_dir.mkdir(parents=True, exist_ok=True)
        sidecar = target_dir / f"{safe_anime}{_META_SUFFIX}"
        try:
            sidecar.write_text(
                json.dumps({"anime": anime, "cover_path": cover_path}),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _read_metadata(self, safe_anime: str, base_dir: Path) -> dict:
        sidecar = base_dir / f"{safe_anime}{_META_SUFFIX}"
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _scan_dir(self, base_dir: Path) -> list[DownloadEntry]:
        entries: list[DownloadEntry] = []
        if not base_dir.exists():
            return entries
        for f in sorted(base_dir.iterdir()):
            if not f.is_file() or f.suffix.lower() not in _VIDEO_EXTS:
                continue
            m = _EPISODE_RE.match(f.name)
            if not m:
                continue
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            safe_anime = m.group(1).strip()
            meta = self._read_metadata(safe_anime, base_dir)
            entries.append(DownloadEntry(
                anime=str(meta.get("anime") or safe_anime),
                episode_num=int(m.group(2)),
                file_path=str(f),
                file_size=size,
                cover_path=meta.get("cover_path"),
            ))
        return entries

    def scan(self) -> list[DownloadEntry]:
        if not self._dir.exists():
            return []
        # Root-level files: kept for backward compatibility with downloads
        # made before per-anime subfolders existed — migrate_to_subfolders()
        # moves these into subfolders, but scan() must still find them even
        # if migration hasn't run (or a file got skipped, e.g. a name
        # collision) so nothing silently disappears from the Downloads view.
        entries = self._scan_dir(self._dir)
        for sub in sorted(self._dir.iterdir()):
            if sub.is_dir():
                entries += self._scan_dir(sub)
        return sorted(entries, key=lambda e: (e.anime.lower(), e.episode_num))

    def group_by_anime(self) -> dict[str, list[DownloadEntry]]:
        groups: dict[str, list[DownloadEntry]] = {}
        for e in self.scan():
            groups.setdefault(e.anime, []).append(e)
        return groups

    def total_size(self) -> int:
        return sum(e.file_size for e in self.scan())

    def delete(self, entry: DownloadEntry) -> bool:
        path = Path(entry.file_path)
        parent = path.parent
        try:
            path.unlink(missing_ok=True)
        except OSError:
            return False
        if parent != self._dir:
            self._cleanup_if_empty(parent)
        return True

    def _cleanup_if_empty(self, folder: Path) -> None:
        """Removes the anime subfolder (and its now-orphaned sidecar) once
        its last video file is gone — otherwise an empty folder plus a
        dangling .meta.json would linger forever."""
        try:
            remaining = list(folder.iterdir())
        except OSError:
            return
        if any(p.suffix.lower() in _VIDEO_EXTS for p in remaining):
            return
        for p in remaining:
            try:
                p.unlink()
            except OSError:
                pass
        try:
            folder.rmdir()
        except OSError:
            pass

    def migrate_to_subfolders(self) -> int:
        """One-time, idempotent migration of downloads made before per-anime
        subfolders existed: moves loose root-level video files (and their
        sidecars) into anime_dir(anime). Never overwrites an existing file
        at the destination — a name collision just leaves that file where it
        was, so nothing is ever silently lost. Returns the number of video
        files moved (a shared sidecar moving alongside its episodes doesn't
        add to that count)."""
        if not self._dir.exists():
            return 0
        moved = 0
        for f in sorted(self._dir.iterdir()):
            if not f.is_file():
                continue
            if f.name.endswith(_META_SUFFIX):
                safe_anime = f.name[: -len(_META_SUFFIX)]
                self._move_into_anime_dir(f, safe_anime)
                continue
            if f.suffix.lower() not in _VIDEO_EXTS:
                continue
            m = _EPISODE_RE.match(f.name)
            if not m:
                continue
            safe_anime = m.group(1).strip()
            if self._move_into_anime_dir(f, safe_anime):
                moved += 1
        return moved

    def _move_into_anime_dir(self, f: Path, safe_anime: str) -> bool:
        if not safe_anime:
            return False
        target_dir = self._dir / safe_anime
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        target_path = target_dir / f.name
        if target_path.exists():
            return False
        try:
            f.rename(target_path)
            return True
        except OSError:
            return False
