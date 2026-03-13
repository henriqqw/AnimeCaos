from __future__ import annotations

import os
import re
import sys
import time
import inspect
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Allow importing the existing desktop package from repository root.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from animecaos.services.anime_service import AnimeService  # pylint: disable=wrong-import-position
from animecaos.services.anilist_service import AniListService  # pylint: disable=wrong-import-position
from animecaos.services.history_service import HistoryService  # pylint: disable=wrong-import-position
from animecaos.services.watchlist_service import WatchlistService  # pylint: disable=wrong-import-position
from animecaos.core import loader as anime_loader  # pylint: disable=wrong-import-position

# Força plugins desktop a usarem Firefox ESR + geckodriver da VPS.
from app.selenium_patch import apply as _apply_selenium_patch  # pylint: disable=wrong-import-position
_apply_selenium_patch()

from app.cloudscraper_patch import apply as _apply_cloudscraper_patch  # pylint: disable=wrong-import-position
_apply_cloudscraper_patch()

# Força plugins desktop a usarem seletores atualizados para AnimesVision.
from app.selectors_patch import apply as _apply_selectors_patch  # pylint: disable=wrong-import-position
_apply_selectors_patch()


class HealthResponse(BaseModel):
    status: str


class SearchResponse(BaseModel):
    query: str
    titles: list[str]


class EpisodesResponse(BaseModel):
    anime: str
    episodes: list[str]


class PlayerUrlResponse(BaseModel):
    anime: str
    episode_index: int
    player_url: str


class AnimeMetaResponse(BaseModel):
    query: str
    description: str | None = None
    cover_url: str | None = None


class WatchlistResponse(BaseModel):
    animes: list[str]


class ContinueWatchingItemResponse(BaseModel):
    anime: str
    episode_index: int
    progress: float


class ContinueWatchingResponse(BaseModel):
    items: list[ContinueWatchingItemResponse]


class HomeFeedItemResponse(BaseModel):
    display_title: str
    canonical_title: str


class HomeFeedResponse(BaseModel):
    trending: list[HomeFeedItemResponse]
    recent: list[HomeFeedItemResponse]
    recommended: list[HomeFeedItemResponse]
    generated_at: str
    cache_ttl_seconds: int


app = FastAPI(
    title="AnimeCaos Mobile Backend",
    version="0.1.0",
    description="API gateway for AnimeCaos scraping and stream resolution.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        print(f"[HTTP] {request.method} {request.url.path} -> 500 ({elapsed_ms:.0f} ms) error={exc}")
        raise

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    print(f"[HTTP] {request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.0f} ms)")
    return response

# Mobile defaults include 3 sources to reduce single-source failures on player URL resolution.
DEFAULT_MOBILE_PLUGINS = ("animesonlinecc", "animefire", "animesvision")

DEFAULT_HOME_TRENDING = ("Jujutsu Kaisen", "Kaiju No. 8", "Blue Lock", "Frieren")
DEFAULT_HOME_RECENT = ("Solo Leveling", "Dan Da Dan", "Sakamoto Days", "Chainsaw Man")
DEFAULT_HOME_RECOMMENDED = ("Vinland Saga", "Mushoku Tensei", "Demon Slayer", "Spy x Family")

HOME_FEED_CACHE_TTL_SECONDS = max(60, int(os.getenv("ANIMECAOS_HOME_FEED_CACHE_TTL", "1800")))


def _parse_plugins() -> list[str]:
    raw = os.getenv("ANIMECAOS_PLUGINS", "")
    if not raw.strip():
        return list(DEFAULT_MOBILE_PLUGINS)
    return [plugin.strip() for plugin in raw.split(",") if plugin.strip()]


def _parse_home_titles(env_name: str, defaults: tuple[str, ...]) -> list[str]:
    raw = os.getenv(env_name, "")
    if not raw.strip():
        return list(defaults)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _normalize_title(value: str) -> str:
    normalized = value.strip().lower()
    normalized = normalized.replace("(dublado)", "").replace("(legendado)", "")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _candidate_score(query: str, candidate: str) -> int:
    normalized_query = _normalize_title(query)
    normalized_candidate = _normalize_title(candidate)
    if not normalized_query or not normalized_candidate:
        return -10_000
    if normalized_candidate == normalized_query:
        return 1000
    if normalized_candidate.startswith(normalized_query):
        return 920 - (len(normalized_candidate) - len(normalized_query))
    if normalized_candidate in normalized_query:
        return 780 - (len(normalized_query) - len(normalized_candidate))
    if normalized_query in normalized_candidate:
        return 860 - (len(normalized_candidate) - len(normalized_query))

    query_tokens = normalized_query.split(" ")
    candidate_tokens = normalized_candidate.split(" ")
    overlap = sum(1 for token in query_tokens if token in candidate_tokens)
    return overlap * 120 - abs(len(candidate_tokens) - len(query_tokens)) * 12


def _rank_candidates(query: str, candidates: list[str]) -> list[str]:
    unique_candidates = list(dict.fromkeys(candidate.strip() for candidate in candidates if candidate.strip()))
    return sorted(unique_candidates, key=lambda candidate: _candidate_score(query, candidate), reverse=True)


# Keep debug flag for runtime diagnostics while using 3 source plugins by default.
debug_mode = os.getenv("ANIMECAOS_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
active_plugins = _parse_plugins()
mobile_app_name = os.getenv("ANIMECAOS_MOBILE_APP_NAME", "animecaos-mobile").strip() or "animecaos-mobile"


def _supports_plugins_argument() -> bool:
    return "plugins" in inspect.signature(AnimeService.__init__).parameters


def _configure_legacy_plugins() -> None:
    if _supports_plugins_argument():
        return
    # Legacy AnimeService does not accept plugins; constrain loader defaults here.
    anime_loader.AVAILABLE_PLUGINS = tuple(active_plugins)


def _create_anime_service() -> AnimeService:
    if _supports_plugins_argument():
        return AnimeService(debug=debug_mode, plugins=active_plugins)
    _configure_legacy_plugins()
    return AnimeService(debug=debug_mode)


service = _create_anime_service()
anilist = AniListService(app_name=mobile_app_name)
watchlist_service = WatchlistService(app_name=mobile_app_name)
history_service = HistoryService(app_name=mobile_app_name, legacy_app_name=None)
service_lock = RLock()

HOME_FEED_CATALOG: dict[str, list[str]] = {
    "trending": _parse_home_titles("ANIMECAOS_HOME_TRENDING", DEFAULT_HOME_TRENDING),
    "recent": _parse_home_titles("ANIMECAOS_HOME_RECENT", DEFAULT_HOME_RECENT),
    "recommended": _parse_home_titles("ANIMECAOS_HOME_RECOMMENDED", DEFAULT_HOME_RECOMMENDED),
}

_home_feed_cache: dict[str, object] = {
    "expires_at": 0.0,
    "payload": None,
}

app.mount("/covers", StaticFiles(directory=str(anilist._cache_dir)), name="covers")


def _resolve_playable_home_item(display_title: str) -> HomeFeedItemResponse | None:
    if not display_title.strip():
        return None

    search_candidates = service.search_animes(display_title)
    ranked_candidates = _rank_candidates(display_title, [display_title, *search_candidates])[:8]

    for candidate in ranked_candidates:
        episodes = service.fetch_episode_titles(candidate)
        if not episodes:
            continue
        try:
            # Playability gate for home feed: episode 1 must resolve with current policy.
            service.resolve_player_url(candidate, 0)
            return HomeFeedItemResponse(display_title=display_title, canonical_title=candidate)
        except Exception:
            continue
    return None


def _build_home_feed_payload() -> HomeFeedResponse:
    sections: dict[str, list[HomeFeedItemResponse]] = {
        "trending": [],
        "recent": [],
        "recommended": [],
    }

    for section_name, titles in HOME_FEED_CATALOG.items():
        accepted_items: list[HomeFeedItemResponse] = []
        seen_canonical: set[str] = set()

        for display_title in titles:
            item = _resolve_playable_home_item(display_title)
            if item is None:
                continue
            canonical_key = _normalize_title(item.canonical_title)
            if canonical_key and canonical_key in seen_canonical:
                continue
            if canonical_key:
                seen_canonical.add(canonical_key)
            accepted_items.append(item)

        sections[section_name] = accepted_items

    return HomeFeedResponse(
        trending=sections["trending"],
        recent=sections["recent"],
        recommended=sections["recommended"],
        generated_at=datetime.now(timezone.utc).isoformat(),
        cache_ttl_seconds=HOME_FEED_CACHE_TTL_SECONDS,
    )


def _get_home_feed(refresh: bool) -> HomeFeedResponse:
    now = time.time()
    cached_payload = _home_feed_cache.get("payload")
    expires_at = float(_home_feed_cache.get("expires_at", 0.0))
    if not refresh and isinstance(cached_payload, HomeFeedResponse) and now < expires_at:
        return cached_payload

    payload = _build_home_feed_payload()
    _home_feed_cache["payload"] = payload
    _home_feed_cache["expires_at"] = now + HOME_FEED_CACHE_TTL_SECONDS
    return payload


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/ping")
def ping() -> dict[str, str]:
    """Zero-overhead probe for failover connectivity checks."""
    return {"pong": "ok"}


@app.on_event("startup")
def log_startup_config() -> None:
    print(f"Info: plugins mobile ativos: {', '.join(active_plugins)}")
    if not _supports_plugins_argument():
        print("Info: AnimeService legado detectado; plugins aplicados via loader.AVAILABLE_PLUGINS.")
    print(f"Info: pasta de dados mobile: {mobile_app_name}")


@app.get("/search", response_model=SearchResponse)
def search_anime(q: str = Query(..., min_length=2, description="Anime query")) -> SearchResponse:
    try:
        with service_lock:
            titles = service.search_animes(q)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"search failed: {exc}") from exc

    print(f"[API] /search: query='{q}', {len(titles)} resultados encontrados")
    if titles:
        print(f"[API] Primeiros resultados: {titles[:5]}")
    else:
        print(f"[API] ⚠️  Nenhum resultado retornado!")

    return SearchResponse(query=q, titles=titles)


@app.get("/home-feed", response_model=HomeFeedResponse)
def home_feed(refresh: bool = Query(False, description="Bypass cache and force feed rebuild")) -> HomeFeedResponse:
    try:
        with service_lock:
            return _get_home_feed(refresh=refresh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"home feed failed: {exc}") from exc


@app.get("/anime-meta", response_model=AnimeMetaResponse)
def anime_meta(q: str = Query(..., min_length=1, description="Anime title")) -> AnimeMetaResponse:
    info = anilist.fetch_anime_info(q)

    cover_url = info.get("cover_url")
    if isinstance(cover_url, str) and cover_url:
        resolved_cover_url = cover_url
    else:
        resolved_cover_url = None
        cover_path = info.get("cover_path")
        if isinstance(cover_path, str) and cover_path:
            cover_name = Path(cover_path).name
            if cover_name:
                resolved_cover_url = f"/covers/{cover_name}"

    return AnimeMetaResponse(
        query=q,
        description=info.get("description"),
        cover_url=resolved_cover_url,
    )


@app.get("/episodes", response_model=EpisodesResponse)
def episodes(anime: str = Query(..., min_length=1)) -> EpisodesResponse:
    try:
        with service_lock:
            episode_titles = service.fetch_episode_titles(anime)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"episodes failed: {exc}") from exc

    return EpisodesResponse(anime=anime, episodes=episode_titles)


@app.get("/player-url", response_model=PlayerUrlResponse)
def player_url(
    anime: str = Query(..., min_length=1),
    episode_index: int = Query(..., ge=0),
) -> PlayerUrlResponse:
    try:
        episode_sources: list[tuple[list[str], str]] = []
        with service_lock:
            resolved_url = service.resolve_player_url(anime, episode_index)
            episode_sources = service.get_episode_sources(anime)
        if episode_sources:
            history_service.save_entry(anime, episode_index, episode_sources)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"player url failed: {exc}") from exc

    return PlayerUrlResponse(
        anime=anime,
        episode_index=episode_index,
        player_url=resolved_url,
    )


@app.get("/watchlist", response_model=WatchlistResponse)
def get_watchlist() -> WatchlistResponse:
    try:
        animes = watchlist_service.load_watchlist()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"watchlist failed: {exc}") from exc
    return WatchlistResponse(animes=animes)


@app.post("/watchlist/add", response_model=WatchlistResponse)
def add_watchlist(anime: str = Query(..., min_length=1)) -> WatchlistResponse:
    try:
        watchlist_service.add_anime(anime.strip())
        animes = watchlist_service.load_watchlist()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"watchlist add failed: {exc}") from exc
    return WatchlistResponse(animes=animes)


@app.post("/watchlist/remove", response_model=WatchlistResponse)
def remove_watchlist(anime: str = Query(..., min_length=1)) -> WatchlistResponse:
    try:
        watchlist_service.remove_anime(anime.strip())
        animes = watchlist_service.load_watchlist()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"watchlist remove failed: {exc}") from exc
    return WatchlistResponse(animes=animes)


@app.get("/continue-watching", response_model=ContinueWatchingResponse)
def continue_watching() -> ContinueWatchingResponse:
    try:
        entries = history_service.load_entries()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"continue watching failed: {exc}") from exc

    items: list[ContinueWatchingItemResponse] = []
    for entry in entries:
        total_episodes = max((len(urls) for urls, _ in entry.episode_sources), default=0)
        progress = ((entry.episode_index + 1) / max(1, total_episodes)) if total_episodes > 0 else 0.0
        items.append(
            ContinueWatchingItemResponse(
                anime=entry.anime,
                episode_index=entry.episode_index,
                progress=float(max(0.0, min(1.0, progress))),
            )
        )

    return ContinueWatchingResponse(items=items)
