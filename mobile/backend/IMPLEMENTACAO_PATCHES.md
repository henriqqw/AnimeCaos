# Implementação dos Patches - Resumo

## O que foi implementado

### 1. cloudscraper_patch.py ✨ NOVO
**Arquivo:** `mobile/backend/app/cloudscraper_patch.py`

**Propósito:** Substituir `requests.get()` por `cloudscraper` nos plugins `animesonlinecc` e `animefire` para bypass do Cloudflare.

**Como funciona:**
- Cria um wrapper `CloudScraperRequests` que intercepta chamadas `requests.get()`
- Substitui o atributo `requests` no namespace de cada plugin
- Usa `cloudscraper.create_scraper()` com configuração otimizada (Firefox UA, delay 10s, double_down)

**Plugins afetados:**
- `animecaos.plugins.animesonlinecc` (busca com HTTP)
- `animecaos.plugins.animefire` (busca com HTTP)

### 2. main.py (atualizado)
**Arquivo:** `mobile/backend/app/main.py`

**Mudança:** Adicionado chamada para `_apply_cloudscraper_patch()` após `_apply_selenium_patch()`

```python
# Força plugins desktop a usarem Firefox ESR + geckodriver da VPS.
from app.selenium_patch import apply as _apply_selenium_patch
_apply_selenium_patch()

# Força plugins desktop a usarem cloudscraper ao invés de requests (bypass Cloudflare).
from app.cloudscraper_patch import apply as _apply_cloudscraper_patch
_apply_cloudscraper_patch()
```

### 3. requirements.txt (atualizado)
**Arquivo:** `mobile/backend/requirements.txt`

**Mudança:** Adicionado `cloudscraper==1.2.71`

### 4. animesvision_selectors.py ✨ NOVO
**Arquivo:** `mobile/backend/app/animesvision_selectors.py`

**Propósito:** Documentar seletores CSS do AnimesVision para facilitar manutenção futura.

**Conteúdo:**
- Lista de seletores para busca de animes
- Lista de seletores para episódios
- Lista de seletores para iframes de player

### 5. test_patches.py ✨ NOVO
**Arquivo:** `mobile/backend/test_patches.py`

**Propósito:** Script de teste para validar que os patches foram aplicados corretamente.

**Uso:**
```bash
cd ~/animecaos/mobile/backend
source .venv/bin/activate
python test_patches.py
```

### 6. PATCHES_README.md ✨ NOVO
**Arquivo:** `mobile/backend/app/PATCHES_README.md`

**Propósito:** Documentação completa dos patches, troubleshooting e guia de extensão.

---

## Como testar na VPS

### Passo 1: Instalar cloudscraper
```bash
cd ~/animecaos/mobile/backend
source .venv/bin/activate
pip install cloudscraper==1.2.71
```

### Passo 2: Rodar testes dos patches
```bash
python test_patches.py
```

**Saída esperada:**
```
============================================================
TESTE DE PATCHES - BACKEND MOBILE
============================================================

[1/3] Testando selenium_patch...
Info: selenium_patch aplicado — binary=/usr/bin/firefox-esr, geckodriver=/usr/local/bin/geckodriver
✓ selenium_patch aplicado com sucesso

[2/3] Testando cloudscraper_patch...
  → animecaos.plugins.animesonlinecc: requests substituído por cloudscraper
  → animecaos.plugins.animefire: requests substituído por cloudscraper
Info: cloudscraper_patch aplicado em 2 módulo(s)
✓ cloudscraper_patch aplicado com sucesso

[3/3] Verificando plugins patcheados...
✓ animesonlinecc.requests patcheado
✓ animefire.requests patcheado
✓ animesvision._make_driver disponível

============================================================
TESTE CONCLUÍDO
============================================================
```

### Passo 3: Iniciar backend e testar busca
```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Logs esperados no startup:**
```
Info: selenium_patch aplicado — binary=/usr/bin/firefox-esr, geckodriver=/usr/local/bin/geckodriver
Info: cloudscraper_patch aplicado em 2 módulo(s)
  → animecaos.plugins.animesonlinecc: requests substituído por cloudscraper
  → animecaos.plugins.animefire: requests substituído por cloudscraper
Info: plugins mobile ativos: animesonlinecc, animefire, animesvision
```

### Passo 4: Testar endpoint de busca
Em outro terminal:
```bash
curl "http://localhost:8000/search?q=hunter"
```

**Resultado esperado:**
- ✅ Sem erros 403 Forbidden
- ✅ Lista de animes retornada
- ✅ Logs mostram todas as 3 fontes tentando busca (pode ter algum 403 residual, mas animesvision deve retornar)

---

## Estrutura de Arquivos Criada/Modificada

```
mobile/backend/
├── app/
│   ├── main.py                      ✏️ MODIFICADO (adicionado cloudscraper_patch)
│   ├── selenium_patch.py            ✓ MANTIDO (já existia)
│   ├── cloudscraper_patch.py        ✨ NOVO
│   ├── animesvision_selectors.py    ✨ NOVO (documentação)
│   └── PATCHES_README.md            ✨ NOVO (documentação completa)
├── requirements.txt                 ✏️ MODIFICADO (adicionado cloudscraper)
└── test_patches.py                  ✨ NOVO (script de teste)
```

---

## Próximos Passos (Opcional)

### 1. Investigar AnimesVision
Se o AnimesVision ainda não retornar resultados após o patch:

```bash
# Testar busca manual com Selenium
cd ~/animecaos/mobile/backend
source .venv/bin/activate
python3 -c "
from selenium import webdriver
from selenium.webdriver.common.by import By

options = webdriver.FirefoxOptions()
options.add_argument('--headless')
options.binary_location = '/usr/bin/firefox-esr'
driver = webdriver.Firefox(options=options)

driver.get('https://animesvision.biz/search?nome=hunter')
import time
time.sleep(3)

cards = driver.find_elements(By.CSS_SELECTOR, 'div.row div.col a')
print(f'Encontrados {len(cards)} resultados')
for card in cards[:5]:
    print(f'  - {card.text.strip()}')

driver.quit()
"
```

### 2. Atualizar seletores CSS
Se necessário, atualizar `animesvision_selectors.py` com os seletores corretos.

### 3. Monitorar logs
Ficar atento a:
- Erros 403 (Cloudflare) → cloudscraper deve resolver
- Timeouts → aumentar delay do cloudscraper
- 0 resultados → seletores CSS desatualizados

---

## Rollback (se necessário)

Para remover o cloudscraper_patch:

```bash
# 1. Editar main.py e remover linhas:
#    from app.cloudscraper_patch import apply as _apply_cloudscraper_patch
#    _apply_cloudscraper_patch()

# 2. Desinstalar cloudscraper
pip uninstall cloudscraper

# 3. Remover de requirements.txt
```

---

**Implementado por:** Assistente Qwen Code  
**Data:** 2026-03-13  
**Status:** ✅ Pronto para teste em produção
