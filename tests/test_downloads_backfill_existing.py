"""
TDD: downloads made *before* the metadata-sidecar fix have no sidecar, so
scan() still reports their sanitized on-disk name (e.g. "One Piece Dublado")
with no cover. If the real title ("One Piece (Dublado)") is already known
this session (user browsed to it, so it's in _cover_cache), the Downloads
screen should self-heal on refresh: recognize that sanitizing the known real
title reproduces the on-disk name, adopt it, and write the sidecar so it's
fixed permanently — no re-download needed.
"""
from __future__ import annotations

from animecaos.services.downloads_service import DownloadsService


def test_refresh_backfills_metadata_for_pre_existing_download_with_known_cover(
    main_window_factory, tmp_path
):
    window = main_window_factory()

    cover_file = tmp_path / "cover.jpg"
    cover_file.write_bytes(b"fake-jpeg-bytes")
    window._cover_cache["One Piece (Dublado)"] = str(cover_file)

    window._downloads_service = DownloadsService(download_dir=tmp_path)
    # Pre-existing download from before the sidecar fix — no metadata written.
    (tmp_path / "One Piece Dublado - EP1.mp4").write_bytes(b"0" * 2048)

    window._refresh_downloads_view()

    assert "One Piece (Dublado)" in window._downloads_view._anime_cards
    assert "One Piece Dublado" not in window._downloads_view._anime_cards

    # Self-healed: a second scan (e.g. next time the user opens Downloads)
    # finds the sidecar without needing _cover_cache to still be populated.
    entries = window._downloads_service.scan()
    assert entries[0].anime == "One Piece (Dublado)"
    assert entries[0].cover_path == str(cover_file)
