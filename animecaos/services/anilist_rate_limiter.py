"""
Shared rate limiter for every request AniListService and AniListAuthService
send to graphql.anilist.co.

This app runs on each user's own machine rather than behind a shared
server, so a burst from one screen (e.g. fetching hover-preview synopses
for ~40 discover cards at once) hits AniList's per-IP limit exactly like a
shared server would — and since the limit is per-IP, not per-request-type,
a burst on one screen can 429 an unrelated call sharing that IP budget
(e.g. the login "Viewer" query, which is unrelated to discover cards). A
single shared limiter, paced comfortably under AniList's documented ~90
requests/minute, protects every current and future call site without each
one having to reason about how many others might be firing at once.
"""
from __future__ import annotations

import threading
import time

# One request every 0.8s is ~75/min — comfortably under AniList's ~90/min
# ceiling, leaving headroom for the rest of a rolling window that a prior
# burst may have already spent.
MIN_INTERVAL_SECONDS = 0.8

_lock = threading.Lock()
_last_call_at = 0.0


def wait_for_slot() -> None:
    """Block the calling thread just long enough to keep AniList GraphQL
    requests spaced at least MIN_INTERVAL_SECONDS apart, across every caller
    in the process. Only ever call this from a background thread — every
    current call site already runs off the UI thread (FunctionWorker /
    threading.Thread), since these calls carry their own multi-second
    network timeouts regardless."""
    global _last_call_at
    with _lock:
        now = time.monotonic()
        wait_time = _last_call_at + MIN_INTERVAL_SECONDS - now
        if wait_time > 0:
            time.sleep(wait_time)
        _last_call_at = time.monotonic()
