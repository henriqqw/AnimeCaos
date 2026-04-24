from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Sequence

from animecaos.core import loader
from animecaos.core.repository import rep
from animecaos.player.video_player import play_video

log = logging.getLogger(__name__)


class AnimeService:
    """Application service for anime search, episode loading and playback."""

    # rep is a module-level singleton with mutable state — all access must be serialized.
    _rep_lock = threading.Lock()

    def __init__(self, debug: bool = False, plugins: list[str] | None = None) -> None:
        self._debug = debug
        self._plugins_loaded = False
        self._selected_plugins = plugins

    def ensure_plugins_loaded(self) -> None:
        if self._plugins_loaded:
            return

        # Use provided plugins or default to single plugin in debug mode
        if self._selected_plugins is not None:
            selected_plugins = self._selected_plugins
        elif self._debug:
            selected_plugins = ["animesonlinecc"]
        else:
            selected_plugins = None
            
        loader.load_plugins({"pt-br"}, selected_plugins)
        self._plugins_loaded = True

    def search_animes(self, query: str) -> list[str]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Digite um termo de busca.")

        with self._rep_lock:
            self.ensure_plugins_loaded()
            rep.reset_runtime_data()
            rep.search_anime(normalized_query)
            titles = rep.get_anime_titles()

            if not titles:
                return []

            # Validate playability while still holding the lock (rep state must stay intact).
            valid: list[str] = []
            with ThreadPoolExecutor(max_workers=min(len(titles), 8)) as executor:
                future_to_title = {
                    executor.submit(rep.is_playable, t): t for t in titles
                }
                for future in as_completed(future_to_title):
                    title = future_to_title[future]
                    try:
                        if future.result():
                            valid.append(title)
                        else:
                            log.debug("Filtrado (sem player valido): %s", title)
                    except Exception:
                        log.debug("Filtrado (erro na validacao): %s", title)

        return sorted(valid)

    def fetch_episode_titles(self, anime: str) -> list[str]:
        if not anime:
            return []

        self.ensure_plugins_loaded()
        rep.search_episodes(anime)
        episode_titles = rep.get_episode_list(anime)
        if episode_titles:
            return episode_titles

        return self.synthetic_episode_titles(anime)

    def synthetic_episode_titles(self, anime: str) -> list[str]:
        return [f"Episodio {index}" for index in range(1, self.get_episode_count(anime) + 1)]

    def get_episode_count(self, anime: str) -> int:
        episode_sources = rep.anime_episodes_urls.get(anime, [])
        lengths = [len(urls) for urls, _ in episode_sources]
        return max(lengths, default=0)

    def load_history_sources(self, anime: str, episode_sources: Sequence[tuple[list[str], str]]) -> int:
        self.ensure_plugins_loaded()
        rep.anime_episodes_urls[anime] = list(episode_sources)
        return self.get_episode_count(anime)

    def resolve_player_url(self, anime: str, episode_index: int) -> str:
        if episode_index < 0:
            raise ValueError("Indice de episodio invalido.")
        self.ensure_plugins_loaded()
        return rep.search_player(anime, episode_index + 1)

    def play_url(self, url: str) -> dict[str, bool]:
        return play_video(url, self._debug)

    def get_episode_sources(self, anime: str) -> list[tuple[list[str], str]]:
        return list(rep.anime_episodes_urls.get(anime, []))
