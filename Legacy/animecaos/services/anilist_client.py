"""Transport layer for graphql.anilist.co.

Three jobs, none of which the old inline `requests.post` calls did:

**Batching.** Every per-title lookup used to be its own POST. AniList counts
*requests*, not fields, so N titles can be collapsed into one request using
GraphQL aliases:

    query ($s0: String, $s1: String) {
      a0: Media(search: $s0, type: ANIME) { ...MediaCore }
      a1: Media(search: $s1, type: ANIME) { ...MediaCore }
    }

That single change turns "30 anime in Minha Lista" from 30-60 requests into
3. `MEDIA_CORE` is deliberately a superset of both old queries, so
`get_title_variants` stops being a separate request entirely — the titles
come back in the same record everything else already needed.

**Single-flight.** Concurrent callers asking for the identical query share
one in-flight request instead of each issuing their own. The old code took
a lock to check the cache, then *released it before* the network call, so
two workers racing on the same uncached title both hit the API.

**Honest error classification.** The old hot paths swallowed everything in
bare `except Exception: pass`, so a 429 was indistinguishable from "no such
anime" — no backoff, no banner, and the app just kept firing into a closed
door. Every response now maps to an explicit ApiStatus that feeds the
limiter and the UI.
"""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import requests
from requests.adapters import HTTPAdapter

from animecaos.services.rate_limiter import Priority, RateLimited, RateLimiter, anilist_limiter

log = logging.getLogger(__name__)

API_URL = "https://graphql.anilist.co"

# Max aliases per request. AniList enforces a query-complexity budget, and
# each alias multiplies the cost of the fragment; 10 keeps us well inside it
# while still cutting request count by an order of magnitude.
BATCH_SIZE = 10

MEDIA_CORE = """
fragment MediaCore on Media {
  id
  idMal
  title { romaji english }
  description
  coverImage { extraLarge large }
  bannerImage
  averageScore
  episodes
  format
  duration
}
"""


class ApiStatus(str, Enum):
    OK = "ok"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    AUTH_ERROR = "auth_error"
    IP_BLOCKED = "ip_blocked"
    SERVER_ERROR = "server_error"
    OFFLINE = "offline"
    NETWORK_ERROR = "network_error"


@dataclass
class ApiResult:
    status: ApiStatus
    data: dict[str, Any] = field(default_factory=dict)
    retry_after: float = 0.0
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status is ApiStatus.OK

    @property
    def is_rate_limited(self) -> bool:
        return self.status is ApiStatus.RATE_LIMITED


class AniListClient:
    def __init__(
        self,
        url: str = API_URL,
        limiter: RateLimiter | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self._url = url
        self._limiter = limiter or anilist_limiter
        self._session = session or self._build_session()
        self._inflight: dict[str, Future] = {}
        self._inflight_lock = threading.Lock()
        self._request_count = 0
        self._count_lock = threading.Lock()

    @staticmethod
    def _build_session() -> requests.Session:
        """Session with a connection pool. The old code used module-level
        requests.post, paying a fresh TCP + TLS handshake on every single
        call — the rest of this codebase (manga_service, the scraper
        plugins) already uses Sessions; AniList was the outlier.

        Deliberately no urllib3 Retry for 429/5xx: retrying a rate-limit
        response is precisely the wrong reflex. Backoff belongs to the
        limiter's circuit breaker, which knows the reset deadline.
        """
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
        session.mount("https://", adapter)
        session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )
        return session

    @property
    def request_count(self) -> int:
        """Total GraphQL requests actually put on the wire. This is the
        number the whole architecture exists to keep small, so it's
        measurable rather than assumed."""
        with self._count_lock:
            return self._request_count

    def reset_request_count(self) -> None:
        with self._count_lock:
            self._request_count = 0

    # ── Core execution ───────────────────────────────────────────────
    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        priority: Priority = Priority.FOREGROUND,
        timeout: float = 15.0,
    ) -> ApiResult:
        """Run a GraphQL query, coalescing identical concurrent calls."""
        variables = variables or {}
        key = _request_key(query, variables)

        with self._inflight_lock:
            existing = self._inflight.get(key)
            if existing is not None:
                future = existing
                leader = False
            else:
                future = Future()
                self._inflight[key] = future
                leader = True

        if not leader:
            # Someone else is already asking this exact question — wait for
            # their answer instead of spending a second request on it.
            try:
                return future.result(timeout=timeout + 10)
            except Exception:
                return ApiResult(ApiStatus.NETWORK_ERROR, message="coalesced request failed")

        try:
            result = self._execute_now(query, variables, priority, timeout)
            future.set_result(result)
            return result
        except BaseException as exc:  # noqa: BLE001 - must always unblock followers
            future.set_exception(exc)
            raise
        finally:
            with self._inflight_lock:
                self._inflight.pop(key, None)

    def _execute_now(
        self,
        query: str,
        variables: dict[str, Any],
        priority: Priority,
        timeout: float,
    ) -> ApiResult:
        try:
            self._limiter.acquire(priority)
        except RateLimited as exc:
            # Refused before touching the network — the caller falls back to
            # cache. This is the path that keeps the app usable while 429'd.
            return ApiResult(ApiStatus.RATE_LIMITED, retry_after=exc.retry_after)

        with self._count_lock:
            self._request_count += 1

        try:
            resp = self._session.post(
                self._url,
                json={"query": query, "variables": variables},
                timeout=timeout,
            )
        except requests.RequestException as exc:
            log.warning("AniList: network error: %s", exc)
            return ApiResult(ApiStatus.NETWORK_ERROR, message=str(exc))

        # Feed the budget back even on failures — the headers are still
        # authoritative, and this is what makes the limiter closed-loop.
        self._limiter.observe_response(resp.headers)
        return self._classify(resp)

    def _classify(self, resp: requests.Response) -> ApiResult:
        status = resp.status_code

        payload: dict[str, Any] = {}
        try:
            payload = resp.json() or {}
        except ValueError:
            payload = {}

        errors = payload.get("errors") or []
        api_msg = ""
        if errors and isinstance(errors, list) and isinstance(errors[0], dict):
            api_msg = str(errors[0].get("message", ""))

        if resp.ok:
            return ApiResult(ApiStatus.OK, data=payload.get("data") or {})

        if status == 404:
            # AniList 404s a Media query that matched nothing. With aliases
            # a partial match still returns usable `data`, so carry it
            # through rather than discarding the titles that DID resolve.
            return ApiResult(
                ApiStatus.NOT_FOUND, data=payload.get("data") or {}, message=api_msg
            )

        if status == 429:
            retry_after = self._limiter.note_rate_limited(resp.headers)
            return ApiResult(ApiStatus.RATE_LIMITED, retry_after=retry_after, message=api_msg)

        if status == 401:
            return ApiResult(ApiStatus.AUTH_ERROR, message=api_msg)

        if status == 403:
            lowered = api_msg.lower()
            if "temporarily disabled" in lowered or "stability" in lowered:
                return ApiResult(ApiStatus.OFFLINE, message=api_msg)
            return ApiResult(ApiStatus.IP_BLOCKED, message=api_msg)

        if status >= 500:
            return ApiResult(ApiStatus.SERVER_ERROR, message=api_msg)

        return ApiResult(ApiStatus.NETWORK_ERROR, message=api_msg or f"HTTP {status}")

    # ── Batched media lookup ─────────────────────────────────────────
    def fetch_media_batch(
        self,
        titles: list[str],
        *,
        priority: Priority = Priority.VISIBLE,
        timeout: float = 15.0,
    ) -> tuple[dict[str, dict | None], ApiResult]:
        """Resolve many titles in as few requests as possible.

        Returns `(results, last_result)` where `results` maps each input
        title to its media record, or to None when AniList genuinely has no
        match. That None is meaningful — callers persist it as a negative
        cache entry so an unmatchable title stops costing a request on
        every single call.

        On a rate-limit refusal, titles that weren't reached are simply
        absent from the mapping (as opposed to present-and-None), so the
        caller can tell "no match" apart from "didn't get to ask".
        """
        results: dict[str, dict | None] = {}
        last = ApiResult(ApiStatus.OK)
        if not titles:
            return results, last

        for chunk_start in range(0, len(titles), BATCH_SIZE):
            chunk = titles[chunk_start : chunk_start + BATCH_SIZE]
            query, variables, aliases = build_batch_query(chunk)
            last = self.execute(
                query, variables, priority=priority, timeout=timeout
            )

            # NOT_FOUND still carries data for the aliases that did resolve.
            if last.status not in (ApiStatus.OK, ApiStatus.NOT_FOUND):
                break

            data = last.data or {}
            for alias, title in aliases.items():
                results[title] = data.get(alias)

        return results, last


def build_batch_query(titles: list[str]) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Build one aliased query for `titles`.

    Returns (query, variables, alias->title). Aliases are positional (a0,
    a1, ...) so the response can be mapped back to the caller's titles
    even though AniList echoes nothing about the search string.
    """
    lines: list[str] = []
    var_defs: list[str] = []
    variables: dict[str, Any] = {}
    aliases: dict[str, str] = {}

    for i, title in enumerate(titles):
        alias = f"a{i}"
        var = f"s{i}"
        var_defs.append(f"${var}: String")
        lines.append(f"  {alias}: Media(search: ${var}, type: ANIME) {{ ...MediaCore }}")
        variables[var] = title
        aliases[alias] = title

    query = "query (" + ", ".join(var_defs) + ") {\n" + "\n".join(lines) + "\n}\n" + MEDIA_CORE
    return query, variables, aliases


def _request_key(query: str, variables: dict[str, Any]) -> str:
    try:
        var_repr = json.dumps(variables, sort_keys=True)
    except (TypeError, ValueError):
        var_repr = repr(sorted(variables.items()))
    return f"{hash(query)}:{var_repr}"
