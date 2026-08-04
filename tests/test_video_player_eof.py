"""
TDD: play_video() decides two different things from the same mpv session and
was conflating them under a single "eof" flag:

  1. Did the episode reach its natural end? (used to trigger autoplay to the
     next episode — must be strict: only a real natural end should advance)
  2. Was it watched long enough to count as a real view for AniList sync?
     (intentionally lenient — watching >=30s also counts, even if the user
     then closed the player manually)

The natural-end detection scraped mpv's human-readable exit log for the
literal string "Exiting... (End of file)". Modern mpv (0.29+, i.e. every
build in real-world use today) actually prints "Exiting... (Eof reached)" —
so that check never matched, and the only thing keeping autoplay working at
all was the >=30s time fallback, which also caused it to misfire when a user
watched >=30s and then manually closed the player mid-episode.
"""
from __future__ import annotations

from animecaos.player.video_player import _detect_natural_eof


def test_detects_modern_mpv_eof_message():
    log = "...\n[cplayer] Exiting... (Eof reached)\n"
    assert _detect_natural_eof(log) is True


def test_detects_legacy_mpv_eof_message():
    log = "...\n[cplayer] Exiting... (End of file)\n"
    assert _detect_natural_eof(log) is True


def test_does_not_detect_eof_on_manual_quit():
    log = "...\n[cplayer] Exiting... (Quit)\n"
    assert _detect_natural_eof(log) is False


def test_does_not_detect_eof_on_empty_log():
    assert _detect_natural_eof("") is False
