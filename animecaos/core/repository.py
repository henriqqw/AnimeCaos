import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from os import cpu_count
from fuzzywuzzy import fuzz

from .loader import PluginInterface

log = logging.getLogger(__name__)


def _max_workers() -> int:
    return max(1, cpu_count() or 1)


class Repository:
    """Shared state and orchestration layer for plugins."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self.sources = {}
        self.anime_to_urls = defaultdict(list)
        self.anime_episodes_titles = defaultdict(list)
        self.anime_episodes_urls = defaultdict(list)
        self.norm_titles = {}
        self._initialized = True

    def register(self, plugin: PluginInterface) -> None:
        self.sources[plugin.name] = plugin

    def reset_runtime_data(self) -> None:
        """Clear search and episode caches while keeping loaded plugins."""
        self.anime_to_urls.clear()
        self.anime_episodes_titles.clear()
        self.anime_episodes_urls.clear()
        self.norm_titles.clear()

    def search_anime(self, query: str) -> None:
        if not self.sources:
            return

        _SEARCH_TIMEOUT = 15  # seconds — don't wait forever for slow plugins

        executor = ThreadPoolExecutor(max_workers=min(len(self.sources), _max_workers()))
        future_to_name = {
            executor.submit(plugin.search_anime, query): name
            for name, plugin in self.sources.items()
        }
        try:
            for future in as_completed(future_to_name, timeout=_SEARCH_TIMEOUT):
                name = future_to_name[future]
                try:
                    future.result(timeout=0)
                except Exception as exc:
                    log.warning("Fonte '%s' falhou na busca: %s", name, exc)
        except Exception:
            # Some plugins didn't finish in time — use whatever results we have
            slow = [n for f, n in future_to_name.items() if not f.done()]
            if slow:
                log.warning("Fontes lentas ignoradas: %s", ", ".join(slow))
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _normalize_title(self, title: str) -> str:
        normalized = title.lower()
        table = {
            "clássico": "",
            "classico": "",
            ":": "",
            "part": "season",
            "temporada": "season",
            "(": "",
            ")": "",
            " ": "",
        }
        for key, value in table.items():
            normalized = normalized.replace(key, value)
        return normalized

    def add_anime(self, title: str, url: str, source: str, params=None) -> None:
        """
        This method assumes that different seasons are different anime.
        """
        normalized = self._normalize_title(title)
        self.norm_titles[title] = normalized

        threshold = 95
        for known_title in self.anime_to_urls.keys():
            if fuzz.ratio(normalized, self.norm_titles[known_title]) >= threshold:
                self.anime_to_urls[known_title].append((url, source, params))
                return

        self.anime_to_urls[title].append((url, source, params))

    def get_anime_titles(self) -> list[str]:
        return sorted(self.anime_to_urls.keys())

    def search_episodes(self, anime: str) -> None:
        if anime in self.anime_episodes_titles and self.anime_episodes_titles[anime]:
            return

        urls_and_scrapers = self.anime_to_urls.get(anime, [])
        if not urls_and_scrapers:
            return

        with ThreadPoolExecutor(max_workers=min(len(urls_and_scrapers), _max_workers())) as executor:
            futures = [
                executor.submit(self.sources[source].search_episodes, anime, url, params)
                for url, source, params in urls_and_scrapers
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    log.warning("Fonte falhou na busca de episodios: %s", exc)

    def add_episode_list(self, anime: str, title_list: list[str], url_list: list[str], source: str) -> None:
        if not title_list or not url_list:
            return
        self.anime_episodes_titles[anime].append(title_list)
        self.anime_episodes_urls[anime].append((url_list, source))

    def get_episode_list(self, anime: str) -> list[str]:
        episode_lists = [lst for lst in self.anime_episodes_titles.get(anime, []) if lst]
        if not episode_lists:
            return []
        # Prefer shorter lists to reduce chance of OVA/special mismatch across sources.
        return sorted(episode_lists, key=len)[0]

    def is_playable(self, anime: str) -> bool:
        """Fast check (HTTP only, no Selenium): load episodes and test the first one."""
        try:
            self.search_episodes(anime)
        except Exception:
            return False

        episode_sources = self.anime_episodes_urls.get(anime, [])
        if not episode_sources:
            return False

        candidates = [
            (urls, source) for urls, source in episode_sources if urls
        ]
        if not candidates:
            return False

        # Check sources in parallel — return True as soon as any is playable
        with ThreadPoolExecutor(max_workers=min(len(candidates), _max_workers())) as executor:
            futures = {
                executor.submit(self.sources[source].is_episode_playable, urls[0]): source
                for urls, source in candidates
            }
            for future in as_completed(futures):
                try:
                    if future.result():
                        for f in futures:
                            if f is not future:
                                f.cancel()
                        return True
                except Exception:
                    continue

        return False

    def search_player(self, anime: str, episode_num: int) -> str:
        """
        Returns first playable source url found for the requested episode.
        """
        selected_urls: list[tuple[str, str]] = []
        for urls, source in self.anime_episodes_urls.get(anime, []):
            if len(urls) >= episode_num:
                selected_urls.append((urls[episode_num - 1], source))

        if not selected_urls:
            raise ValueError("Nenhuma fonte possui esse episodio.")

        errors = []
        with ThreadPoolExecutor(max_workers=min(len(selected_urls), _max_workers())) as executor:
            future_to_source = {
                executor.submit(self.sources[source].search_player_src, url): source
                for url, source in selected_urls
            }
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    player_src = future.result()
                    if player_src:
                        from urllib.parse import urlparse
                        host = urlparse(player_src).netloc.lower()
                        if "blogger.com" in host:
                            errors.append(f"{source}: link do blogger bloqueado globalmente")
                            continue
                        for pending in future_to_source:
                            if pending is not future:
                                pending.cancel()
                        return player_src
                    errors.append(f"{source}: sem src de player")
                except Exception as exc:
                    errors.append(f"{source}: {exc}")

        all_blogger = all("blogger" in e.lower() or "hospedagem" in e.lower() for e in errors) if errors else False
        if all_blogger:
            raise RuntimeError(
                "Este anime usa hospedagem de video indisponivel (Blogger). "
                "Tente outro titulo."
            )
        joined_errors = "; ".join(errors) if errors else "sem detalhes"
        raise RuntimeError(f"Falha ao resolver player em todas as fontes ({joined_errors}).")


rep = Repository()


if __name__ == "__main__":
    rep1, rep2 = Repository(), Repository()
    print(rep1 is rep2)
