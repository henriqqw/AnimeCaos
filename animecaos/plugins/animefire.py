import re
import unicodedata

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from animecaos.core.loader import PluginInterface
from animecaos.core.repository import rep

from .utils import build_firefox_options, is_firefox_installed_as_snap


REQUEST_TIMEOUT_SECONDS = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (animecaos)"}


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
        
        print(f"[{AnimeFire.name}] search_anime: {len(cards)} cards encontrados com class='{target_class}'")
        print(f"[{AnimeFire.name}] HTML length: {len(response.text)} chars")
        
        # Mostrar todas as classes div encontradas
        all_divs = soup.find_all("div")
        classes_found = set()
        for div in all_divs[:50]:
            classes = div.get("class", [])
            if classes:
                classes_found.add(" ".join(classes))
        print(f"[{AnimeFire.name}] Classes div encontradas: {list(classes_found)[:20]}")

        titles_urls: list[tuple[str, str]] = []
        for card in cards:
            link_tag = card.find("a", href=True)
            title_tag = card.find("h3", class_="animeTitle")
            if not link_tag or not title_tag:
                continue
            titles_urls.append((title_tag.get_text(strip=True), link_tag["href"]))

        if not titles_urls:
            # Fallback parser for minor HTML layout changes.
            fallback_urls = []
            for div in cards:
                article = getattr(div, "article", None)
                anchor = getattr(article, "a", None) if article else None
                if anchor and anchor.get("href"):
                    fallback_urls.append(anchor["href"])
            titles = [h3.get_text(strip=True) for h3 in soup.find_all("h3", class_="animeTitle")]
            titles_urls = list(zip(titles, fallback_urls))

        if not titles_urls:
            return

        print(f"[{AnimeFire.name}] {len(titles_urls)} animes encontrados")
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
    def search_player_src(url_episode: str) -> str:
        options = build_firefox_options()

        try:
            if is_firefox_installed_as_snap():
                service = FirefoxService(executable_path="/snap/bin/geckodriver")
                driver = webdriver.Firefox(options=options, service=service)
            else:
                driver = webdriver.Firefox(options=options)
        except WebDriverException as exc:
            raise RuntimeError("Firefox/geckodriver nao encontrado.") from exc

        try:
            driver.get(url_episode)

            try:
                video = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.ID, "my-video_html5_api"))
                )
                src = video.get_property("src") or video.get_attribute("src")
                if src:
                    return src
            except TimeoutException:
                pass

            try:
                iframe = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located(
                        (By.XPATH, "/html/body/div[2]/div[2]/div/div[1]/div[1]/div/div/div[2]/div[4]/iframe")
                    )
                )
                src = iframe.get_property("src") or iframe.get_attribute("src")
                if src:
                    if "blogger.com/video.g" in src:
                        raise RuntimeError("Hospedagem de video nao disponivel para este episodio.")
                    return src
            except TimeoutException as exc:
                raise RuntimeError("Iframe/video nao encontrado no AnimeFire.") from exc

            raise RuntimeError("Fonte de video nao encontrada no AnimeFire.")
        finally:
            driver.quit()


def load(languages_dict):
    if any(language in languages_dict for language in AnimeFire.languages):
        rep.register(AnimeFire)
