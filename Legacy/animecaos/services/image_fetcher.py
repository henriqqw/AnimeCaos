"""Parallel downloader for cover/banner art from AniList's CDN.

The CDN (s4.anilist.co) is **not** the rate-limited GraphQL API, so this
deliberately does not touch the rate limiter — that separation was already
correct in the old code and is preserved here. What was wrong was that
covers downloaded *serially, inline*, inside the GraphQL worker:
`_media_to_card` called `_download_cover_url` once per media item, so a
25-item discover section performed 25 sequential 10-second-timeout GETs
before returning anything at all. That is the bulk of the "app takes
forever to open" feeling, and none of it was ever rate-limit related.

Three fixes:

* **Parallel, on its own pool** — 8 workers, unthrottled, so cards can
  render immediately and art streams in behind them.
* **Atomic writes** — download to a temp file, then os.replace. The old
  code wrote straight to the final path, which is exactly how a partial
  download produced the 0-byte/truncated files that render as blank white
  cards. The existing >1KB guard treats the symptom; this removes the
  cause, and keeps the guard as a cheap backstop for files written by
  older versions.
* **Negative caching** — a URL that fails is remembered for an hour.
  Previously a failure was never recorded, so a broken image was
  re-requested on every single call, forever.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

from animecaos.core.paths import cache_dir
from animecaos.services.cache_store import CacheStore, get_store, ttl_for

log = logging.getLogger(__name__)

MAX_WORKERS = 8
MIN_VALID_BYTES = 1024
TIMEOUT = 15.0


class ImageFetcher:
    def __init__(
        self,
        covers_dir: Path | None = None,
        store: CacheStore | None = None,
        *,
        max_workers: int = MAX_WORKERS,
        session: requests.Session | None = None,
    ) -> None:
        self._dir = covers_dir or (cache_dir() / "covers")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._store = store if store is not None else get_store()
        self._session = session or self._build_session(max_workers)
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="cover"
        )
        self._downloads = 0
        self._lock = threading.Lock()

    @staticmethod
    def _build_session(max_workers: int) -> requests.Session:
        session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=max_workers, pool_maxsize=max_workers, max_retries=0
        )
        session.mount("https://", adapter)
        session.headers.update({"User-Agent": "AnimeCaos"})
        return session

    @property
    def download_count(self) -> int:
        with self._lock:
            return self._downloads

    # ── Paths ────────────────────────────────────────────────────────
    def path_for(self, url: str) -> Path:
        """Content-addressed by URL hash, matching the previous naming so
        every already-downloaded cover stays valid across this upgrade."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        ext = url.split(".")[-1] if "." in url[-6:] else "jpg"
        return self._dir / f"{url_hash}.{ext}"

    def cached_path(self, url: str) -> str | None:
        """Local path if we already have a valid file — no network, safe to
        call from the UI thread."""
        if not url:
            return None
        path = self.path_for(url)
        try:
            if path.exists() and path.stat().st_size > MIN_VALID_BYTES:
                return str(path)
        except OSError:
            pass
        return None

    # ── Fetching ─────────────────────────────────────────────────────
    def fetch(self, url: str) -> str | None:
        """Download `url` unless we already have it. Blocking; call from a
        worker thread (or via fetch_many)."""
        if not url:
            return None

        cached = self.cached_path(url)
        if cached:
            return cached

        # Known-bad URL: don't spend a request rediscovering that.
        fail_key = f"image:fail:{url}"
        if self._store.get(fail_key) is not None:
            return None

        path = self.path_for(url)
        # Clear a stale truncated file so the >1KB check can't wedge us
        # into never re-downloading it.
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

        try:
            resp = self._session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            content = resp.content
        except Exception as exc:
            log.debug("cover: download failed for %s (%s)", url, exc)
            self._remember_failure(fail_key)
            return None

        if len(content) <= MIN_VALID_BYTES:
            self._remember_failure(fail_key)
            return None

        # Atomic: write to a sibling temp file, fsync, then rename. A
        # crash mid-download can now only ever leave a .tmp behind, never
        # a half-written cover that renders blank.
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            with open(tmp, "wb") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except OSError as exc:
            log.debug("cover: write failed for %s (%s)", url, exc)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            return None

        with self._lock:
            self._downloads += 1
        return str(path)

    def _remember_failure(self, key: str) -> None:
        soft, hard = ttl_for("image:fail")
        self._store.put(key, "image:fail", True, soft_ttl=soft, hard_ttl=hard)

    def fetch_many(self, urls: list[str]) -> dict[str, str | None]:
        """Download many covers in parallel. This is the call that replaces
        25 sequential GETs on the GraphQL thread with 25 concurrent ones on
        a pool built for it."""
        unique = [u for u in dict.fromkeys(urls) if u]
        if not unique:
            return {}
        results = list(self._pool.map(self.fetch, unique))
        return dict(zip(unique, results))

    def fetch_async(self, url: str, callback) -> None:
        """Fire-and-forget download; `callback(url, path_or_None)` runs on
        the pool thread."""
        if not url:
            return

        def _run() -> None:
            path = self.fetch(url)
            try:
                callback(url, path)
            except Exception:
                log.exception("cover: callback failed for %s", url)

        self._pool.submit(_run)

    def shutdown(self, wait: bool = False) -> None:
        self._pool.shutdown(wait=wait)
