#!/usr/bin/env python3
"""
Script para extrair HTML e descobrir seletores CSS atualizados.
Execute na VPS para debug.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup
import time

print("=" * 60)
print("EXTRAINDO HTML DOS SITES PARA ANALISE DE SELECTORES")
print("=" * 60)

options = Options()
options.add_argument("--headless")
options.binary_location = "/usr/bin/firefox-esr"

# Testar AnimesOnlineCC
print("\n[1/3] AnimesOnlineCC...")
try:
    driver = webdriver.Firefox(options=options)
    driver.get("https://animesonlinecc.to/search/hunter")
    time.sleep(3)
    html = driver.page_source
    driver.quit()
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Tentar varios seletores comuns
    selectors = [
        "div.data",
        "div.film-detail",
        "div.flw-item", 
        "div.item",
        "div.card",
        "article",
        "div.anime-item",
    ]
    
    print("  Seletores testados:")
    for sel in selectors:
        if "." in sel:
            cls = sel.split(".")[1]
            elements = soup.find_all("div", class_=cls)
        else:
            elements = soup.find_all(sel)
        print(f"    {sel}: {len(elements)} elementos")
    
    # Mostrar estrutura
    print("  Estrutura encontrada:")
    all_divs = soup.find_all("div")
    for div in all_divs[:20]:
        classes = div.get("class", [])
        if classes:
            print(f"    div.{classes} - {len(div.get_text(strip=True))} chars")
            
except Exception as e:
    print(f"  Erro: {e}")

# Testar AnimeFire
print("\n[2/3] AnimeFire...")
try:
    driver = webdriver.Firefox(options=options)
    driver.get("https://animefire.io/pesquisar/hunter")
    time.sleep(3)
    html = driver.page_source
    driver.quit()
    
    soup = BeautifulSoup(html, "html.parser")
    
    selectors = [
        "div.col-6",
        "div.divCardUltimosEps",
        "div.anime-card",
        "article",
        "div.card",
    ]
    
    print("  Seletores testados:")
    for sel in selectors:
        if "." in sel:
            cls = sel.split(".")[1]
            elements = soup.find_all("div", class_=cls)
        else:
            elements = soup.find_all(sel)
        print(f"    {sel}: {len(elements)} elementos")
    
    # Mostrar estrutura
    print("  Estrutura encontrada:")
    all_divs = soup.find_all("div")
    for div in all_divs[:20]:
        classes = div.get("class", [])
        if classes:
            text_len = len(div.get_text(strip=True))
            print(f"    div.{classes} - {text_len} chars")
            
except Exception as e:
    print(f"  Erro: {e}")

# Testar AnimesVision
print("\n[3/3] AnimesVision...")
try:
    driver = webdriver.Firefox(options=options)
    driver.get("https://animesvision.biz/search?nome=hunter")
    time.sleep(3)
    html = driver.page_source
    driver.quit()
    
    soup = BeautifulSoup(html, "html.parser")
    
    selectors = [
        "div.film-detail",
        "div.flw-item",
        "div.item",
        "div.row",
        "div.col",
    ]
    
    print("  Seletores testados:")
    for sel in selectors:
        if "." in sel:
            cls = sel.split(".")[1]
            elements = soup.find_all("div", class_=cls)
        else:
            elements = soup.find_all(sel)
        print(f"    {sel}: {len(elements)} elementos")
    
    # Mostrar links encontrados
    print("  Links encontrados:")
    links = soup.find_all("a", href=True)
    for link in links[:10]:
        href = link.get("href", "")
        text = link.get_text(strip=True)
        if text and ("anime" in href or "/anime" in href or "/episodio" in href):
            print(f"    {text} -> {href}")
            
except Exception as e:
    print(f"  Erro: {e}")

print("\n" + "=" * 60)
print("ANALISE CONCLUIDA")
print("=" * 60)
