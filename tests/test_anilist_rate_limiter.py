"""
TDD: AnimeCaos runs on each user's own machine, so a burst of AniList
requests (e.g. hover-preview synopsis fetches for ~40 discover cards) hits
AniList's per-IP rate limit on its own — and since the limit is per-IP, it
can 429 an unrelated call sharing that budget (this actually happened: the
login "Viewer" query got rate-limited by a burst of discover-card fetches).
wait_for_slot() must keep consecutive calls spaced at least
MIN_INTERVAL_SECONDS apart, shared across every caller in the process.
"""
from __future__ import annotations

import threading
import time

from animecaos.services import anilist_rate_limiter as limiter


def _reset():
    limiter._last_call_at = 0.0


def test_first_call_does_not_wait():
    _reset()
    start = time.monotonic()
    limiter.wait_for_slot()
    assert time.monotonic() - start < 0.05


def test_second_call_right_after_the_first_is_paced_out():
    _reset()
    limiter.wait_for_slot()
    start = time.monotonic()
    limiter.wait_for_slot()
    elapsed = time.monotonic() - start
    assert elapsed >= limiter.MIN_INTERVAL_SECONDS - 0.02


def test_call_after_the_interval_has_already_passed_does_not_wait():
    _reset()
    limiter._last_call_at = time.monotonic() - limiter.MIN_INTERVAL_SECONDS - 1
    start = time.monotonic()
    limiter.wait_for_slot()
    assert time.monotonic() - start < 0.05


def test_concurrent_callers_are_still_paced_one_at_a_time():
    _reset()
    calls: list[float] = []
    call_lock = threading.Lock()

    def worker():
        limiter.wait_for_slot()
        with call_lock:
            calls.append(time.monotonic())

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    calls.sort()
    gaps = [b - a for a, b in zip(calls, calls[1:])]
    assert all(gap >= limiter.MIN_INTERVAL_SECONDS - 0.02 for gap in gaps)
