"""
Monkey-patch para atualizar seletores CSS do AnimesVision em runtime.
Resolve o problema de "nenhum resultado" quando o site muda o layout.
"""

from __future__ import annotations

import sys
import time
from urllib.parse import quote
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.animesvision_selectors import (
    ANIME_SEARCH_SELECTORS,
    EPISODE_SELECTORS,
    IFRAME_SELECTORS,
    get_search_query_url
)


def _patched_animesvision_search_anime(query: str) -> None:
    """Substituto para AnimesVision.search_anime com seletores atualizados."""
    from animecaos.core.repository import rep
    from animecaos.plugins.animesvision import AnimesVision, _make_driver
    
    url = get_search_query_url(query)
    driver = _make_driver()
    try:
        driver.get(url)
        time.sleep(3)

        # Tentar múltiplos seletores
        selector_str = ", ".join(ANIME_SEARCH_SELECTORS)
        cards = driver.find_elements(By.CSS_SELECTOR, selector_str)
        
        found_count = 0
        for card in cards:
            title = card.text.strip()
            href = card.get_attribute("href") or ""
            if title and href:
                rep.add_anime(title, href, AnimesVision.name)
                found_count += 1
        
        print(f"[AnimesVision] Busca: {query} -> {found_count} resultados")
    except Exception as e:
        print(f"[AnimesVision] search_anime erro: {e}")
    finally:
        driver.quit()


def _patched_animesvision_search_episodes(anime: str, anime_url: str, params: object = None) -> None:
    """Substituto para AnimesVision.search_episodes."""
    from animecaos.core.repository import rep
    from animecaos.plugins.animesvision import AnimesVision, _make_driver
    
    driver = _make_driver()
    try:
        driver.get(anime_url)
        time.sleep(3)

        ep_links = []
        title_list = []

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
            print(f"[AnimesVision] Episódios: {anime} -> {len(ep_links)} encontrados")
    except Exception as e:
        print(f"[AnimesVision] search_episodes erro: {e}")
    finally:
        driver.quit()


def _patched_animesvision_search_player_src(episode_url: str) -> str:
    """Substituto para AnimesVision.search_player_src."""
    from animecaos.plugins.animesvision import AnimesVision, _make_driver, _is_blocked
    
    driver = _make_driver()
    try:
        driver.get(episode_url)
        
        # Tentar múltiplos seletores de iframe
        iframe = None
        for selector in IFRAME_SELECTORS:
            try:
                iframe = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if iframe: break
            except:
                continue
        
        if not iframe:
            raise RuntimeError("Player iframe nao encontrado no AnimesVision (tentou todos os seletores).")

        src = iframe.get_attribute("src") or ""
        if not src:
            raise RuntimeError("Iframe de player sem src no AnimesVision.")

        if _is_blocked(src):
            raise RuntimeError("Fonte bloqueada (link protegido).")

        return src
    finally:
        driver.quit()


def apply() -> None:
    """Aplica o patch de seletores no AnimesVision."""
    mod_name = "animecaos.plugins.animesvision"
    mod = sys.modules.get(mod_name)
    if mod is None:
        try:
            import importlib
            mod = importlib.import_module(mod_name)
        except Exception as e:
            print(f"Info: AnimesVision não carregado para patch de seletores ({e})")
            return

    # Patch nos métodos da classe AnimesVision
    from animecaos.plugins.animesvision import AnimesVision
    AnimesVision.search_anime = staticmethod(_patched_animesvision_search_anime)
    AnimesVision.search_episodes = staticmethod(_patched_animesvision_search_episodes)
    AnimesVision.search_player_src = staticmethod(_patched_animesvision_search_player_src)

    print("Info: animesvision_selectors_patch aplicado com sucesso")
