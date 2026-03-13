"""
Monkey-patch para atualizar seletores CSS e lógica de busca dos plugins.
Resolve problemas de layout desatualizado e bloqueios.
"""

from __future__ import annotations

import sys
import time
from urllib.parse import quote
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.animesvision_selectors import (
    ANIME_SEARCH_SELECTORS,
    EPISODE_SELECTORS,
    IFRAME_SELECTORS,
    get_search_query_url
)


# --- ANIMESVISION PATCH ---

def _patched_animesvision_search_anime(query: str) -> None:
    from animecaos.core.repository import rep
    from animecaos.plugins.animesvision import AnimesVision, _make_driver
    
    url = get_search_query_url(query)
    driver = _make_driver()
    try:
        driver.get(url)
        time.sleep(3)
        selector_str = ", ".join(ANIME_SEARCH_SELECTORS)
        cards = driver.find_elements(By.CSS_SELECTOR, selector_str)
        found_count = 0
        for card in cards:
            title = card.text.strip()
            href = card.get_attribute("href") or ""
            if title and href:
                rep.add_anime(title, href, AnimesVision.name)
                found_count += 1
        
        if found_count == 0:
            print(f"[AnimesVision] 0 resultados! Título: '{driver.title}', HTML fragment: {driver.page_source[:500]}...")
        else:
            print(f"[AnimesVision] Busca: {query} -> {found_count} resultados")
    except Exception as e:
        print(f"[AnimesVision] search_anime erro: {e}")
    finally:
        driver.quit()

def _patched_animesvision_search_episodes(anime: str, anime_url: str, params: object = None) -> None:
    from animecaos.core.repository import rep
    from animecaos.plugins.animesvision import AnimesVision, _make_driver
    driver = _make_driver()
    try:
        driver.get(anime_url)
        time.sleep(3)
        ep_links, title_list = [], []
        selector_str = ", ".join(EPISODE_SELECTORS)
        for a in driver.find_elements(By.CSS_SELECTOR, selector_str):
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
        print(f"[AnimesVision] search_episodes erro: {e}")
    finally:
        driver.quit()

def _patched_animesvision_search_player_src(episode_url: str) -> str:
    from animecaos.plugins.animesvision import AnimesVision, _make_driver, _is_blocked
    driver = _make_driver()
    try:
        driver.get(episode_url)
        iframe = None
        for selector in IFRAME_SELECTORS:
            try:
                iframe = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                if iframe: break
            except: continue
        if not iframe: raise RuntimeError("Player iframe nao encontrado no AnimesVision.")
        src = iframe.get_attribute("src") or ""
        if not src: raise RuntimeError("Iframe de player sem src no AnimesVision.")
        if _is_blocked(src): raise RuntimeError("Fonte bloqueada.")
        return src
    finally:
        driver.quit()


# --- ANIMEFIRE PATCH ---

def _patched_animefire_search_anime(query: str):
    from animecaos.core.repository import rep
    from animecaos.plugins.animefire import AnimeFire, _slugify_query, HEADERS, REQUEST_TIMEOUT_SECONDS
    from app.cloudscraper_patch import patched_get

    slug = _slugify_query(query)
    if not slug: return
    url = f"https://animefire.io/pesquisar/{slug}"
    
    try:
        # Usa o patched_get para bypass do Cloudflare
        response = patched_get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers=HEADERS)
        if response.status_code == 404: return
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        # Seletor genérico para cards de anime no AnimeFire
        cards = soup.select("div.minWDanime, div.divCardUltimosEps, .col-6.col-sm-4")
        
        found = 0
        for card in cards:
            link_tag = card.find("a", href=True)
            title_tag = card.find(["h3", "h2", "span"], class_="animeTitle") or card.find("h3")
            if not link_tag or not title_tag: continue
            rep.add_anime(title_tag.get_text(strip=True), link_tag["href"], AnimeFire.name)
            found += 1
        
        if found == 0:
            soup_text = response.text if hasattr(response, "text") else "N/A"
            print(f"[AnimeFire] 0 resultados! Status: {response.status_code}, HTML fragment: {soup_text[:500]}...")
        else:
            print(f"[AnimeFire] Busca: {query} -> {found} resultados")
    except Exception as e:
        print(f"[AnimeFire] search_anime erro: {e}")


# --- ANIMESONLINECC PATCH ---

def _patched_animesonlinecc_search_anime(query: str):
    from animecaos.core.repository import rep
    from animecaos.plugins.animesonlinecc import AnimesOnlineCC, HEADERS, REQUEST_TIMEOUT_SECONDS, _workers
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.cloudscraper_patch import patched_get

    url = "https://animesonlinecc.to/search/" + "+".join(query.split())
    try:
        # Usa o patched_get para bypass do Cloudflare
        response = patched_get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Seletores para Dooplay theme ou layouts similares
        items = soup.select("div.result-item, div.author-posts article, div.data")
        titles_urls = []
        for item in items:
            h3 = item.find(["h3", "h2", "span"])
            anchor = h3.find("a", href=True) if h3 else item.find("a", href=True)
            if anchor:
                titles_urls.append((anchor.get_text(strip=True), anchor["href"]))

        def inspect_season_count(anime_url: str) -> int:
            try:
                details = patched_get(anime_url, timeout=REQUEST_TIMEOUT_SECONDS, headers=HEADERS)
                details_soup = BeautifulSoup(details.text, "html.parser")
                return len(details_soup.find_all("div", class_="se-c")) or 1
            except: return 1

        if titles_urls:
            with ThreadPoolExecutor(max_workers=_workers(len(titles_urls))) as executor:
                future_to_item = {executor.submit(inspect_season_count, u): (t, u) for t, u in titles_urls}
                for future in as_completed(future_to_item):
                    title, anime_url = future_to_item[future]
                    season_count = max(1, future.result())
                    rep.add_anime(title, anime_url, AnimesOnlineCC.name)
            print(f"[AnimesOnlineCC] Busca: {query} -> {len(titles_urls)} resultados")
        else:
            soup_text = response.text if hasattr(response, "text") else "N/A"
            print(f"[AnimesOnlineCC] 0 resultados! Status: {response.status_code}, HTML fragment: {soup_text[:500]}...")
    except Exception as e:
        print(f"[AnimesOnlineCC] search_anime erro: {e}")


def apply() -> None:
    """Aplica o patch de seletores em todos os plugins."""
    # Patch AnimesVision
    try:
        from animecaos.plugins.animesvision import AnimesVision
        AnimesVision.search_anime = staticmethod(_patched_animesvision_search_anime)
        AnimesVision.search_episodes = staticmethod(_patched_animesvision_search_episodes)
        AnimesVision.search_player_src = staticmethod(_patched_animesvision_search_player_src)
        print("Info: animesvision_selectors_patch aplicado")
    except Exception as e: print(f"Info: falha patch animesvision ({e})")

    # Patch AnimeFire
    try:
        from animecaos.plugins.animefire import AnimeFire
        AnimeFire.search_anime = staticmethod(_patched_animefire_search_anime)
        print("Info: animefire_selectors_patch aplicado")
    except Exception as e: print(f"Info: falha patch animefire ({e})")

    # Patch AnimesOnlineCC
    try:
        from animecaos.plugins.animesonlinecc import AnimesOnlineCC
        AnimesOnlineCC.search_anime = staticmethod(_patched_animesonlinecc_search_anime)
        print("Info: animesonlinecc_selectors_patch aplicado")
    except Exception as e: print(f"Info: falha patch animesonlinecc ({e})")
