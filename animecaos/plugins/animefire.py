import logging
import re
import unicodedata

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


def _is_video_url(url: str) -> bool:
    """Check if URL looks like a direct video file (not an HTML page)."""
    if not url:
        return False
    lower = url.split("?")[0].lower()
    return lower.endswith((".mp4", ".m3u8", ".webm", ".mkv", ".ts"))


def _slugify_query(query: str) -> str:
    ascii_query = unicodedata.normalize("NFKD", query).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_query).strip("-")
    return slug


class AnimeFire(PluginInterface):
    languages = ["pt-br"]
    name = "animefire"

    @staticmethod
    def search_anime(query: str):
        slug = _slugify_query(query)
        if not slug:
            return

        url = f"https://animefire.io/pesquisar/{slug}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers=HEADERS)
        if response.status_code == 404:
            return
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        target_class = "col-6 col-sm-4 col-md-3 col-lg-2 mb-1 minWDanime divCardUltimosEps"
        cards = soup.find_all("div", class_=target_class)

        titles_urls: list[tuple[str, str]] = []
        for card in cards:
            link_tag = card.find("a", href=True)
            title_tag = card.find("h3", class_="animeTitle")
            if not link_tag or not title_tag:
                continue
            titles_urls.append((title_tag.get_text(strip=True), link_tag["href"]))

        if not titles_urls:
            # Fallback: extract from article > a structure
            for card in cards:
                article = card.find("article")
                anchor = article.find("a", href=True) if article else None
                if anchor and anchor.get("href"):
                    title = anchor.get("title") or anchor.get_text(strip=True)
                    if title:
                        titles_urls.append((title, anchor["href"]))

        if not titles_urls:
            return

        log.debug("%s: %d animes encontrados", AnimeFire.name, len(titles_urls))
        for title, anime_url in titles_urls:
            rep.add_anime(title, anime_url, AnimeFire.name)

    @staticmethod
    def search_episodes(anime: str, url: str, params):
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers=HEADERS)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.find_all("a", class_="lEp epT divNumEp smallbox px-2 mx-1 text-left d-flex")
        episode_links = [link["href"] for link in links if link.get("href")]
        episode_titles = [link.get_text(strip=True) for link in links]
        if not episode_links:
            return

        rep.add_episode_list(anime, episode_titles, episode_links, AnimeFire.name)

    @staticmethod
    def is_episode_playable(url_episode: str) -> bool:
        """Fast HTTP check: hit the animefire video API to see if CDN sources exist."""
        # Episode URL: https://animefire.io/animes/{slug}/{ep}
        # Video API:   https://animefire.io/video/{slug}/{ep}
        try:
            api_url = url_episode.replace("/animes/", "/video/")
            response = requests.get(api_url, timeout=REQUEST_TIMEOUT_SECONDS, headers=HEADERS)
            if response.status_code != 200:
                return False
            data = response.json().get("data", [])
            return len(data) > 0
        except Exception:
            return False

    @staticmethod
    def search_player_src(url_episode: str) -> str:
        driver = make_driver()
        try:
            driver.get(url_episode)

            # 1) Try direct <video> element on the page
            try:
                video = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.ID, "my-video_html5_api"))
                )
                src = video.get_property("src") or video.get_attribute("src")
                if src and _is_video_url(src):
                    return validate_player_src(src, AnimeFire.name)
            except TimeoutException:
                pass

            # 2) Try iframe — navigate inside to extract the real video URL
            try:
                iframe = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src]"))
                )
                iframe_src = iframe.get_property("src") or iframe.get_attribute("src")
                if iframe_src:
                    if "blogger.com/video.g" in iframe_src:
                        raise RuntimeError("Hospedagem de video nao disponivel para este episodio.")

                    # If the iframe src itself is a direct video URL, use it
                    if _is_video_url(iframe_src):
                        return validate_player_src(iframe_src, AnimeFire.name)

                    # Otherwise, navigate inside the iframe and look for <video>
                    driver.switch_to.frame(iframe)
                    try:
                        inner_video = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.TAG_NAME, "video"))
                        )
                        inner_src = (
                            inner_video.get_property("src")
                            or inner_video.get_attribute("src")
                        )
                        if inner_src and _is_video_url(inner_src):
                            return validate_player_src(inner_src, AnimeFire.name)

                        # Check <source> children
                        source = inner_video.find_elements(By.TAG_NAME, "source")
                        for s in source:
                            s_src = s.get_property("src") or s.get_attribute("src")
                            if s_src and _is_video_url(s_src):
                                return validate_player_src(s_src, AnimeFire.name)
                    except TimeoutException:
                        pass
                    finally:
                        driver.switch_to.default_content()

                    # Last resort: return iframe src and let mpv/yt-dlp try
                    return validate_player_src(iframe_src, AnimeFire.name)

            except TimeoutException as exc:
                raise RuntimeError("Iframe/video nao encontrado no AnimeFire.") from exc

            raise RuntimeError("Fonte de video nao encontrada no AnimeFire.")
        finally:
            driver.quit()


def load(languages_dict):
    if any(language in languages_dict for language in AnimeFire.languages):
        rep.register(AnimeFire)
