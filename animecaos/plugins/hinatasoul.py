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

_PAGE_LOAD_TIMEOUT = 15


class HinataSoul(PluginInterface):
    """Integracao com Hinata Soul."""

    name = "hinatasoul"
    languages = ["pt-br"]

    @staticmethod
    def search_anime(query: str) -> None:
        q = quote(query)
        url = f"https://hinatasoul.com/busca?busca={q}"
        driver = make_driver()
        driver.set_page_load_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            driver.get(url)

            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.item a, div.post a, a[href*='/animes/']"))
                )
            except TimeoutException:
                log.debug("%s: nenhum resultado carregado para '%s'", HinataSoul.name, query)
                return

            cards = driver.find_elements(By.CSS_SELECTOR, "div.item, div.post")
            for card in cards:
                try:
                    a = card.find_element(By.CSS_SELECTOR, "a")
                    href = a.get_attribute("href")
                    title = a.get_attribute("title") or a.text.strip()
                    if title and href:
                        rep.add_anime(title, href, HinataSoul.name)
                except Exception:
                    continue

            log.debug("%s: busca concluida", HinataSoul.name)
        except Exception as e:
            log.debug("%s: search_anime erro: %s", HinataSoul.name, e)
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
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/episodio'], a.btn-ep"))
                )
            except TimeoutException:
                return

            ep_links = []
            title_list = []

            for a in driver.find_elements(By.CSS_SELECTOR, "a[href*='/episodio'], a.btn-ep"):
                href = a.get_attribute("href") or ""
                name = a.get_attribute("title") or a.text.strip()
                if href and href not in ep_links:
                    ep_links.append(href)
                    title_list.append(name if name else f"Episódio {len(ep_links)}")

            if ep_links:
                ep_links.reverse()
                title_list.reverse()
                rep.add_episode_list(anime, title_list, ep_links, HinataSoul.name)
        except Exception as e:
            log.debug("%s: search_episodes erro: %s", HinataSoul.name, e)
        finally:
            driver.quit()

    @staticmethod
    def is_episode_playable(url_episode: str) -> bool:
        """Fast HTTP check: look for blogger iframe in raw HTML."""
        try:
            response = requests.get(url_episode, timeout=10, headers=_HEADERS)
            if response.status_code != 200:
                return False
            return "blogger.com/video" not in response.text
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
                    EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src], video"))
                )
            except TimeoutException as exc:
                raise RuntimeError("Player nao encontrado.") from exc

            src = iframe.get_attribute("src") or ""
            if not src:
                src_elem = iframe.find_element(By.CSS_SELECTOR, "source")
                src = src_elem.get_attribute("src") if src_elem else ""
                if not src:
                    raise RuntimeError("Sem src no HinataSoul.")

            if "blogger.com" in src:
                raise RuntimeError("Blogger não é mais suportado (fonte instavel).")

            return validate_player_src(src, HinataSoul.name)
        finally:
            driver.quit()


def load(languages_dict):
    if any(lang in languages_dict for lang in HinataSoul.languages):
        rep.register(HinataSoul)
