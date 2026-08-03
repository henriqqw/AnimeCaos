import logging

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from urllib.parse import quote

from animecaos.core.repository import rep
from animecaos.core.loader import PluginInterface
from .driver_pool import make_driver

log = logging.getLogger(__name__)

_PAGE_LOAD_TIMEOUT = 15


class BetterAnime(PluginInterface):
    """Integracao com BetterAnime via Selenium."""

    name = "betteranime"
    languages = ["pt-br"]

    @staticmethod
    def search_anime(query: str) -> None:
        q = quote(query)
        url = f"https://betteranime.net/pesquisa?pesquisa={q}"
        driver = make_driver()
        driver.set_page_load_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            driver.get(url)

            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article a"))
                )
            except TimeoutException:
                return

            cards = driver.find_elements(By.CSS_SELECTOR, "article a")
            for a in cards:
                href = a.get_attribute("href")
                title_elem = a.find_elements(By.CSS_SELECTOR, "h3")
                title = title_elem[0].text.strip() if title_elem else a.get_attribute("title") or a.text.strip()
                if title and href:
                    rep.add_anime(title, href, BetterAnime.name)
        except Exception as e:
            log.debug("%s: search_anime erro: %s", BetterAnime.name, e)
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
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.list-group-item, #episodesList a"))
                )
            except TimeoutException:
                return

            ep_links = []
            title_list = []

            for a in driver.find_elements(By.CSS_SELECTOR, "a.list-group-item, #episodesList a"):
                href = a.get_attribute("href") or ""
                name = a.get_attribute("title") or a.text.strip()
                if href and href not in ep_links:
                    ep_links.append(href)
                    title_list.append(name if name else f"Episódio {len(ep_links)}")

            if ep_links:
                ep_links.reverse()
                title_list.reverse()
                rep.add_episode_list(anime, title_list, ep_links, BetterAnime.name)
        except Exception as e:
            log.debug("%s: search_episodes erro: %s", BetterAnime.name, e)
        finally:
            driver.quit()

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
                    raise RuntimeError("Sem src no BetterAnime.")

            if "blogger.com" in src:
                raise RuntimeError("Blogger não é mais suportado (fonte instavel).")

            return src
        finally:
            driver.quit()


def load(languages_dict):
    # BetterAnime desativado - site fora do ar (betteranime.net DNS error)
    return
