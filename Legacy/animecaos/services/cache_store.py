"""Persistent, TTL'd, evicting cache for API responses.

Backed by SQLite (stdlib — no server, no new dependency, just a file). It
replaces three ad-hoc JSON caches that all shared the same three defects:
they rewrote the whole file on every single write, they never evicted
anything (growing without bound), and they wrote non-atomically — which is
how partially-written files that render as blank cards got created.

The central idea here is the **two-tier TTL**. Every entry carries both a
soft and a hard expiry:

    fresh          soft_expires_at        hard_expires_at
    |───────────────────|─────────────────────|──────────────>
      serve as-is         serve + revalidate     must refetch
                          in background
                          ("stale")

That split is what lets the app open instantly (paint whatever is cached,
refresh behind the scenes) while still preserving the existing
serve-stale-on-error behaviour: when the network fails or we're rate
limited, a stale entry is far better than an empty screen, so callers can
opt to accept entries past their soft expiry.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from animecaos.core.paths import cache_dir

log = logging.getLogger(__name__)

DB_FILENAME = "api_cache.db"

# Keep the newest N entries by last access; older rows are dropped on
# startup eviction. Sized so a heavy user's whole library fits comfortably
# while the file stays a few MB.
MAX_ENTRIES = 5000

# Sentinel for "never expires" (deterministic data like translations).
NEVER = float("inf")


@dataclass(frozen=True)
class CacheHit:
    """A cache lookup that found something.

    `is_stale` means the entry is past its soft expiry: still usable, but
    the caller should kick off a background refresh. `is_negative` means we
    cached the *absence* of a result (see put(negative=True)) — the caller
    should treat it as "we already know there's nothing here" and NOT
    re-request, which is the whole point of caching misses.
    """

    value: Any
    is_stale: bool
    is_negative: bool
    created_at: float


class CacheStore:
    """Thread-safe SQLite-backed cache.

    Connections are per-thread (sqlite3 objects can't be shared across
    threads), created lazily via threading.local. WAL journaling lets
    readers proceed while a writer holds the DB, which matters because the
    UI thread reads this while background workers write to it.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or (cache_dir() / DB_FILENAME)
        self._local = threading.local()
        self._stats_lock = threading.Lock()
        self._hits = 0
        self._stale_hits = 0
        self._negative_hits = 0
        self._misses = 0
        self._init_schema()

    # ── Connection handling ──────────────────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row
            # WAL: concurrent readers + one writer, instead of a global
            # lock that would stall the UI thread behind a worker's write.
            conn.execute("PRAGMA journal_mode=WAL")
            # NORMAL is the right durability tradeoff for a cache: losing
            # the last few writes on a hard crash just costs a refetch.
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

    def _init_schema(self) -> None:
        conn = self._conn()
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    key             TEXT PRIMARY KEY,
                    namespace       TEXT NOT NULL,
                    payload         TEXT,
                    created_at      REAL NOT NULL,
                    soft_expires_at REAL NOT NULL,
                    hard_expires_at REAL NOT NULL,
                    is_negative     INTEGER NOT NULL DEFAULT 0,
                    hits            INTEGER NOT NULL DEFAULT 0,
                    last_hit_at     REAL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ns_expiry "
                "ON entries(namespace, hard_expires_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_last_hit ON entries(last_hit_at)"
            )

    # ── Core API ─────────────────────────────────────────────────────
    def get(self, key: str, *, allow_stale: bool = True) -> CacheHit | None:
        """Look up `key`.

        Returns None on a miss, or when the entry is past its HARD expiry
        (unusable). Entries past only their soft expiry come back with
        is_stale=True so the caller can serve them immediately and
        revalidate in the background — unless allow_stale=False, which
        forces a refetch (used for explicit user-initiated refreshes).
        """
        now = time.time()
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM entries WHERE key = ?", (key,)
        ).fetchone()

        if row is None:
            self._bump("miss")
            return None

        if now >= row["hard_expires_at"]:
            # Past hard expiry: unusable. Drop it so it stops occupying
            # space and counting toward the LRU cap.
            with conn:
                conn.execute("DELETE FROM entries WHERE key = ?", (key,))
            self._bump("miss")
            return None

        is_stale = now >= row["soft_expires_at"]
        if is_stale and not allow_stale:
            self._bump("miss")
            return None

        with conn:
            conn.execute(
                "UPDATE entries SET hits = hits + 1, last_hit_at = ? WHERE key = ?",
                (now, key),
            )

        is_negative = bool(row["is_negative"])
        self._bump("stale" if is_stale else ("negative" if is_negative else "hit"))

        try:
            value = json.loads(row["payload"]) if row["payload"] is not None else None
        except (ValueError, TypeError):
            # Corrupt payload — treat as a miss rather than propagating junk.
            with conn:
                conn.execute("DELETE FROM entries WHERE key = ?", (key,))
            return None

        return CacheHit(
            value=value,
            is_stale=is_stale,
            is_negative=is_negative,
            created_at=row["created_at"],
        )

    def put(
        self,
        key: str,
        namespace: str,
        value: Any,
        *,
        soft_ttl: float,
        hard_ttl: float,
        negative: bool = False,
    ) -> None:
        """Store `value` under `key`.

        `negative=True` records that a lookup legitimately found nothing
        (e.g. AniList has no match for a scraper's title). Caching those is
        what stops an unmatchable title from costing two requests on every
        single call, forever — the single worst request amplifier in the
        old code.
        """
        now = time.time()
        soft = now + soft_ttl if soft_ttl != NEVER else NEVER
        hard = now + hard_ttl if hard_ttl != NEVER else NEVER
        # SQLite can't store float('inf') in a REAL column portably enough
        # to compare reliably, so clamp "never" to a far-future timestamp.
        soft = min(soft, 4102444800.0)  # 2100-01-01
        hard = min(hard, 4102444800.0)

        try:
            payload = json.dumps(value)
        except (TypeError, ValueError):
            log.warning("cache: value for %s is not JSON-serializable, skipping", key)
            return

        conn = self._conn()
        with conn:
            conn.execute(
                """
                INSERT INTO entries
                    (key, namespace, payload, created_at,
                     soft_expires_at, hard_expires_at, is_negative, hits, last_hit_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                ON CONFLICT(key) DO UPDATE SET
                    namespace       = excluded.namespace,
                    payload         = excluded.payload,
                    created_at      = excluded.created_at,
                    soft_expires_at = excluded.soft_expires_at,
                    hard_expires_at = excluded.hard_expires_at,
                    is_negative     = excluded.is_negative,
                    last_hit_at     = excluded.last_hit_at
                """,
                (key, namespace, payload, now, soft, hard, int(negative), now),
            )

    def delete(self, key: str) -> None:
        conn = self._conn()
        with conn:
            conn.execute("DELETE FROM entries WHERE key = ?", (key,))

    def purge_namespace(self, namespace: str) -> int:
        conn = self._conn()
        with conn:
            cur = conn.execute(
                "DELETE FROM entries WHERE namespace = ?", (namespace,)
            )
        return cur.rowcount

    # ── Maintenance ──────────────────────────────────────────────────
    def evict(self) -> int:
        """Drop hard-expired rows, then LRU-trim to MAX_ENTRIES.

        Called once at startup. The old JSON caches never did this at all,
        so they grew unboundedly for the life of the install.
        """
        now = time.time()
        conn = self._conn()
        removed = 0
        with conn:
            cur = conn.execute(
                "DELETE FROM entries WHERE hard_expires_at <= ?", (now,)
            )
            removed += cur.rowcount

            count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            if count > MAX_ENTRIES:
                cur = conn.execute(
                    """
                    DELETE FROM entries WHERE key IN (
                        SELECT key FROM entries
                        ORDER BY COALESCE(last_hit_at, created_at) ASC
                        LIMIT ?
                    )
                    """,
                    (count - MAX_ENTRIES,),
                )
                removed += cur.rowcount
        if removed:
            log.info("cache: evicted %d entries", removed)
        return removed

    def stats(self) -> dict[str, int]:
        """Hit/miss counters plus on-disk size. Surfaced under
        ANIMECAOS_API_DEBUG so the request-volume win is measurable rather
        than assumed."""
        conn = self._conn()
        total = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        negative = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE is_negative = 1"
        ).fetchone()[0]
        with self._stats_lock:
            return {
                "entries": total,
                "negative_entries": negative,
                "hits": self._hits,
                "stale_hits": self._stale_hits,
                "negative_hits": self._negative_hits,
                "misses": self._misses,
            }

    def _bump(self, kind: str) -> None:
        with self._stats_lock:
            if kind == "hit":
                self._hits += 1
            elif kind == "stale":
                self._stale_hits += 1
            elif kind == "negative":
                self._negative_hits += 1
            else:
                self._misses += 1

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


# ── Namespace TTL policy ─────────────────────────────────────────────
# Soft = when to revalidate in the background. Hard = when the data is
# genuinely unusable. Hard TTLs are deliberately long: a month-old cover
# URL still beats a blank card when the user is offline or rate limited.
_DAY = 86400.0
_HOUR = 3600.0

TTL: dict[str, tuple[float, float]] = {
    # Title -> full media record. Descriptions/episode counts barely change.
    "media": (7 * _DAY, 30 * _DAY),
    # "AniList has no match for this title" — shorter, since AniList may
    # add the entry later, but long enough to kill the repeat-request storm.
    "media:negative": (6 * _HOUR, _DAY),
    "discover:trending": (3 * _HOUR, 7 * _DAY),
    "discover:seasonal": (6 * _HOUR, 30 * _DAY),
    # Title -> anilist/mal id. An immutable mapping once resolved.
    "ids": (30 * _DAY, NEVER),
    # Deterministic: same input text always yields the same translation.
    "translate": (NEVER, NEVER),
    # Matches the previous url_cache.py behaviour exactly.
    "player_url": (4 * _HOUR, 4 * _HOUR),
    # A CDN image URL that failed to download.
    "image:fail": (_HOUR, _DAY),
}


def ttl_for(namespace: str) -> tuple[float, float]:
    """Soft/hard TTL for a namespace, defaulting to a conservative 1h/1d."""
    return TTL.get(namespace, (_HOUR, _DAY))


# ── Process-wide singleton ───────────────────────────────────────────
_store: CacheStore | None = None
_store_lock = threading.Lock()


def get_store() -> CacheStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = CacheStore()
            _store.evict()
            _migrate_legacy_json(_store)
        return _store


def _migrate_legacy_json(store: CacheStore) -> None:
    """One-time import of the two old JSON caches, then delete them.

    Purely opportunistic — if anything goes wrong we just start with a cold
    cache, which costs a refetch and nothing more. Never let a migration
    failure block app startup.
    """
    root = cache_dir()

    discover = root / "discover_cache.json"
    if discover.exists():
        try:
            data = json.loads(discover.read_text("utf-8"))
            cached_at = float(data.get("cached_at") or 0)
            age = time.time() - cached_at
            for section in ("trending", "seasonal"):
                items = data.get(section)
                if not items:
                    continue
                ns = f"discover:{section}"
                soft, hard = ttl_for(ns)
                # Preserve the entry's real age rather than resetting it.
                store.put(
                    f"{ns}:default",
                    ns,
                    items,
                    soft_ttl=max(0.0, soft - age),
                    hard_ttl=max(0.0, hard - age),
                )
            discover.unlink()
            log.info("cache: migrated discover_cache.json")
        except Exception as exc:
            log.debug("cache: discover migration skipped (%s)", exc)

    player = root / "player_urls.json"
    if player.exists():
        try:
            data = json.loads(player.read_text("utf-8"))
            now = time.time()
            for key, entry in data.items():
                expires = float(entry.get("expires") or 0)
                remaining = expires - now
                if remaining <= 0:
                    continue
                url = entry.get("url")
                if not url:
                    continue
                store.put(
                    f"player_url:{key}",
                    "player_url",
                    url,
                    soft_ttl=remaining,
                    hard_ttl=remaining,
                )
            player.unlink()
            log.info("cache: migrated player_urls.json")
        except Exception as exc:
            log.debug("cache: player_url migration skipped (%s)", exc)


def reset_store_for_tests(store: CacheStore | None = None) -> None:
    """Swap the singleton. Tests only."""
    global _store
    with _store_lock:
        _store = store
