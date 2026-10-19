from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from enum import Enum

import requests
from bs4 import BeautifulSoup

from animecaos.services.anilist_client import AniListClient, ApiResult, ApiStatus
from animecaos.services.cache_store import CacheStore, get_store, ttl_for
from animecaos.services.image_fetcher import ImageFetcher
from animecaos.services.rate_limiter import Priority, anilist_limiter
from animecaos.services.request_scheduler import RequestScheduler

log = logging.getLogger(__name__)

APP_NAME = "AnimeCaos"

_EMPTY_INFO: dict[str, str | None] = {
    "description": None,
    "cover_path": None,
    "cover_url": None,
    "score": None,
    "episodes": None,
}


class AniListStatus(str, Enum):
    OK = "ok"
    OFFLINE = "offline"
    IP_BLOCKED = "ip_blocked"
    RATE_LIMITED = "rate_limited"
    AUTH_ERROR = "auth_error"
    SERVER_ERROR = "server_error"
    UNKNOWN_ERROR = "unknown_error"

    def ui_title(self) -> str:
        return {
            AniListStatus.OK: "",
            AniListStatus.OFFLINE: "AniList temporariamente offline",
            AniListStatus.IP_BLOCKED: "AniList — acesso bloqueado",
            AniListStatus.RATE_LIMITED: "AniList — limite de requisições atingido",
            AniListStatus.AUTH_ERROR: "AniList — token expirado ou inválido",
            AniListStatus.SERVER_ERROR: "AniList com instabilidade",
            AniListStatus.UNKNOWN_ERROR: "AniList indisponível",
        }[self]

    def ui_description(self) -> str:
        return {
            AniListStatus.OK: "",
            AniListStatus.OFFLINE: (
                "Capas e seções de descoberta indisponíveis. "
                "Pesquisa, episódios e player funcionam normalmente."
            ),
            AniListStatus.IP_BLOCKED: (
                "Muitas requisições foram feitas. Capas e descoberta indisponíveis por enquanto. "
                "Pesquisa, episódios e player funcionam normalmente."
            ),
            AniListStatus.RATE_LIMITED: (
                "Conteúdo em cache continua disponível e a descoberta volta automaticamente. "
                "Pesquisa, episódios e player funcionam normalmente."
            ),
            AniListStatus.AUTH_ERROR: (
                "Token AniList expirado (válido por 1 ano). Reconecte sua conta em Configurações. "
                "Pesquisa, episódios e player funcionam normalmente."
            ),
            AniListStatus.SERVER_ERROR: (
                "Servidores da AniList com instabilidade. Capas e descoberta indisponíveis temporariamente. "
                "Pesquisa, episódios e player funcionam normalmente."
            ),
            AniListStatus.UNKNOWN_ERROR: (
                "Capas e seções de descoberta indisponíveis. "
                "Pesquisa, episódios e player funcionam normalmente."
            ),
        }[self]


_STATUS_MAP = {
    ApiStatus.OK: AniListStatus.OK,
    ApiStatus.NOT_FOUND: AniListStatus.OK,
    ApiStatus.RATE_LIMITED: AniListStatus.RATE_LIMITED,
    ApiStatus.AUTH_ERROR: AniListStatus.AUTH_ERROR,
    ApiStatus.IP_BLOCKED: AniListStatus.IP_BLOCKED,
    ApiStatus.SERVER_ERROR: AniListStatus.SERVER_ERROR,
    ApiStatus.OFFLINE: AniListStatus.OFFLINE,
    ApiStatus.NETWORK_ERROR: AniListStatus.UNKNOWN_ERROR,
}

TRENDING_QUERY = """
query ($perPage: Int) {
  Page(perPage: $perPage) {
    media(type: ANIME, sort: TRENDING_DESC, isAdult: false) {
      id
      title { romaji english }
      coverImage { extraLarge large }
      bannerImage
      averageScore
      episodes
      format
      duration
    }
  }
}
"""

SEASONAL_QUERY = """
query ($season: MediaSeason, $seasonYear: Int, $perPage: Int) {
  Page(perPage: $perPage) {
    media(type: ANIME, season: $season, seasonYear: $seasonYear,
          sort: POPULARITY_DESC, isAdult: false) {
      id
      title { romaji english }
      coverImage { extraLarge large }
      bannerImage
      averageScore
      episodes
      status
    }
  }
}
"""


def normalize_title(title: str) -> str:
    """Cache key for a title. Strips the scraper's dub/sub suffixes so
    "Naruto (Dublado) - Dublado" and "Naruto" share one cache entry — and,
    critically, one request."""
    clean = title.replace("(Dublado)", "").replace("(Legendado)", "").strip()
    if " - " in clean:
        clean = clean.split(" - ")[0].strip()
    return clean.strip().lower()


class AniListService:
    """Facade over the cache / limiter / client / scheduler stack.

    The public API is unchanged from the previous direct-HTTP version so
    MainWindow keeps working, but every method now goes through the
    persistent cache first and the network only when it has to.
    """

    def __init__(
        self,
        app_name: str = APP_NAME,
        *,
        client: AniListClient | None = None,
        store: CacheStore | None = None,
        images: ImageFetcher | None = None,
    ) -> None:
        self._store = store if store is not None else get_store()
        self._client = client or AniListClient()
        self._images = images or ImageFetcher(store=self._store)
        self._scheduler = RequestScheduler(self._client)
        self._limiter = anilist_limiter
        self._translate_meta = os.getenv("ANIMECAOS_TRANSLATE_META", "1").lower() in {
            "1", "true", "yes", "on",
        }
        self._api_status: AniListStatus = AniListStatus.OK
        self._status_lock = threading.Lock()

    # ── Wiring accessors ─────────────────────────────────────────────
    @property
    def client(self) -> AniListClient:
        return self._client

    @property
    def images(self) -> ImageFetcher:
        return self._images

    @property
    def scheduler(self) -> RequestScheduler:
        return self._scheduler

    # ── Status ───────────────────────────────────────────────────────
    @property
    def is_offline(self) -> bool:
        return self.api_status != AniListStatus.OK

    @property
    def api_status(self) -> AniListStatus:
        """Live status. Rate limiting is read straight off the limiter's
        circuit breaker, so the banner clears itself the moment the window
        elapses instead of persisting until the next successful discover
        load (which is what made it feel stuck before)."""
        if self._limiter.is_open:
            return AniListStatus.RATE_LIMITED
        with self._status_lock:
            return self._api_status

    @property
    def retry_after(self) -> int | None:
        remaining = self._limiter.retry_after
        if remaining > 0:
            return int(remaining) + 1
        return None

    def _note(self, result: ApiResult) -> None:
        mapped = _STATUS_MAP.get(result.status, AniListStatus.UNKNOWN_ERROR)
        with self._status_lock:
            self._api_status = mapped

    # ── Metadata ─────────────────────────────────────────────────────
    def fetch_anime_info(
        self, query: str, *, priority: Priority = Priority.FOREGROUND
    ) -> dict[str, str | None]:
        """Cover + description + score for a title.

        Cache-first: a hit costs zero requests, and a *negative* hit (we
        already know AniList has no match) also costs zero — that alone
        removes the biggest request amplifier in the old code, where an
        unmatchable title re-spent two requests on every single call.
        """
        if not query:
            return dict(_EMPTY_INFO)

        key = normalize_title(query)
        if not key:
            return dict(_EMPTY_INFO)

        cached = self._store.get(f"media:{key}")
        if cached is not None:
            if cached.is_negative:
                return dict(_EMPTY_INFO)
            return self._hydrate(cached.value)

        results, result = self._client.fetch_media_batch([key], priority=priority)
        self._note(result)
        media = results.get(key)

        if media is None:
            if key in results:
                # Definitive "AniList has no such anime" — remember it.
                soft, hard = ttl_for("media:negative")
                self._store.put(
                    f"media:{key}", "media", None,
                    soft_ttl=soft, hard_ttl=hard, negative=True,
                )
            return dict(_EMPTY_INFO)

        record = self._store_media(key, media)
        return self._hydrate(record)

    def prefetch_titles(
        self,
        titles: list[str],
        *,
        priority: Priority = Priority.VISIBLE,
        callback=None,
    ) -> list[str]:
        """Warm the cache for many titles in as few requests as possible.

        Returns the subset that was already cached (so callers can render
        those immediately). Everything else is queued on the coalescing
        scheduler, which merges it with whatever else is in flight.
        """
        already: list[str] = []
        for title in titles:
            key = normalize_title(title)
            if not key:
                continue
            if self._store.get(f"media:{key}") is not None:
                already.append(title)
                continue
            self._scheduler.submit_media(
                key,
                lambda k, media, result, _t=title: self._on_prefetched(
                    k, media, result, _t, callback
                ),
                priority=priority,
            )
        return already

    def _on_prefetched(self, key, media, result: ApiResult, title, callback) -> None:
        self._note(result)
        if media is not None:
            self._store_media(key, media)
        elif result.ok or result.status is ApiStatus.NOT_FOUND:
            soft, hard = ttl_for("media:negative")
            self._store.put(
                f"media:{key}", "media", None,
                soft_ttl=soft, hard_ttl=hard, negative=True,
            )
        if callback is not None:
            try:
                callback(title, self.get_cached_info(title))
            except Exception:
                log.exception("prefetch callback failed for %r", title)

    def get_cached_info(self, title: str) -> dict[str, str | None]:
        """Cache-only lookup — never touches the network, safe on the UI
        thread."""
        key = normalize_title(title)
        cached = self._store.get(f"media:{key}") if key else None
        if cached is None or cached.is_negative:
            return dict(_EMPTY_INFO)
        return self._hydrate(cached.value)

    def _store_media(self, key: str, media: dict) -> dict:
        """Normalize a raw AniList media record and persist it."""
        title_obj = media.get("title") or {}
        cover_image = media.get("coverImage") or {}
        cover_url = cover_image.get("extraLarge") or cover_image.get("large")

        description = media.get("description") or ""
        if description:
            description = BeautifulSoup(description, "html.parser").get_text("\n")
            description = "\n".join(
                line.strip() for line in description.splitlines() if line.strip()
            )
            if self._translate_meta:
                description = self._translate_to_ptbr(description) or description

        record = {
            "id": media.get("id"),
            "id_mal": media.get("idMal"),
            "romaji": title_obj.get("romaji"),
            "english": title_obj.get("english"),
            "description": description,
            "cover_url": cover_url if isinstance(cover_url, str) else None,
            "banner_url": media.get("bannerImage"),
            "score": media.get("averageScore"),
            "episodes": media.get("episodes"),
            "format": media.get("format"),
            "duration": media.get("duration"),
        }
        soft, hard = ttl_for("media")
        self._store.put(f"media:{key}", "media", record, soft_ttl=soft, hard_ttl=hard)
        return record

    def _hydrate(self, record: dict | None) -> dict[str, str | None]:
        """Turn a stored record into the dict shape callers expect. The
        cover is resolved from local disk only — downloading is the image
        pipeline's job and must not block a metadata lookup."""
        if not record:
            return dict(_EMPTY_INFO)
        cover_url = record.get("cover_url")
        return {
            "description": record.get("description") or None,
            "cover_path": self._images.cached_path(cover_url) if cover_url else None,
            "cover_url": cover_url,
            "score": record.get("score"),
            "episodes": record.get("episodes"),
        }

    def ensure_cover(self, title: str) -> str | None:
        """Download this title's cover if needed. Blocking — call from a
        worker."""
        key = normalize_title(title)
        cached = self._store.get(f"media:{key}") if key else None
        if cached is None or cached.is_negative or not cached.value:
            return None
        url = cached.value.get("cover_url")
        return self._images.fetch(url) if url else None

    def get_title_variants(self, query: str) -> list[str]:
        """Alternate (romaji/english) titles.

        Costs no request of its own anymore: the batch fragment already
        carries both titles, so this reads whatever `fetch_anime_info`
        cached. Previously this was a separate, entirely uncached query.
        """
        key = normalize_title(query)
        if not key:
            return []
        cached = self._store.get(f"media:{key}")
        if cached is None:
            self.fetch_anime_info(query)
            cached = self._store.get(f"media:{key}")
        if cached is None or cached.is_negative or not cached.value:
            return []
        variants: list[str] = []
        for field in ("romaji", "english"):
            value = cached.value.get(field)
            if value and value.strip() and value.strip().lower() != key:
                variants.append(value.strip())
        return variants

    def get_media_id(self, title: str) -> int | None:
        return self._cached_field(title, "id")

    def get_mal_id(self, title: str) -> int | None:
        return self._cached_field(title, "id_mal")

    def _cached_field(self, title: str, field: str) -> int | None:
        key = normalize_title(title)
        cached = self._store.get(f"media:{key}") if key else None
        if cached is None or cached.is_negative or not cached.value:
            return None
        value = cached.value.get(field)
        return value if isinstance(value, int) else None

    # ── Discover sections ────────────────────────────────────────────
    def fetch_trending(
        self, per_page: int = 20, *, priority: Priority = Priority.VISIBLE
    ) -> list[dict]:
        return self._fetch_section(
            "discover:trending",
            TRENDING_QUERY,
            {"perPage": per_page},
            priority=priority,
        )

    def fetch_seasonal(
        self, per_page: int = 20, *, priority: Priority = Priority.VISIBLE
    ) -> list[dict]:
        season, year = self._current_season()
        return self._fetch_section(
            "discover:seasonal",
            SEASONAL_QUERY,
            {"season": season, "seasonYear": year, "perPage": per_page},
            priority=priority,
        )

    def _fetch_section(
        self, namespace: str, query: str, variables: dict, *, priority: Priority
    ) -> list[dict]:
        """Stale-while-revalidate: fresh cache returns instantly with zero
        requests; stale cache is *still returned* after a refresh attempt,
        so a rate-limited or offline app shows content instead of an empty
        screen. That serve-stale-on-error behaviour existed before and is
        deliberately preserved."""
        cache_key = f"{namespace}:default"
        cached = self._store.get(cache_key)

        if cached is not None and not cached.is_stale:
            return list(cached.value or [])

        result = self._client.execute(query, variables, priority=priority)
        self._note(result)

        if not result.ok:
            if cached is not None:
                log.info("%s: serving stale cache (%s)", namespace, result.status.value)
                return list(cached.value or [])
            return []

        items = ((result.data or {}).get("Page") or {}).get("media") or []
        cards = [self._media_to_card(m) for m in self._dedupe_media(items)]

        soft, hard = ttl_for(namespace)
        self._store.put(cache_key, namespace, cards, soft_ttl=soft, hard_ttl=hard)

        # Persist each card as a media record too, so hovering any of them
        # is already a cache hit and costs nothing.
        for media in self._dedupe_media(items):
            title_obj = media.get("title") or {}
            title = title_obj.get("english") or title_obj.get("romaji") or ""
            key = normalize_title(title)
            if key and self._store.get(f"media:{key}") is None:
                self._store_media(key, media)

        # Covers download in parallel off the API thread.
        urls = [c["cover_url"] for c in cards if c.get("cover_url")]
        if urls:
            self._images.fetch_many(urls)
            for card in cards:
                if card.get("cover_url"):
                    card["cover_path"] = self._images.cached_path(card["cover_url"])
            self._store.put(cache_key, namespace, cards, soft_ttl=soft, hard_ttl=hard)

        return cards

    def fetch_spotlight_extras(self, card: dict) -> dict:
        result = dict(card)
        banner_url = card.get("banner_url")
        if banner_url:
            result["banner_path"] = self._images.fetch(banner_url)

        title = card.get("title", "")
        if title and not result.get("description"):
            try:
                info = self.fetch_anime_info(title, priority=Priority.VISIBLE)
                result["description"] = info.get("description") or ""
            except Exception:
                log.debug("spotlight: description lookup failed for %r", title)
        return result

    # ── Internal helpers ─────────────────────────────────────────────
    @staticmethod
    def _dedupe_media(items: list[dict]) -> list[dict]:
        seen_ids: set[int] = set()
        seen_titles: set[str] = set()
        result: list[dict] = []
        for m in items:
            mid = m.get("id")
            title_obj = m.get("title") or {}
            title = (title_obj.get("english") or title_obj.get("romaji") or "").strip().lower()
            if mid in seen_ids:
                continue
            if title and title in seen_titles:
                continue
            if mid:
                seen_ids.add(mid)
            if title:
                seen_titles.add(title)
            result.append(m)
        return result

    def _media_to_card(self, media: dict) -> dict:
        title_obj = media.get("title") or {}
        title = title_obj.get("english") or title_obj.get("romaji") or ""
        cover_image = media.get("coverImage") or {}
        cover_url = cover_image.get("extraLarge") or cover_image.get("large")
        score = media.get("averageScore")
        episodes = media.get("episodes")
        if score:
            badge = f"★ {score / 10:.1f}"
        elif episodes:
            badge = f"{episodes} eps"
        else:
            badge = ""
        return {
            "title": title,
            "cover_url": cover_url,
            "cover_path": self._images.cached_path(cover_url) if cover_url else None,
            "anilist_id": media.get("id"),
            "badge": badge,
            "banner_url": media.get("bannerImage"),
            "format": media.get("format"),
            "duration": media.get("duration"),
            "score": score,
            "episodes": episodes,
        }

    @staticmethod
    def _current_season() -> tuple[str, int]:
        now = datetime.now()
        month, year = now.month, now.year
        if month <= 3:
            return "WINTER", year
        if month <= 6:
            return "SPRING", year
        if month <= 9:
            return "SUMMER", year
        return "FALL", year

    def _translate_to_ptbr(self, text: str) -> str | None:
        """Translations are deterministic, so they're cached forever — the
        old code re-translated the same synopsis on every launch."""
        if not text:
            return None

        import hashlib

        key = "translate:" + hashlib.md5(text[:600].encode("utf-8")).hexdigest()
        cached = self._store.get(key)
        if cached is not None:
            return cached.value or None

        try:
            from urllib.parse import quote

            snippet = text[:600]
            url = (
                "https://translate.googleapis.com/translate_a/single"
                f"?client=gtx&sl=en&tl=pt-BR&dt=t&q={quote(snippet)}"
            )
            resp = requests.get(
                url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code == 200:
                data = resp.json()
                translated = "".join(p[0] for p in data[0] if p and p[0]).strip()
                if translated:
                    soft, hard = ttl_for("translate")
                    self._store.put(
                        key, "translate", translated, soft_ttl=soft, hard_ttl=hard
                    )
                    return translated
        except Exception:
            log.debug("translate: failed, keeping original text")
        return None

    # ── Diagnostics ──────────────────────────────────────────────────
    def debug_stats(self) -> dict[str, object]:
        return {
            "requests": self._client.request_count,
            "cover_downloads": self._images.download_count,
            "cache": self._store.stats(),
            "limiter": self._limiter.stats(),
        }

    def shutdown(self) -> None:
        self._scheduler.shutdown()
        self._images.shutdown()
