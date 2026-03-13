from concurrent.futures import ThreadPoolExecutor, as_completed
from os import cpu_count

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
        
        print(f"[{AnimesOnlineCC.name}] search_anime: {len(divs)} divs encontradas com class='data'")
        print(f"[{AnimesOnlineCC.name}] HTML length: {len(response.text)} chars")

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
            
        print(f"[{AnimesOnlineCC.name}] {len(titles_urls)} animes encontrados")

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
            iframe = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located(
                    (By.XPATH, "/html/body/div[1]/div[2]/div[2]/div[2]/div[1]/div[1]/div[1]/iframe")
                )
            )
            src = iframe.get_property("src") or iframe.get_attribute("src")
            if not src:
                raise RuntimeError("Iframe sem src na pagina de episodio.")

            if "blogger.com/video.g" in src:
                raise RuntimeError("Hospedagem de video nao disponivel para este episodio.")

            return src
        except TimeoutException as exc:
            raise RuntimeError("Iframe nao encontrado no AnimesOnlineCC.") from exc
        finally:
            driver.quit()


def load(languages_dict):
    if any(language in languages_dict for language in AnimesOnlineCC.languages):
        rep.register(AnimesOnlineCC)
