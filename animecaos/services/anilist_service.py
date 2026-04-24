from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from threading import RLock

import requests
from bs4 import BeautifulSoup

from animecaos.services.watchlist_service import _watchlist_dir

log = logging.getLogger(__name__)

APP_NAME = "AnimeCaos"


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
                "Limite de 90 req/min atingido. Capas e descoberta voltam automaticamente. "
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


class AniListService:
    """AniList GraphQL API client with persistent disk cache for offline use."""

    def __init__(self, app_name: str = APP_NAME) -> None:
        self._url = "https://graphql.anilist.co"
        self._cache_dir = _watchlist_dir(app_name) / "cache" / "covers"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._disk_cache_file = _watchlist_dir(app_name) / "cache" / "discover_cache.json"
        self._translate_meta = os.getenv("ANIMECAOS_TRANSLATE_META", "1").lower() in {"1", "true", "yes", "on"}
        self._memory_cache: dict[str, dict[str, str | None]] = {}
        self._media_id_cache: dict[str, int] = {}
        self._trending_cache: list[dict] | None = None
        self._seasonal_cache: list[dict] | None = None
        self._cache_stale: bool = False
        self._cache_lock = RLock()
        self._api_status: AniListStatus = AniListStatus.OK
        self._retry_after: int | None = None

        # Load disk cache so discover sections work even when AniList is offline
        self._load_disk_cache()

        self._query_template = """
        query ($search: String) {
          Media (search: $search, type: ANIME) {
            id
            title {
              romaji
              english
            }
            description
            coverImage {
              large
            }
          }
        }
        """

    # ── Disk cache ────────────────────────────────────────────────

    _CACHE_TTL_SECONDS = 4 * 3600  # 4 hours

    def _load_disk_cache(self) -> None:
        try:
            if self._disk_cache_file.exists():
                data = json.loads(self._disk_cache_file.read_text(encoding="utf-8"))
                cached_at = data.get("cached_at", 0)
                age = datetime.now(timezone.utc).timestamp() - cached_at
                self._trending_cache = data.get("trending") or None
                self._seasonal_cache = data.get("seasonal") or None
                self._cache_stale = age > self._CACHE_TTL_SECONDS
                if self._cache_stale:
                    log.debug("Discover cache expirado (%.0fh) — sera atualizado na proxima conexao", age / 3600)
                else:
                    log.debug("Discover cache carregado do disco (%d trending, %d seasonal)",
                              len(self._trending_cache or []), len(self._seasonal_cache or []))
        except Exception as exc:
            log.debug("Falha ao carregar discover cache: %s", exc)

    def _save_disk_cache(self) -> None:
        try:
            data = {
                "cached_at": datetime.now(timezone.utc).timestamp(),
                "trending": self._trending_cache or [],
                "seasonal": self._seasonal_cache or [],
            }
            self._disk_cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            log.debug("Falha ao salvar discover cache: %s", exc)

    # ── Status ────────────────────────────────────────────────────

    @property
    def is_offline(self) -> bool:
        return self._api_status != AniListStatus.OK

    @property
    def api_status(self) -> AniListStatus:
        return self._api_status

    @property
    def retry_after(self) -> int | None:
        return self._retry_after

    def _handle_error_response(self, resp: requests.Response, context: str) -> None:
        status = resp.status_code
        try:
            errors = resp.json().get("errors") or []
            api_msg = errors[0].get("message", "") if errors else ""
        except Exception:
            api_msg = resp.text[:200]

        if status == 401:
            log.error("AniList %s — 401 Auth error: %s", context, api_msg)
            self._api_status = AniListStatus.AUTH_ERROR
        elif status == 403:
            if "temporarily disabled" in api_msg.lower() or "stability" in api_msg.lower():
                log.error("AniList %s — 403 Manutenção: %s", context, api_msg)
                self._api_status = AniListStatus.OFFLINE
            else:
                log.error("AniList %s — 403 Acesso bloqueado: %s", context, api_msg)
                self._api_status = AniListStatus.IP_BLOCKED
        elif status == 429:
            retry = resp.headers.get("Retry-After") or resp.headers.get("X-RateLimit-Reset")
            self._retry_after = int(retry) if retry and retry.isdigit() else 60
            log.warning("AniList %s — 429 Rate limit. Retry-After=%ss", context, self._retry_after)
            self._api_status = AniListStatus.RATE_LIMITED
        elif status >= 500:
            log.error("AniList %s — %d Server error: %s", context, status, api_msg)
            self._api_status = AniListStatus.SERVER_ERROR
        else:
            log.error("AniList %s — HTTP %d: %s", context, status, api_msg)
            self._api_status = AniListStatus.UNKNOWN_ERROR

    # ── Metadata ─────────────────────────────────────────────────

    def fetch_anime_info(self, query: str) -> dict[str, str | None]:
        """Fetch cover + description for a title. Returns cached result if available."""
        if not query:
            return {"description": None, "cover_path": None, "cover_url": None}

        clean_query = (
            query
            .replace("(Dublado)", "")
            .replace("(Legendado)", "")
            .strip()
        )
        if " - " in clean_query:
            clean_query = clean_query.split(" - ")[0].strip()

        cache_key = clean_query.lower()
        with self._cache_lock:
            cached = self._memory_cache.get(cache_key)
            if cached is not None:
                return dict(cached)

        queries_to_try = [clean_query]
        first_word = clean_query.split()[0] if clean_query.split() else ""
        if first_word and first_word.lower() != clean_query.lower() and len(first_word) >= 3:
            queries_to_try.append(first_word)

        media = None
        for search_q in queries_to_try:
            try:
                response = requests.post(
                    self._url,
                    json={"query": self._query_template, "variables": {"search": search_q}},
                    timeout=10,
                )
                response.raise_for_status()
                media = response.json().get("data", {}).get("Media")
                if media:
                    break
            except Exception:
                pass

        if not media:
            return {"description": None, "cover_path": None, "cover_url": None}

        media_id = media.get("id")
        if isinstance(media_id, int):
            with self._cache_lock:
                self._media_id_cache[cache_key] = media_id

        description = media.get("description", "")
        if description:
            description = BeautifulSoup(description, "html.parser").get_text("\n")
            description = "\n".join(line.strip() for line in description.splitlines() if line.strip())
            if self._translate_meta:
                translated = self._translate_to_ptbr(description)
                if translated:
                    description = translated
                # else: keep original — better to show English than nothing

        cover_url = media.get("coverImage", {}).get("large")
        cover_path = None
        if isinstance(cover_url, str):
            cover_path = self._download_cover_url(cover_url)

        result = {
            "description": description,
            "cover_path": cover_path,
            "cover_url": cover_url if isinstance(cover_url, str) else None,
        }
        with self._cache_lock:
            self._memory_cache[cache_key] = result
        return dict(result)

    def get_title_variants(self, query: str) -> list[str]:
        clean = query.replace("(Dublado)", "").replace("(Legendado)", "").strip()
        if not clean:
            return []
        gql = """
        query ($search: String) {
          Media(search: $search, type: ANIME) {
            title { romaji english }
          }
        }
        """
        try:
            resp = requests.post(
                self._url,
                json={"query": gql, "variables": {"search": clean}},
                timeout=8,
            )
            resp.raise_for_status()
            title_obj = (resp.json().get("data", {}).get("Media") or {}).get("title") or {}
            variants: list[str] = []
            for key in ("romaji", "english"):
                v = title_obj.get(key)
                if v and v.strip() and v.strip().lower() != clean.lower():
                    variants.append(v.strip())
            return variants
        except Exception:
            return []

    def get_media_id(self, title: str) -> int | None:
        clean = title.replace("(Dublado)", "").replace("(Legendado)", "").strip().lower()
        with self._cache_lock:
            return self._media_id_cache.get(clean)

    # ── Discover sections ─────────────────────────────────────────

    def fetch_trending(self, per_page: int = 20) -> list[dict]:
        """Return trending anime. Uses disk cache when AniList is offline or cache is fresh."""
        with self._cache_lock:
            if self._trending_cache is not None and not self._cache_stale:
                return list(self._trending_cache)

        query = """
        query ($perPage: Int) {
          Page(perPage: $perPage) {
            media(type: ANIME, sort: TRENDING_DESC, isAdult: false) {
              id
              title { romaji english }
              coverImage { large }
              bannerImage
              averageScore
              episodes
              format
              duration
            }
          }
        }
        """
        try:
            resp = requests.post(
                self._url,
                json={"query": query, "variables": {"perPage": per_page}},
                timeout=15,
            )
            if not resp.ok:
                self._handle_error_response(resp, "fetch_trending")
                with self._cache_lock:
                    return list(self._trending_cache) if self._trending_cache else []
            items = resp.json().get("data", {}).get("Page", {}).get("media") or []
        except requests.RequestException as exc:
            log.error("AniList fetch_trending — erro de conexão: %s", exc)
            self._api_status = AniListStatus.UNKNOWN_ERROR
            with self._cache_lock:
                return list(self._trending_cache) if self._trending_cache else []

        self._api_status = AniListStatus.OK
        self._retry_after = None
        self._cache_stale = False
        result = [self._media_to_card(m) for m in self._dedupe_media(items)]
        with self._cache_lock:
            self._trending_cache = result
        self._save_disk_cache()
        return list(result)

    def fetch_seasonal(self, per_page: int = 20) -> list[dict]:
        """Return seasonal anime. Uses disk cache when AniList is offline or cache is fresh."""
        with self._cache_lock:
            if self._seasonal_cache is not None and not self._cache_stale:
                return list(self._seasonal_cache)

        season, year = self._current_season()
        query = """
        query ($season: MediaSeason, $seasonYear: Int, $perPage: Int) {
          Page(perPage: $perPage) {
            media(type: ANIME, season: $season, seasonYear: $seasonYear,
                  sort: POPULARITY_DESC, isAdult: false) {
              id
              title { romaji english }
              coverImage { large }
              averageScore
              episodes
              status
            }
          }
        }
        """
        try:
            resp = requests.post(
                self._url,
                json={"query": query, "variables": {
                    "season": season, "seasonYear": year, "perPage": per_page,
                }},
                timeout=15,
            )
            if not resp.ok:
                self._handle_error_response(resp, "fetch_seasonal")
                with self._cache_lock:
                    return list(self._seasonal_cache) if self._seasonal_cache else []
            items = resp.json().get("data", {}).get("Page", {}).get("media") or []
        except requests.RequestException as exc:
            log.error("AniList fetch_seasonal — erro de conexão: %s", exc)
            self._api_status = AniListStatus.UNKNOWN_ERROR
            with self._cache_lock:
                return list(self._seasonal_cache) if self._seasonal_cache else []

        self._api_status = AniListStatus.OK
        self._retry_after = None
        self._cache_stale = False
        result = [self._media_to_card(m) for m in self._dedupe_media(items)]
        with self._cache_lock:
            self._seasonal_cache = result
        self._save_disk_cache()
        return list(result)

    def fetch_spotlight_extras(self, card: dict) -> dict:
        """Download banner image and fetch description for the spotlight card."""
        result = dict(card)
        banner_url = card.get("banner_url")
        if banner_url:
            result["banner_path"] = self._download_cover_url(banner_url)

        title = card.get("title", "")
        if title and not result.get("description"):
            try:
                info = self.fetch_anime_info(title)
                result["description"] = info.get("description") or ""
            except Exception:
                pass

        return result

    # ── Internal helpers ──────────────────────────────────────────

    @staticmethod
    def _dedupe_media(items: list[dict]) -> list[dict]:
        """Remove duplicate media entries by id, then by title."""
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
        cover_url = (media.get("coverImage") or {}).get("large")
        cover_path = self._download_cover_url(cover_url) if cover_url else None
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
            "cover_path": cover_path,
            "anilist_id": media.get("id"),
            "badge": badge,
            "banner_url": media.get("bannerImage"),
            "format": media.get("format"),
            "duration": media.get("duration"),
            "score": score,
            "episodes": episodes,
        }

    def _download_cover_url(self, url: str) -> str | None:
        url_hash = hashlib.md5(url.encode()).hexdigest()
        ext = url.split(".")[-1] if "." in url[-6:] else "jpg"
        cover_path = self._cache_dir / f"{url_hash}.{ext}"
        if cover_path.exists():
            return str(cover_path)
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            cover_path.write_bytes(resp.content)
            return str(cover_path)
        except Exception:
            return None

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
        if not text:
            return None
        try:
            from urllib.parse import quote
            # Truncate before encoding to avoid URL length limits
            snippet = text[:600]
            url = (
                "https://translate.googleapis.com/translate_a/single"
                f"?client=gtx&sl=en&tl=pt-BR&dt=t&q={quote(snippet)}"
            )
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, timeout=8, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                translated = "".join(p[0] for p in data[0] if p and p[0])
                return translated.strip() or None
        except Exception:
            pass
        return None
