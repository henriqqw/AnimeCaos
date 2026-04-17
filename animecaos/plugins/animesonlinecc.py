import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from animecaos.core.loader import PluginInterface
from animecaos.core.repository import rep

from .utils import driver_session, validate_player_src
from .player_cache import cache_player_url, get_cached_player_url

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (animecaos)"}

_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)
_retry = Retry(total=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
_SESSION.mount("https://", HTTPAdapter(max_retries=_retry))
_SESSION.mount("http://", HTTPAdapter(max_retries=_retry))



class AnimesOnlineCC(PluginInterface):
    languages = ["pt-br"]
    name = "animesonlinecc"

    @staticmethod
    def search_anime(query: str):
        url = "https://animesonlinecc.to/search/" + "+".join(query.lower().split())
        response = _SESSION.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        divs = soup.find_all("div", class_="data")

        titles_urls: list[tuple[str, str]] = []
        for div in divs:
            h3 = div.find("h3")
            if not h3:
                continue
            anchor = h3.find("a", href=True)
            if not anchor:
                continue

            title = anchor.get_text(strip=True)
            anime_url = anchor["href"]
            titles_urls.append((title, anime_url))

        log.debug("%s: %d animes encontrados", AnimesOnlineCC.name, len(titles_urls))

        # Season count is detected lazily in search_episodes() to avoid N extra
        # HTTP requests during search — only register the base entry here.
        for title, anime_url in titles_urls:
            rep.add_anime(title, anime_url, AnimesOnlineCC.name)

    @staticmethod
    def search_episodes(anime: str, url: str, season):
        response = _SESSION.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        seasons = soup.find_all("ul", class_="episodios")
        if not seasons:
            return

        # Retroactively register additional seasons now that we have the page.
        # This was deferred from search_anime() to avoid N extra HTTP requests.
        base_title = anime.removesuffix(f" Season {season}") if season and season > 1 else anime
        for season_num in range(2, len(seasons) + 1):
            season_title = f"{base_title} Season {season_num}"
            rep.add_anime(season_title, url, AnimesOnlineCC.name, season_num)

        season_idx = (season - 1) if season is not None else 0
        if season_idx < 0 or season_idx >= len(seasons):
            return

        season_list = seasons[season_idx]
        urls, titles = [], []
        for div in season_list.find_all("div", class_="episodiotitle"):
            anchor = div.find("a", href=True)
            if not anchor:
                continue
            urls.append(anchor["href"])
            titles.append(anchor.get_text(strip=True))

        if not urls:
            return

        rep.add_episode_list(anime, titles, urls, AnimesOnlineCC.name)

    @staticmethod
    def is_episode_playable(url_episode: str) -> bool:
        """Fast HTTP check: look for blogger iframe in raw HTML."""
        try:
            response = _SESSION.get(url_episode, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code != 200:
                return False
            return "blogger.com/video" not in response.text
        except Exception:
            return False

    @staticmethod
    def search_player_src(url_episode: str) -> str:
        cached = get_cached_player_url(AnimesOnlineCC.name, url_episode)
        if cached:
            return cached

        with driver_session(AnimesOnlineCC.name) as driver:
            driver.get(url_episode)
            try:
                iframe = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src]"))
                )
            except TimeoutException as exc:
                raise RuntimeError("Iframe nao encontrado no AnimesOnlineCC.") from exc

            src = iframe.get_property("src") or iframe.get_attribute("src")
            if not src:
                raise RuntimeError("Iframe sem src na pagina de episodio.")

            if "blogger.com/video.g" in src:
                raise RuntimeError("Hospedagem de video nao disponivel para este episodio.")

            result = validate_player_src(src, AnimesOnlineCC.name)
            cache_player_url(AnimesOnlineCC.name, url_episode, result)
            return result


def load(languages_dict):
    if any(language in languages_dict for language in AnimesOnlineCC.languages):
        rep.register(AnimesOnlineCC)
