"""
TDD: AnimeFire's video API returns one entry per available quality
(e.g. [{"src": ..., "label": "360p"}, {"src": ..., "label": "720p"},
{"src": ..., "label": "1080p"}]), lowest quality first. The player was
always picking data[0] (the first entry it found a usable "src" key on) —
since the API always lists 360p first, playback was silently stuck at the
worst quality even when 720p/1080p were available for that episode.

Must always pick the highest resolution available, falling back to
whatever quality actually exists (own worst) when better options aren't
offered for that particular episode.
"""
from __future__ import annotations

from animecaos.plugins.animefire import _pick_best_source, _quality_rank


def test_picks_the_highest_quality_when_multiple_are_available():
    data = [
        {"src": "https://cdn.example/1/360.mp4", "label": "360p"},
        {"src": "https://cdn.example/1/720.mp4", "label": "720p"},
        {"src": "https://cdn.example/1/1080.mp4", "label": "1080p"},
    ]
    assert _pick_best_source(data) == "https://cdn.example/1/1080.mp4"


def test_order_in_the_response_does_not_matter():
    data = [
        {"src": "https://cdn.example/1/720.mp4", "label": "720p"},
        {"src": "https://cdn.example/1/360.mp4", "label": "360p"},
    ]
    assert _pick_best_source(data) == "https://cdn.example/1/720.mp4"


def test_falls_back_to_the_only_quality_available():
    data = [{"src": "https://cdn.example/1/360.mp4", "label": "360p"}]
    assert _pick_best_source(data) == "https://cdn.example/1/360.mp4"


def test_skips_entries_without_a_usable_video_url():
    data = [
        {"src": "https://cdn.example/1/page.html", "label": "1080p"},  # not a direct video file
        {"src": "https://cdn.example/1/360.mp4", "label": "360p"},
    ]
    assert _pick_best_source(data) == "https://cdn.example/1/360.mp4"


def test_returns_none_for_empty_or_all_invalid_data():
    assert _pick_best_source([]) is None
    assert _pick_best_source([{"label": "720p"}]) is None  # no src at all


def test_unlabeled_entry_still_loses_to_a_labeled_one():
    data = [
        {"src": "https://cdn.example/1/unknown.mp4"},
        {"src": "https://cdn.example/1/360.mp4", "label": "360p"},
    ]
    assert _pick_best_source(data) == "https://cdn.example/1/360.mp4"


def test_quality_rank_parses_the_number_out_of_the_label():
    assert _quality_rank("720p") == 720
    assert _quality_rank("1080p") == 1080
    assert _quality_rank(None) == -1
    assert _quality_rank("") == -1
