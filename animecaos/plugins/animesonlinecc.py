import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from os import cpu_count

import requests
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from animecaos.core.loader import PluginInterface
from animecaos.core.repository import rep

from .utils import make_driver, validate_player_src

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (animecaos)"}


def _workers(limit: int) -> int:
    return max(1, min(limit, cpu_count() or 1))


class AnimesOnlineCC(PluginInterface):
    languages = ["pt-br"]
    name = "animesonlinecc"

    @staticmethod
    def search_anime(query: str):
        url = "https://animesonlinecc.to/search/" + "+".join(query.split())
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers=HEADERS)
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

        def inspect_season_count(anime_url: str) -> int:
            try:
                details = requests.get(anime_url, timeout=REQUEST_TIMEOUT_SECONDS, headers=HEADERS)
                details.raise_for_status()
                details_soup = BeautifulSoup(details.text, "html.parser")
                return len(details_soup.find_all("div", class_="se-c")) or 1
            except Exception:
                return 1

        with ThreadPoolExecutor(max_workers=_workers(len(titles_urls))) as executor:
            future_to_item = {
                executor.submit(inspect_season_count, anime_url): (title, anime_url)
                for title, anime_url in titles_urls
            }
            for future in as_completed(future_to_item):
                title, anime_url = future_to_item[future]
                season_count = max(1, future.result())
                rep.add_anime(title, anime_url, AnimesOnlineCC.name)
                for season_num in range(2, season_count + 1):
                    rep.add_anime(f"{title} Season {season_num}", anime_url, AnimesOnlineCC.name, season_num)

    @staticmethod
    def search_episodes(anime: str, url: str, season):
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers=HEADERS)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        seasons = soup.find_all("ul", class_="episodios")
        if not seasons:
            return

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
            response = requests.get(url_episode, timeout=REQUEST_TIMEOUT_SECONDS, headers=HEADERS)
            if response.status_code != 200:
                return False
            return "blogger.com/video" not in response.text
        except Exception:
            return False

    @staticmethod
    def search_player_src(url_episode: str) -> str:
        driver = make_driver()
        try:
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

            return validate_player_src(src, AnimesOnlineCC.name)
        finally:
            driver.quit()


def load(languages_dict):
    if any(language in languages_dict for language in AnimesOnlineCC.languages):
        rep.register(AnimesOnlineCC)
