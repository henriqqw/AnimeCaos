"""
Monkey-patch para forçar os plugins desktop a usarem cloudscraper ao invés de requests.
Aplicado no startup do mobile backend para bypass do Cloudflare.

Alvo: módulos animecaos.plugins.animesonlinecc e animecaos.plugins.animefire
que usam requests.get() para busca de animes.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

import cloudscraper

# ---------------------------------------------------------------------------
# Scraper global reutilizável (configuração otimizada para sites de anime)
# ---------------------------------------------------------------------------
_scraper = None


def _get_scraper() -> cloudscraper.CloudScraper:
    """Cria ou retorna scraper singleton com configurações otimizadas."""
    global _scraper
    if _scraper is None:
        # cloudscraper create_scraper - apenas browser e delay
        # double_down foi removido em versões recentes
        _scraper = cloudscraper.create_scraper(
            browser={"browser": "firefox", "platform": "windows", "mobile": False},
            delay=10,
        )
    return _scraper


def _patched_get(url, **kwargs):
    """
    Substituto drop-in para requests.get() que usa cloudscraper.
    Preserva a interface: cloudscraper_patch.get(url, timeout=X, headers=Y)
    """
    scraper = _get_scraper()
    
    # Extrair parâmetros relevantes
    timeout = kwargs.pop("timeout", None)
    headers = kwargs.pop("headers", None)
    
    # Cloudscraper aceita os mesmos parâmetros que requests
    if headers:
        kwargs["headers"] = headers
    
    # Nota: cloudscraper não suporta timeout nativo
    try:
        return scraper.get(url, **kwargs)
    except Exception as e:
        print(f"[cloudscraper] Erro ao buscar {url}: {e}")
        raise


def _patched_head(url, **kwargs):
    """Substituto drop-in para requests.head() que usa cloudscraper."""
    scraper = _get_scraper()
    headers = kwargs.pop("headers", None)
    if headers:
        kwargs["headers"] = headers
    return scraper.head(url, **kwargs)


def _patched_post(url, **kwargs):
    """Substituto drop-in para requests.post() que usa cloudscraper."""
    scraper = _get_scraper()
    headers = kwargs.pop("headers", None)
    if headers:
        kwargs["headers"] = headers
    return scraper.post(url, **kwargs)


# ---------------------------------------------------------------------------
# Módulos de plugins que usam requests.get() para busca
# ---------------------------------------------------------------------------
_MODULES_WITH_REQUESTS = (
    "animecaos.plugins.animesonlinecc",
    "animecaos.plugins.animefire",
)


def _ensure_imported(mod_name: str):
    """Importa o módulo se ainda não estiver em sys.modules."""
    if mod_name not in sys.modules:
        try:
            importlib.import_module(mod_name)
        except Exception:
            pass  # Plugin pode não existir; ignorar.
    return sys.modules.get(mod_name)


def apply() -> None:
    """
    Aplica patch substituindo o módulo requests nos plugins
    por um wrapper que usa cloudscraper.
    
    Estratégia:
    1. Importa os módulos de plugins primeiro
    2. Cria um módulo fake 'requests' com cloudscraper
    3. Substitui diretamente o atributo requests no namespace do plugin
    """
    # 1. Importar plugins primeiro (necessário para o patch funcionar)
    print("Info: Importando plugins para aplicar cloudscraper_patch...")
    for mod_name in _MODULES_WITH_REQUESTS:
        try:
            importlib.import_module(mod_name)
            print(f"  → {mod_name}: importado")
        except Exception as e:
            print(f"  ⚠ {mod_name}: falha ao importar ({e})")

    # 2. Criar módulo fake do requests com cloudscraper
    class CloudScraperRequests:
        """Wrapper drop-in para requests que usa cloudscraper."""
        get = staticmethod(_patched_get)
        head = staticmethod(_patched_head)
        post = staticmethod(_patched_post)
        
        # Manter compatibilidade com código que verifica atributos
        @staticmethod
        def exceptions():
            if "requests" in sys.modules:
                return __import__("requests").exceptions
            return None
    
    fake_requests = CloudScraperRequests()

    # 3. Aplicar patch em cada módulo - substituir diretamente no namespace
    patched_count = 0
    for mod_name in _MODULES_WITH_REQUESTS:
        mod = sys.modules.get(mod_name)
        if mod is None:
            print(f"  Aviso: módulo {mod_name} não encontrado em sys.modules")
            continue
        
        # Substituir o módulo requests no namespace do plugin
        # Isso funciona porque os plugins fazem: import requests
        # E o atributo 'requests' no módulo é sobrescrito
        mod.requests = fake_requests
        patched_count += 1
        print(f"  → {mod_name}: requests substituído por cloudscraper")

    print(f"Info: cloudscraper_patch aplicado em {patched_count} módulo(s)")
