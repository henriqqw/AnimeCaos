from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

MANGA_DL_DIR = Path.home() / "Downloads" / "AnimeCaos" / "Manga"


def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()[:80]


@dataclass
class MangaDownloadEntry:
    manga_title: str
    chapter_label: str
    file_path: str
    file_size: int
    page_count: int

    @property
    def size_str(self) -> str:
        mb = self.file_size / (1024 * 1024)
        return f"{mb:.1f} MB"


class MangaDownloadService:
    def __init__(self, download_dir: Path | None = None) -> None:
        self._dir = download_dir or MANGA_DL_DIR

    def get_dir(self) -> Path:
        return self._dir

    def chapter_path(self, manga_title: str, chapter_label: str) -> Path:
        d = self._dir / _safe(manga_title)
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{_safe(chapter_label)}.cbz"

    def is_downloaded(self, manga_title: str, chapter_label: str) -> bool:
        return self.chapter_path(manga_title, chapter_label).exists()

    def save_chapter(self, manga_title: str, chapter_label: str, pages: list[bytes]) -> str:
        path = self.chapter_path(manga_title, chapter_label)
        tmp = path.with_suffix(".cbz.tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as zf:
            for i, data in enumerate(pages):
                zf.writestr(f"page_{i + 1:03d}.jpg", data)
        tmp.rename(path)
        return str(path)

    def read_pages(self, file_path: str) -> list[bytes]:
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                return [zf.read(n) for n in sorted(zf.namelist())]
        except Exception:
            return []

    def scan(self) -> list[MangaDownloadEntry]:
        if not self._dir.exists():
            return []
        entries: list[MangaDownloadEntry] = []
        for manga_dir in sorted(self._dir.iterdir()):
            if not manga_dir.is_dir():
                continue
            for f in sorted(manga_dir.iterdir()):
                if f.suffix.lower() != ".cbz":
                    continue
                try:
                    size = f.stat().st_size
                    with zipfile.ZipFile(f, "r") as zf:
                        page_count = len(zf.namelist())
                except Exception:
                    size = 0
                    page_count = 0
                entries.append(MangaDownloadEntry(
                    manga_title=manga_dir.name,
                    chapter_label=f.stem,
                    file_path=str(f),
                    file_size=size,
                    page_count=page_count,
                ))
        return entries

    def group_by_manga(self) -> dict[str, list[MangaDownloadEntry]]:
        groups: dict[str, list[MangaDownloadEntry]] = {}
        for e in self.scan():
            groups.setdefault(e.manga_title, []).append(e)
        return groups

    def delete(self, entry: MangaDownloadEntry) -> bool:
        try:
            Path(entry.file_path).unlink(missing_ok=True)
            return True
        except Exception:
            return False
