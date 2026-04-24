from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from enum import Enum
from threading import RLock

import requests
from bs4 import BeautifulSoup

from animecaos.services.watchlist_service import _watchlist_dir

log = logging.getLogger(__name__)

APP_NAME = "AnimeCaos"


class AniListStatus(str, Enum):
    OK = "ok"
    OFFLINE = "offline"             # 403 manutenção confirmada pela mensagem
    IP_BLOCKED = "ip_blocked"       # 403 genérico / IP bloqueado
    RATE_LIMITED = "rate_limited"   # 429 — inclui retry_after em segundos
    AUTH_ERROR = "auth_error"       # 401 — token inválido ou expirado
    SERVER_ERROR = "server_error"   # 5xx
    UNKNOWN_ERROR = "unknown_error"

    # Mensagens amigáveis exibidas na UI
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
    """Service to fetch anime metadata (covers, synopsis) from AniList GraphQL API."""

    def __init__(self, app_name: str = APP_NAME) -> None:
        self._url = "https://graphql.anilist.co"
        self._cache_dir = _watchlist_dir(app_name) / "cache" / "covers"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._translate_meta = os.getenv("ANIMECAOS_TRANSLATE_META", "1").lower() in {"1", "true", "yes", "on"}
        self._memory_cache: dict[str, dict[str, str | None]] = {}
        self._media_id_cache: dict[str, int] = {}
        self._trending_cache: list[dict] | None = None
        self._seasonal_cache: list[dict] | None = None
        self._cache_lock = RLock()
        self._api_status: AniListStatus = AniListStatus.OK
        self._retry_after: int | None = None  # segundos restantes após 429

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
        """Parse error responses and set status + log accordingly."""
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
            reset_ts = resp.headers.get("X-RateLimit-Reset", "?")
            log.warning(
                "AniList %s — 429 Rate limit (90 req/min). Retry-After=%ss, Reset=%s",
                context, self._retry_after, reset_ts,
            )
            self._api_status = AniListStatus.RATE_LIMITED

        elif status >= 500:
            log.error("AniList %s — %d Server error: %s", context, status, api_msg)
            self._api_status = AniListStatus.SERVER_ERROR

        else:
            log.error("AniList %s — HTTP %d: %s", context, status, api_msg)
            self._api_status = AniListStatus.UNKNOWN_ERROR

    def fetch_anime_info(self, query: str) -> dict[str, str | None]:
        """Fetches metadata for a given anime title."""
        if not query:
            return {"description": None, "cover_path": None, "cover_url": None}

        # Sanitize: remove dub/sub markers and trailing subtitles after " - "
        clean_query = (
            query
            .replace("(Dublado)", "")
            .replace("(Legendado)", "")
            .strip()
        )
        # Strip season subtitle: "Re:Zero kara ... - Hyouketsu no Kizuna" → "Re:Zero kara ..."
        if " - " in clean_query:
            clean_query = clean_query.split(" - ")[0].strip()

        cache_key = clean_query.lower()

        with self._cache_lock:
            cached = self._memory_cache.get(cache_key)
            if cached is not None:
                return dict(cached)

        # Try up to two queries: full clean title, then first-word-only fallback
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
                description = translated if translated else None

        cover_url = media.get("coverImage", {}).get("large")
        cover_path = None

        if isinstance(cover_url, str):
            url_hash = hashlib.md5(cover_url.encode()).hexdigest()
            ext = cover_url.split(".")[-1] if "." in cover_url[-6:] else "jpg"
            cover_path = self._cache_dir / f"{url_hash}.{ext}"

            if not cover_path.exists():
                try:
                    img_resp = requests.get(cover_url, timeout=10)
                    img_resp.raise_for_status()
                    cover_path.write_bytes(img_resp.content)
                except Exception:
                    cover_path = None

        result = {
            "description": description,
            "cover_path": str(cover_path) if cover_path else None,
            "cover_url": cover_url if isinstance(cover_url, str) else None,
        }
        with self._cache_lock:
            self._memory_cache[cache_key] = result
        return dict(result)

    def get_title_variants(self, query: str) -> list[str]:
        """Query AniList for a title and return romaji + english alternatives."""
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

    def fetch_trending(self, per_page: int = 20) -> list[dict]:
        with self._cache_lock:
            if self._trending_cache is not None:
                return list(self._trending_cache)

        query = """
        query ($perPage: Int) {
          Page(perPage: $perPage) {
            media(type: ANIME, sort: TRENDING_DESC, isAdult: false) {
              id
              title { romaji english }
              coverImage { large }
              averageScore
              episodes
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
                return []
            items = resp.json().get("data", {}).get("Page", {}).get("media") or []
        except requests.RequestException as exc:
            log.error("AniList fetch_trending — erro de conexão: %s", exc)
            self._api_status = AniListStatus.UNKNOWN_ERROR
            return []

        self._api_status = AniListStatus.OK
        self._retry_after = None
        result = [self._media_to_card(m) for m in items]
        with self._cache_lock:
            self._trending_cache = result
        return list(result)

    def fetch_seasonal(self, per_page: int = 20) -> list[dict]:
        with self._cache_lock:
            if self._seasonal_cache is not None:
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
                return []
            items = resp.json().get("data", {}).get("Page", {}).get("media") or []
        except requests.RequestException as exc:
            log.error("AniList fetch_seasonal — erro de conexão: %s", exc)
            self._api_status = AniListStatus.UNKNOWN_ERROR
            return []

        self._api_status = AniListStatus.OK
        self._retry_after = None
        result = [self._media_to_card(m) for m in items]
        with self._cache_lock:
            self._seasonal_cache = result
        return list(result)

    def _media_to_card(self, media: dict) -> dict:
        title_obj = media.get("title") or {}
        title = title_obj.get("english") or title_obj.get("romaji") or ""
        cover_url = (media.get("coverImage") or {}).get("large")
        cover_path = self._download_cover_url(cover_url) if cover_url else None
        score = media.get("averageScore")
        episodes = media.get("episodes")
        if score:
            badge = f"\u2605 {score / 10:.1f}"
        elif episodes:
            badge = f"{episodes} eps"
        else:
            badge = ""
        return {
            "title": title,
            "cover_path": cover_path,
            "anilist_id": media.get("id"),
            "badge": badge,
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
        """Translates the given text to Portuguese (pt-br) using the free Google Translate API endpoint."""
        if not text:
            return None
        try:
            from urllib.parse import quote
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=pt&dt=t&q={quote(text)}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                translated = "".join(sentence[0] for sentence in data[0] if sentence[0])
                return translated.strip() or None
        except Exception:
            pass
        return None
