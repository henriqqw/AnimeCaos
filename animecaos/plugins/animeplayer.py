import base64
import logging
import re
import time
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from animecaos.core.loader import PluginInterface
from animecaos.core.repository import rep

from .utils import driver_session, make_driver

log = logging.getLogger(__name__)


def _build_proxy_url(data_src: str) -> str | None:
    """Extract the blogger token from data-src and build a direct proxy URL."""
    parsed = urlparse(data_src)
    qs = parse_qs(parsed.query)
    token_list = qs.get("token", [])
    if not token_list:
        return None

    token = token_list[0]
    # Pad base64
    padding = 4 - len(token) % 4
    if padding != 4:
        token += "=" * padding

    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except Exception:
        return None

    if "blogger.com" not in decoded:
        return None

    # Build the proxy URL that serves the actual video
    base = f"{parsed.scheme}://{parsed.netloc}"
    proxy_path = parsed.path.replace("player.php", "proxy.php")
    return f"{base}{proxy_path}?src={decoded}&itag=22"


class AnimePlayer(PluginInterface):
    languages = ["pt-br"]
    name = "animeplayer"

    @staticmethod
    def search_anime(query: str):
        driver = make_driver()
        try:
            driver.get(f"https://animeplayer.com.br/?s={query}")
            time.sleep(3)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            articles = soup.find_all("article")
            if not articles:
                return

            titles_urls: list[tuple[str, str]] = []
            for art in articles:
                title_el = art.select_one(".details .title a")
                if not title_el or not title_el.get("href"):
                    continue
                title = title_el.get_text(strip=True)
                url = title_el["href"]
                if title and "/animes/" in url:
                    titles_urls.append((title, url))

            if not titles_urls:
                return

            log.debug("%s: %d animes encontrados", AnimePlayer.name, len(titles_urls))
            for title, anime_url in titles_urls:
                rep.add_anime(title, anime_url, AnimePlayer.name)
        finally:
            driver.quit()

    @staticmethod
    def search_episodes(anime: str, url: str, params):
        driver = make_driver()
        try:
            driver.get(url)
            time.sleep(3)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            episodes_li = soup.select(".episodios li")
            if not episodes_li:
                return

            episode_titles: list[str] = []
            episode_links: list[str] = []
            for li in episodes_li:
                a = li.select_one("a[href]")
                title_el = li.select_one(".episodiotitle p, .episodiotitle a")
                if not a or not a.get("href"):
                    continue
                ep_title = title_el.get_text(strip=True) if title_el else ""
                episode_titles.append(ep_title)
                episode_links.append(a["href"])

            episode_titles.reverse()
            episode_links.reverse()

            if not episode_links:
                return

            log.debug("%s: %d episodios encontrados para '%s'", AnimePlayer.name, len(episode_links), anime)
            rep.add_episode_list(anime, episode_titles, episode_links, AnimePlayer.name)
        finally:
            driver.quit()

    @staticmethod
    def search_player_src(url_episode: str) -> str:
        with driver_session(AnimePlayer.name) as driver:
            driver.get(url_episode)
            time.sleep(4)

            soup = BeautifulSoup(driver.page_source, "html.parser")

            placeholder = soup.select_one(".player-placeholder[data-src]")
            if not placeholder or not placeholder.get("data-src"):
                raise RuntimeError("Player nao encontrado no AnimePlayer.")

            data_src = placeholder["data-src"]

            proxy_url = _build_proxy_url(data_src)
            if proxy_url:
                raise RuntimeError(
                    "Hospedagem de video protegida por Cloudflare (animeplayer/blogger)."
                )

            return data_src


def load(languages_dict):
    if any(language in languages_dict for language in AnimePlayer.languages):
        rep.register(AnimePlayer)
