#!/usr/bin/env python3
"""
Teste direto do cloudscraper nos plugins.
Execute na VPS após aplicar o patch.
"""

import sys
from pathlib import Path

# Adicionar root do projeto ao path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

print("=" * 60)
print("TESTE DIRETO - CLOUDSCRAPER")
print("=" * 60)

# Aplicar patches
from app.selenium_patch import apply as apply_selenium
apply_selenium()

from app.cloudscraper_patch import apply as apply_cloudscraper
apply_cloudscraper()

# Importar plugins
print("\nImportando plugins...")
from animecaos.plugins import animesonlinecc, animefire, animesvision
from animecaos.core.repository import rep

print("Plugins importados com sucesso!\n")

# Testar animesonlinecc
print("-" * 60)
print("Testando animesonlinecc...")
print("-" * 60)
try:
    rep.reset_runtime_data()
    animesonlinecc.AnimesOnlineCC.search_anime("hunter")
    resultados = rep.get_anime_titles()
    print(f"✓ animesonlinecc: {len(resultados)} resultados")
    for titulo in resultados[:5]:
        print(f"  - {titulo}")
except Exception as e:
    print(f"✗ animesonlinecc: {e}")

# Testar animefire
print("\n" + "-" * 60)
print("Testando animefire...")
print("-" * 60)
try:
    rep.reset_runtime_data()
    animefire.AnimeFire.search_anime("hunter")
    resultados = rep.get_anime_titles()
    print(f"✓ animefire: {len(resultados)} resultados")
    for titulo in resultados[:5]:
        print(f"  - {titulo}")
except Exception as e:
    print(f"✗ animefire: {e}")

# Testar animesvision (pode demorar)
print("\n" + "-" * 60)
print("Testando animesvision (pode demorar alguns segundos)...")
print("-" * 60)
try:
    rep.reset_runtime_data()
    animesvision.AnimesVision.search_anime("hunter")
    resultados = rep.get_anime_titles()
    print(f"✓ animesvision: {len(resultados)} resultados")
    for titulo in resultados[:5]:
        print(f"  - {titulo}")
except Exception as e:
    print(f"✗ animesvision: {e}")

print("\n" + "=" * 60)
print("TESTE CONCLUÍDO")
print("=" * 60)
