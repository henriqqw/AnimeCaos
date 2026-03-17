import logging

import requests
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from urllib.parse import quote

from animecaos.core.repository import rep
from animecaos.core.loader import PluginInterface
from .utils import make_driver, validate_player_src

_HEADERS = {"User-Agent": "Mozilla/5.0 (animecaos)"}

log = logging.getLogger(__name__)

_BLOCKED_HOSTS = ("blogger.com/video.g",)
_PAGE_LOAD_TIMEOUT = 15


def _is_blocked(url: str) -> bool:
    return any(host in url for host in _BLOCKED_HOSTS)


class AnimesVision(PluginInterface):
    """Integração com AnimesVision - usa Selenium para bypassar Cloudflare."""

    name = "animesvision"
    languages = ["pt-br"]

    @staticmethod
    def search_anime(query: str) -> None:
        q = quote(query)
        url = f"https://animesvision.biz/search?nome={q}"
        driver = make_driver()
        driver.set_page_load_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            driver.get(url)

            # Wait for actual content to render instead of a blind sleep
            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/animes/']"))
                )
            except TimeoutException:
                log.debug("%s: nenhum resultado carregado para '%s'", AnimesVision.name, query)
                return

            # Broad selector: any link pointing to an anime page
            links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/animes/']")
            seen: set[str] = set()
            for a in links:
                href = a.get_attribute("href") or ""
                title = a.get_attribute("title") or a.text.strip()
                if href and title and href not in seen:
                    seen.add(href)
                    rep.add_anime(title, href, AnimesVision.name)

            log.debug("%s: %d animes encontrados", AnimesVision.name, len(seen))
        except Exception as e:
            log.debug("%s: search_anime erro: %s", AnimesVision.name, e)
        finally:
            driver.quit()

    @staticmethod
    def search_episodes(anime: str, anime_url: str, params: object = None) -> None:
        driver = make_driver()
        driver.set_page_load_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            driver.get(anime_url)

            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/episodio/'], a[href*='/ep/']"))
                )
            except TimeoutException:
                return

            ep_links = []
            title_list = []

            for a in driver.find_elements(By.CSS_SELECTOR, "a[href*='/episodio/'], a[href*='/ep/'], a.ep-item, ul.listsss a"):
                href = a.get_attribute("href") or ""
                name = a.get_attribute("title") or a.text.strip()
                if href and href not in ep_links:
                    ep_links.append(href)
                    title_list.append(name if name else f"Episódio {len(ep_links)}")

            if ep_links:
                ep_links.reverse()
                title_list.reverse()
                rep.add_episode_list(anime, title_list, ep_links, AnimesVision.name)
        except Exception as e:
            log.debug("%s: search_episodes erro: %s", AnimesVision.name, e)
        finally:
            driver.quit()

    @staticmethod
    def is_episode_playable(url_episode: str) -> bool:
        """Fast HTTP check: look for blocked hosts in raw HTML."""
        try:
            response = requests.get(url_episode, timeout=10, headers=_HEADERS)
            if response.status_code != 200:
                return False
            return not any(host in response.text for host in _BLOCKED_HOSTS)
        except Exception:
            return False

    @staticmethod
    def search_player_src(episode_url: str) -> str:
        driver = make_driver()
        driver.set_page_load_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            driver.get(episode_url)
            try:
                iframe = WebDriverWait(driver, 12).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src]"))
                )
            except TimeoutException as exc:
                raise RuntimeError("Player iframe nao encontrado no AnimesVision.") from exc

            src = iframe.get_attribute("src") or ""
            if not src:
                raise RuntimeError("Iframe de player sem src no AnimesVision.")

            if _is_blocked(src):
                raise RuntimeError("Fonte do Blogger nao suportada (link protegido).")

            return validate_player_src(src, AnimesVision.name)
        finally:
            driver.quit()


def load(languages_dict):
    if any(lang in languages_dict for lang in AnimesVision.languages):
        rep.register(AnimesVision)
