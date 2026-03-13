"""
Monkey-patch para forçar os plugins desktop a usarem cloudscraper ou Selenium.
Aplicado no startup do mobile backend para bypass do Cloudflare.

Estratégia:
1. Tenta cloudscraper primeiro (mais rápido)
2. Se falhar (403), usa Selenium como fallback (mais lento mas funciona)
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

import cloudscraper
import requests

# ---------------------------------------------------------------------------
# Scraper global reutilizável
# ---------------------------------------------------------------------------
_scraper = None


def _get_scraper() -> cloudscraper.CloudScraper:
    """Cria ou retorna scraper singleton."""
    global _scraper
    if _scraper is None:
        _scraper = cloudscraper.create_scraper(
            browser={"browser": "firefox", "platform": "windows", "mobile": False},
            delay=10,
        )
    return _scraper


def _get_with_selenium(url: str, headers: dict | None = None) -> requests.Response:
    """Fallback: usa Selenium para buscar URL quando cloudscraper falha."""
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.options import Options
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    print(f"[Selenium] Fallback para: {url}")
    
    options = Options()
    options.add_argument("--headless")
    options.binary_location = "/usr/bin/firefox-esr"
    
    # Stealth: Tentar parecer menos com um bot
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
    options.set_preference("general.useragent.override", user_agent)
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    
    driver = None
    try:
        from selenium.webdriver.firefox.service import Service
        service = Service("/usr/local/bin/geckodriver")
        driver = webdriver.Firefox(options=options, service=service)
        driver.set_page_load_timeout(30)
        driver.get(url)
        
        print(f"[Selenium] Aguardando bypass do Cloudflare (Título atual: '{driver.title}')...")
        
        # Esperar até 45 segundos pelo bypass
        wait = WebDriverWait(driver, 45)
        
        # 1. Esperar título mudar de "Just a Moment" ou "Please Wait"
        def _check_title(d):
            cf_titles = ["Just a Moment", "Cloudflare", "Attention Required", "Please Wait", "Wait a moment"]
            return not any(t in d.title for t in cf_titles)
            
        wait.until(_check_title)
        
        # 2. Esperar o body aparecer e não conter "Enable JavaScript" (comum no refresh do CF)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # 3. Pequeno delay extra para garantir renderização de JS
        import time
        time.sleep(5)
        
        # Pegar HTML da página
        html = driver.page_source
        
        # Criar response fake compatível com requests
        from requests.models import Response
        response = Response()
        response.status_code = 200
        response._content = html.encode("utf-8")
        response.headers["Content-Type"] = "text/html"
        response.url = driver.current_url
        
        print(f"[Selenium] Sucesso: {url} (Título: '{driver.title}', Length: {len(html)})")
        return response
        
    except TimeoutException:
        title = driver.title if driver else "N/A"
        print(f"[Selenium] Timeout no bypass do Cloudflare: {url} (Título: '{title}')")
        
        # Log de diagnóstico: mostra o que foi carregado
        if driver:
             html = driver.page_source
             print(f"[Selenium] HTML fragment: {html[:500]}...")
             
             from requests.models import Response
             response = Response()
             response.status_code = 403
             response._content = html.encode("utf-8")
             response.url = driver.current_url
             return response
        raise
    except Exception as e:
        print(f"[Selenium] Erro crítico no fallback: {url} - {e}")
        raise
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def patched_get(url, **kwargs):
    """
    Substituto drop-in para requests.get().
    Estratégia: cloudscraper -> Selenium fallback
    """
    scraper = _get_scraper()
    
    # Extrair parâmetros
    timeout = kwargs.pop("timeout", None)
    original_headers = kwargs.pop("headers", None)
    
    # Tentar cloudscraper primeiro
    print(f"[cloudscraper] Tentando: {url}")
    try:
        response = scraper.get(url, headers=original_headers, **kwargs)
        print(f"[cloudscraper] Status: {url} -> {response.status_code}")
        
        # Se 403, tentar Selenium
        if response.status_code == 403:
            print(f"[cloudscraper] 403 - Usando Selenium fallback...")
            return _get_with_selenium(url, original_headers)
        
        return response
        
    except Exception as e:
        print(f"[cloudscraper] Erro: {url} - {e}")
        print(f"[Selenium] Fallback ativado...")
        return _get_with_selenium(url, original_headers)


def _patched_head(url, **kwargs):
    """Substituto para requests.head()."""
    scraper = _get_scraper()
    headers = kwargs.pop("headers", None)
    try:
        return scraper.head(url, headers=headers, **kwargs)
    except:
        # Fallback para requests normal
        return requests.head(url, headers=headers, **kwargs)


def _patched_post(url, **kwargs):
    """Substituto para requests.post()."""
    scraper = _get_scraper()
    headers = kwargs.pop("headers", None)
    return scraper.post(url, headers=headers, **kwargs)


# ---------------------------------------------------------------------------
# Módulos de plugins
# ---------------------------------------------------------------------------
_MODULES_WITH_REQUESTS = (
    "animecaos.plugins.animesonlinecc",
    "animecaos.plugins.animefire",
)


def apply() -> None:
    """Aplica patch nos plugins."""
    # 1. Importar plugins primeiro
    print("Info: Importando plugins para cloudscraper_patch...")
    for mod_name in _MODULES_WITH_REQUESTS:
        try:
            importlib.import_module(mod_name)
            print(f"  → {mod_name}: importado")
        except Exception as e:
            print(f"  ⚠ {mod_name}: falha ({e})")

    # 2. Criar wrapper
    class CloudScraperRequests:
        """Wrapper drop-in para requests."""
        get = staticmethod(patched_get)
        head = staticmethod(_patched_head)
        post = staticmethod(_patched_post)
        
        @staticmethod
        def exceptions():
            if "requests" in sys.modules:
                return __import__("requests").exceptions
            return None
    
    fake_requests = CloudScraperRequests()

    # 3. Aplicar patch
    patched_count = 0
    for mod_name in _MODULES_WITH_REQUESTS:
        mod = sys.modules.get(mod_name)
        if mod is None:
            print(f"  Aviso: {mod_name} não encontrado")
            continue
        
        mod.requests = fake_requests
        patched_count += 1
        print(f"  → {mod_name}: requests substituído")

    print(f"Info: cloudscraper_patch aplicado em {patched_count} módulo(s)")
