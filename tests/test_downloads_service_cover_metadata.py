"""
TDD: DownloadsService.scan() reconstructed the anime title by regex-parsing
the video filename on disk. But the filename is built from a *sanitized*
version of the title (letters/digits/space/-/_ only — see
main_window._start_download_worker), which strips parentheses, colons,
apostrophes, question marks, etc. So "One Piece (Dublado)" is saved as
"One Piece Dublado - EP1.mp4", and the Downloads screen re-derives the anime
name as "One Piece Dublado" — a string that matches nothing in the app's
cover cache (keyed by the real title "One Piece (Dublado)" everywhere else),
so the cover never shows. Any title with such characters is affected, not
just this one anime.

Fix: persist the real title (and a known-good cover path) in a small JSON
sidecar written next to the downloads at download time, and have scan() read
it back instead of trusting the lossy filename-derived name.
"""
from __future__ import annotations

import json

from animecaos.services.downloads_service import DownloadEntry, DownloadsService


def _touch_video(dir_, name: str, size: int = 1024) -> None:
    path = dir_ / name
    path.write_bytes(b"0" * size)


def test_scan_falls_back_to_filename_when_no_metadata_sidecar(tmp_path):
    _touch_video(tmp_path, "Naruto - EP1.mp4")
    svc = DownloadsService(download_dir=tmp_path)

    entries = svc.scan()

    assert len(entries) == 1
    assert entries[0].anime == "Naruto"
    assert entries[0].cover_path is None


def test_scan_uses_the_real_title_from_the_metadata_sidecar(tmp_path):
    _touch_video(tmp_path, "One Piece Dublado - EP1.mp4")
    cover_file = tmp_path / "cover.jpg"
    cover_file.write_bytes(b"fake-jpeg-bytes")
    sidecar = tmp_path / "One Piece Dublado.meta.json"
    sidecar.write_text(
        json.dumps({"anime": "One Piece (Dublado)", "cover_path": str(cover_file)}),
        encoding="utf-8",
    )

    svc = DownloadsService(download_dir=tmp_path)
    entries = svc.scan()

    assert len(entries) == 1
    assert entries[0].anime == "One Piece (Dublado)"
    assert entries[0].cover_path == str(cover_file)


def test_group_by_anime_groups_under_the_real_title(tmp_path):
    _touch_video(tmp_path, "One Piece Dublado - EP1.mp4")
    _touch_video(tmp_path, "One Piece Dublado - EP2.mp4")
    sidecar = tmp_path / "One Piece Dublado.meta.json"
    sidecar.write_text(json.dumps({"anime": "One Piece (Dublado)"}), encoding="utf-8")

    svc = DownloadsService(download_dir=tmp_path)
    groups = svc.group_by_anime()

    assert list(groups.keys()) == ["One Piece (Dublado)"]
    assert len(groups["One Piece (Dublado)"]) == 2


def test_write_cover_metadata_then_scan_round_trip(tmp_path):
    svc = DownloadsService(download_dir=tmp_path)
    svc.write_metadata("One Piece (Dublado)", cover_path="/covers/onepiece.jpg")
    _touch_video(tmp_path, "One Piece Dublado - EP1.mp4")

    entries = svc.scan()

    assert entries[0].anime == "One Piece (Dublado)"
    assert entries[0].cover_path == "/covers/onepiece.jpg"


def test_malformed_sidecar_does_not_crash_scan(tmp_path):
    _touch_video(tmp_path, "Naruto - EP1.mp4")
    (tmp_path / "Naruto.meta.json").write_text("{not valid json", encoding="utf-8")

    svc = DownloadsService(download_dir=tmp_path)
    entries = svc.scan()

    assert len(entries) == 1
    assert entries[0].anime == "Naruto"
    assert entries[0].cover_path is None
