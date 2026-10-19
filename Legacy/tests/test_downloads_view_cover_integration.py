"""
Integration test: a downloaded episode's cover must show up in the Downloads
screen under the anime's REAL title, even though the video file on disk is
named with a sanitized title (parentheses/colons stripped). Exercises the
full path: DownloadsService.scan() reading the metadata sidecar ->
MainWindow._refresh_downloads_view() building the effective cover map ->
DownloadsView rendering the group card.
"""
from __future__ import annotations

from animecaos.services.downloads_service import DownloadsService


def test_download_group_uses_real_title_and_sidecar_cover(main_window_factory, tmp_path):
    window = main_window_factory()

    cover_file = tmp_path / "cover.jpg"
    cover_file.write_bytes(b"fake-jpeg-bytes")

    window._downloads_service = DownloadsService(download_dir=tmp_path)
    window._downloads_service.write_metadata("One Piece (Dublado)", cover_path=str(cover_file))
    (tmp_path / "One Piece Dublado - EP1.mp4").write_bytes(b"0" * 2048)

    window._refresh_downloads_view()

    assert "One Piece (Dublado)" in window._downloads_view._anime_cards
    assert "One Piece Dublado" not in window._downloads_view._anime_cards
    assert window._cover_cache.get("One Piece (Dublado)") == str(cover_file)
