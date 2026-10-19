"""
Integration test: MainWindow._on_discover_loaded() must wire a "spotlights"
list (plural) all the way into the actual SpotlightBanner carousel widget —
this is the seam between the background discover-fetch payload and the UI,
which changed shape (singular "spotlight" dict -> plural "spotlights" list)
when the hero became a carousel.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def window(main_window_factory):
    return main_window_factory()


def test_discover_payload_populates_the_carousel_with_all_spotlights(window):
    payload = {
        "trending": [],
        "seasonal": [],
        "spotlights": [
            {"title": "Anime A", "_rank": 1},
            {"title": "Anime B", "_rank": 2},
            {"title": "Anime C", "_rank": 3},
        ],
    }

    window._on_discover_loaded(payload)

    banner = window._home_view.spotlight
    assert banner.isVisible() is True
    assert len(banner._cards) == 3
    assert banner._dots._count == 3
    assert banner._prev_arrow.isVisible() is True


def test_empty_spotlights_list_hides_the_banner(window):
    window._on_discover_loaded({"trending": [], "seasonal": [], "spotlights": []})

    assert window._home_view.spotlight.isVisible() is False
