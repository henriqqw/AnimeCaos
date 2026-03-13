from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.firefox.service import Service as FirefoxService
from urllib.parse import quote
import time

from animecaos.core.paths import get_bin_path
from animecaos.core.repository import rep
from animecaos.core.loader import PluginInterface
from .utils import build_firefox_options, is_firefox_installed_as_snap


_BLOCKED_HOSTS = ("blogger.com/video.g",)


def _is_blocked(url: str) -> bool:
    return any(host in url for host in _BLOCKED_HOSTS)


def _make_driver() -> webdriver.Firefox:
    options = build_firefox_options()
    try:
        if is_firefox_installed_as_snap():
            service = FirefoxService(executable_path="/snap/bin/geckodriver")
            return webdriver.Firefox(options=options, service=service)
        
        # Inject bundled geckodriver if present
        gd_path = get_bin_path("geckodriver")
        if gd_path != "geckodriver":
            service = FirefoxService(executable_path=gd_path)
            return webdriver.Firefox(options=options, service=service)
            
        return webdriver.Firefox(options=options)
    except WebDriverException as exc:
        raise RuntimeError("Firefox/geckodriver nao encontrado.") from exc


class AnimesVision(PluginInterface):
    """Integração com AnimesVision - usa Selenium para bypassar Cloudflare."""

    name = "animesvision"
    languages = ["pt-br"]

    @staticmethod
    def search_anime(query: str) -> None:
        q = quote(query)
        url = f"https://animesvision.biz/search?nome={q}"
        driver = _make_driver()
        try:
            driver.get(url)
            # aguardar carregamento mínimo
            time.sleep(3)
            
            print(f"[{AnimesVision.name}] search_anime: URL={url}")

            # Tentar encontrar cards de resultados
            cards = driver.find_elements(By.CSS_SELECTOR, "div.film-detail h3 a, div.flw-item h2 a, div.item a.name")
            print(f"[{AnimesVision.name}] {len(cards)} cards encontrados com seletores padrao")
            
            # Tentar outros seletores comuns
            other_selectors = [
                "div.row div.col a",
                "div.list-anime a",
                "a.anime-title",
                "div.card-anime a",
                "div.anime-item a",
            ]
            for selector in other_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"[{AnimesVision.name}] Seletor '{selector}': {len(elements)} elementos")
            
            for card in cards:
                title = card.text.strip()
                href = card.get_attribute("href") or ""
                if title and href:
                    rep.add_anime(title, href, AnimesVision.name)
        except Exception as e:
            print(f"[{AnimesVision.name}] search_anime erro: {e}")
        finally:
            driver.quit()

    @staticmethod
    def search_episodes(anime: str, anime_url: str, params: object = None) -> None:
        driver = _make_driver()
        try:
            driver.get(anime_url)
            time.sleep(3)

            ep_links = []
            title_list = []

            # Tentar encontrar links de episódio (formato /episodio/xxx ou /ep/xxx)
            for a in driver.find_elements(By.CSS_SELECTOR, "a[href*='/episodio/'], a[href*='/ep/'], a.ep-item, ul.listsss a"):
                href = a.get_attribute("href") or ""
                name = a.get_attribute("title") or a.text.strip()
                if href and href not in ep_links:
                    ep_links.append(href)
                    title_list.append(name if name else f"Episódio {len(ep_links)}")

            if ep_links:
                # Invertemos para ter ordem cronológica (sites costumam mostrar do mais novo pro mais antigo)
                ep_links.reverse()
                title_list.reverse()
                rep.add_episode_list(anime, title_list, ep_links, AnimesVision.name)
        except Exception as e:
            print(f"[{AnimesVision.name}] search_episodes erro: {e}")
        finally:
            driver.quit()

    @staticmethod
    def search_player_src(episode_url: str) -> str:
        driver = _make_driver()
        try:
            driver.get(episode_url)
            # Aguardar iframe de player aparecer
            try:
                iframe = WebDriverWait(driver, 12).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#playerframe, iframe.player-frame, div.player-frame iframe, iframe"))
                )
            except TimeoutException as exc:
                raise RuntimeError("Player iframe nao encontrado no AnimesVision.") from exc

            src = iframe.get_attribute("src") or ""
            if not src:
                raise RuntimeError("Iframe de player sem src no AnimesVision.")

            if _is_blocked(src):
                raise RuntimeError("Fonte do Blogger nao suportada (link protegido).")

            return src
        finally:
            driver.quit()


def load(languages_dict):
    if any(lang in languages_dict for lang in AnimesVision.languages):
        rep.register(AnimesVision)
