# AnimeCaos - Contexto Global do Projeto (Modelo ITS)

Data de referencia: 2026-03-17
Repositorio: animecaos
Versao app: 0.1.2

---

## 1) Modelo ITS

Este documento usa o modelo ITS para organizar contexto tecnico completo:

- I (Intent): objetivo do produto, escopo funcional e regras de negocio.
- T (Topology): arquitetura, componentes, camadas, integracoes e dados.
- S (Strategy): estrategias de execucao, concorrencia, resiliencia, performance e evolucao.

---

## 2) I - Intent (Produto e Regras)

## 2.1 Proposito do produto

AnimeCaos e um hub desktop para descoberta, reproducao e download de episodios de anime a partir de multiplas fontes publicas. O foco e experiencia local, interface limpa e operacao sem anuncios na UI do app.

## 2.2 Objetivos principais

- Busca unificada em varias fontes.
- Resolucao de episodios e player URL por source plugin.
- Reproducao via mpv.
- Download offline via yt-dlp.
- Metadados (capa/sinopse) via AniList.
- Historico de continuidade por anime/episodio.
- Distribuicao em executavel standalone.

## 2.3 Escopo funcional atual

- GUI PySide6 (principal).
- CLI legado com fluxo simplificado.
- Landing Next.js institucional/comercial.

## 2.4 Regras de negocio centrais

1. Busca invalida (query vazia) deve falhar com mensagem amigavel.
2. Lista final de busca prioriza resultados com pelo menos uma fonte "playable".
3. Resolucao de player escolhe a primeira fonte valida em execucao concorrente.
4. Links Blogger sao tratados como indisponiveis para reproducao.
5. Historico deve salvar anime, indice de episodio e fontes de episodio.
6. Metadados nao podem bloquear fluxo principal da UI.
7. Operacoes pesadas rodam em worker/background para nao travar thread principal.

## 2.5 Nao objetivos explicitos

- Nao ha backend proprio para catalogo.
- Nao ha banco SQL no projeto atual (persistencia local JSON + cache arquivos).
- Nao ha autenticao de usuario.
- Nao ha servico de streaming proprio.

---

## 3) T - Topology (Arquitetura, Dados e Fluxos)

## 3.1 Mapa de componentes

- Entry points:
  - `main.py`
  - `animecaos/__main__.py`
  - `animecaos/app.py`
- UI:
  - GUI: `animecaos/ui/gui/*`
  - CLI: `animecaos/ui/cli/*`
- Service layer:
  - `animecaos/services/anime_service.py`
  - `animecaos/services/anilist_service.py`
  - `animecaos/services/history_service.py`
  - `animecaos/services/watchlist_service.py`
  - `animecaos/services/updater_service.py`
- Core:
  - `animecaos/core/repository.py`
  - `animecaos/core/loader.py`
  - `animecaos/core/paths.py`
- Plugins (sources):
  - `animecaos/plugins/animefire.py`
  - `animecaos/plugins/animesonlinecc.py`
  - `animecaos/plugins/animesvision.py`
  - `animecaos/plugins/hinatasoul.py`
  - `animecaos/plugins/betteranime.py` (desativado no load)
  - `animecaos/plugins/animeplayer.py` (implementado, nao listado no AVAILABLE_PLUGINS)
- Player:
  - `animecaos/player/video_player.py`
- Landing:
  - `landing/src/*`

## 3.2 Arquitetura em camadas

1. Interface Layer (GUI/CLI)
2. Application Services
3. Core Orchestration (Repository + Plugin Loader)
4. Source Plugins (HTTP/Selenium scraping)
5. Infra local (mpv, yt-dlp, geckodriver, filesystem)

## 3.3 Design de integracao por plugin

Contrato (`PluginInterface`):

- `search_anime(query)`
- `search_episodes(anime, url, params)`
- `search_player_src(url_episode) -> str`
- `is_episode_playable(url_episode) -> bool` (default permissivo)

Orquestracao:

- Plugins registram no singleton `rep` (`Repository`).
- Busca de anime e episodios e concorrente.
- Falhas por plugin sao isoladas com log e fluxo segue com resultados parciais.

## 3.4 Entidades de dominio

- Anime
  - titulo exibivel
  - titulo normalizado (fuzzy dedupe)
  - lista de fontes/URLs candidatas
- SourcePlugin
  - nome
  - funcoes de busca/resolucao
- Episode
  - titulo episodio
  - url episodio por fonte
- EpisodeSourceSet
  - `list[tuple[list[url], source_name]]`
- HistoryEntry (`dataclass`)
  - anime
  - episode_index
  - episode_sources
- WatchlistItem
  - anime string
- MetadataInfo
  - description
  - cover_path
  - cover_url
- UpdateInfo
  - current_version
  - latest_version
  - release_notes
  - download_url

## 3.5 Estruturas de dados internas (Repository)

- `sources: dict[source_name, plugin_class]`
- `anime_to_urls: defaultdict[list[(url, source, params)]]`
- `anime_episodes_titles: defaultdict[list[list[str]]]`
- `anime_episodes_urls: defaultdict[list[(list[url], source)]]`
- `norm_titles: dict[title, normalized_title]`

## 3.6 Persistencia local

Windows path base: `%APPDATA%/AnimeCaos` (fallback: `%USERPROFILE%/AppData/Roaming/AnimeCaos`)

Arquivos:

- `history.json`
- `watchlist.json`
- `cache/covers/*` (imagens AniList)
- `log.txt` (mpv)
- `updater.log` (batch update)

Compatibilidade legacy:

- suporte a pasta legacy `animecaos` minusculo para ler dados antigos.

## 3.7 Fluxos principais (sequence)

## Fluxo A - Startup GUI

1. `run_gui(debug)` cria QApplication, tema e splash.
2. Inicializa services (AnimeService, HistoryService, AniListService).
3. Splash termina, instancia MainWindow.
4. MainWindow carrega historico e inicia check de update em background.

## Fluxo B - Busca de anime

1. Usuario envia query.
2. MainWindow chama `AnimeService.search_animes(query)` em worker.
3. Service garante plugins carregados.
4. Repository limpa estado runtime e busca em fontes concorrentes.
5. Service valida tocabilidade (`rep.is_playable`) para cada titulo.
6. UI recebe lista final, renderiza cards e dispara metadata async por card.

## Fluxo C - Carregar episodios

1. Abrir detalhe de anime.
2. `fetch_episode_titles(anime)` em worker.
3. Repository executa `search_episodes` nas URLs/fontes do anime.
4. Escolha da lista final prioriza lista mais curta (heuristica anti mismatch OVA/especial).
5. UI popula EpisodeRows.

## Fluxo D - Reproducao

1. Usuario clica Play no episodio.
2. MainWindow pede `resolve_player_url(anime, idx)`.
3. Repository tenta resolver player source em paralelo entre fontes.
4. Primeiro URL valido e retornado.
5. `play_video(url)` executa mpv com headers (referer + user-agent).
6. Ao fim, historico e atualizado.

## Fluxo E - Download

1. Usuario clica Download.
2. App resolve player URL (mesma logica de reproducao).
3. `DownloadWorker` inicia yt-dlp em subprocess.
4. Overlay parseia progresso/ETA/speed.
5. Conclusao: opcao abrir pasta downloads.

## Fluxo F - Continuar do historico

1. Home mostra cards de historico.
2. Clique carrega `HistoryEntry`.
3. Service injeta fontes historicas em memoria.
4. Gera titulos sinteticos `Episodio N`.
5. UI posiciona no episodio salvo.

## Fluxo G - Metadados AniList

1. Worker chama AniList GraphQL por anime.
2. Remove HTML da descricao.
3. Opcional: traduz para PT via endpoint Google Translate publico.
4. Download de capa para cache local.
5. Atualiza UI (detalhe e cards).

## Fluxo H - Atualizacao do app

1. Worker chama GitHub Releases latest.
2. Se versao nova: dialog de confirmacao.
3. Download zip/exe.
4. Gera batch `update.bat` para hot swap.
5. Reinicia app.

## 3.8 Estados de UI relevantes

MainWindow:

- `_busy`: lock de tarefa unica para operacoes criticas.
- `_current_anime`, `_episodes_anime`
- `_current_episode_index`
- `_episode_titles`
- `_cover_cache`
- `_active_workers`, `_metadata_workers`
- `_active_download_worker`

Views:

- SearchView: welcome -> skeleton loading -> results/empty
- DetailView: loading episodios -> lista/empty
- Overlays: play/download status

## 3.9 Landing architecture

- Framework: Next.js App Router.
- i18n: `next-intl`.
- Motion/UI: `framer-motion`, `lucide-react`.
- SEO: metadata por rota + JSON-LD.
- Estrutura por locale: `/pt`, `/en`.
- Conteudo em `landing/src/messages/{pt,en}.json`.

---

## 4) S - Strategy (Tecnica, Operacao e Evolucao)

## 4.1 Estrategia de execucao

- Concurrency-first nas operacoes de IO/rede via `ThreadPoolExecutor`.
- Fail-soft: plugin com erro nao derruba busca global.
- Async-like em GUI via `QThreadPool + QRunnable`.
- Work separation:
  - task runner geral para operacoes bloqueantes
  - workers dedicados para download/update/metadata

## 4.2 Estrategia de resiliencia

- Timeouts em requests/plugin waits.
- Try/except amplo em fronteiras de plugin.
- Fallback de dados:
  - sem episodios -> lista sintetica em historico
  - sem metadata -> placeholders dinamicos
- Check rapido de tocabilidade com HTTP quando possivel.

## 4.3 Estrategia de deduplicacao e matching

- Normalizacao de titulo:
  - lowercase, remocoes/substituicoes (`temporada`->`season`, etc)
- Fuzzy ratio com threshold 95 para agrupar itens parecidos.

## 4.4 Estrategia de cache

- AniList:
  - memory cache por chave de query limpa
  - disk cache para covers
- Cover cache de UI em memoria para cards/detalhes
- Nao ha cache TTL formal para busca/episodios no core atualmente.

## 4.5 Estrategia de seguranca funcional

- Bloqueio explicito para hosts Blogger em resolucao de player.
- Validacao de URL de player (nao javascript/about:blank; exigir http/https).
- Referer derivado da URL para compatibilidade com hosts.

## 4.6 Estrategia de distribuicao

- Build Python: PyInstaller onefile + binarios embarcados.
- Dependencias runtime esperadas:
  - mpv
  - yt-dlp
  - geckodriver
  - Firefox
- Instalador Windows via Inno Setup (script existente).

## 4.7 Estrategia de observabilidade

- Logging Python (`debug` ou `warning`).
- Log textual de eventos no painel da GUI.
- Logs externos:
  - mpv -> `log.txt`
  - updater -> `updater.log`

## 4.8 Estrategia de performance atual (diagnostico)

Pontos fortes:

- Busca e resolucao por fonte em paralelo.
- Filtro rapido de tocabilidade por HTTP nos plugins que implementam.

Pontos limitantes:

- Validacao de todos resultados no caminho critico da busca.
- Custo de abrir Selenium repetidamente.
- N+1 requests em algumas fontes durante busca.
- Timeout de busca pode nao cortar completamente workers lentos.

## 4.9 Estrategia de evolucao recomendada (roadmap tecnico)

1. Instrumentar KPIs de busca e fonte.
2. Separar busca em 2 fases:
   - fase rapida de descoberta
   - validacao progressiva/background
3. Introduzir cache TTL para query e episodios.
4. Pool/semaforo para Selenium.
5. Lazy metadata por visibilidade de card.
6. Hardening de concorrencia no Repository (locks finos).

---

## 5) Stack e Bibliotecas

## 5.1 Desktop (Python)

- Python 3.10+
- PySide6 6.10.2
- requests 2.32.3
- beautifulsoup4 4.12.3
- selenium 4.26.1
- fuzzywuzzy 0.18.0
- python-Levenshtein 0.26.1
- yt-dlp (runtime tool)
- mpv (runtime tool)
- pyinstaller 6.11.1
- windows-curses 2.4.0 (CLI fallback no Windows)

## 5.2 Landing (Web)

- Next.js 16.1.6
- React 19.2.3
- TypeScript 5
- next-intl 4.8.3
- framer-motion 12.35.2
- lucide-react 0.577.0
- next-sitemap 4.2.3
- @vercel/analytics 1.6.1
- eslint 9 + eslint-config-next

---

## 6) Arquitetura de arquivos (high-level)

```
animecaos/
  app.py
  core/
    loader.py
    repository.py
    paths.py
  services/
    anime_service.py
    anilist_service.py
    history_service.py
    watchlist_service.py
    updater_service.py
  plugins/
    animefire.py
    animesonlinecc.py
    animesvision.py
    hinatasoul.py
    betteranime.py
    animeplayer.py
    utils.py
  ui/
    gui/
      app.py
      main_window.py
      views.py
      components.py
      workers.py
      overlays...
    cli/
      app.py
      menu.py
  player/
    video_player.py

landing/
  src/
    app/
    components/
    messages/
    lib/
    i18n/
```

---

## 7) Contratos e formatos de dados

## 7.1 History JSON (shape)

`history.json`:

```json
{
  "Anime Title": [
    [
      [["url_ep1", "url_ep2"], "source_name"],
      [["url_ep1_alt"], "source_alt"]
    ],
    3
  ]
}
```

Onde:

- elemento [0] = episode_sources serializado
- elemento [1] = episode_index (0-based)

## 7.2 Watchlist JSON

`watchlist.json`:

```json
[
  "Anime A",
  "Anime B"
]
```

## 7.3 Runtime payloads importantes

- Search result card: `{ "title": str, "cover_path": str|None }`
- Resume payload: `{ "entry": HistoryEntry, "episode_titles": list[str] }`
- Play payload: `{ anime, episode_index, player_url, episode_sources, eof }`

---

## 8) Regras operacionais por modulo

## 8.1 `AnimeService`

- Carrega plugins 1x por instancia.
- Em debug, restringe plugin default para `animesonlinecc`.
- Busca: reseta runtime, busca titulos, valida tocabilidade.
- Episodios: retorna lista real ou sintetica.
- Player: resolve URL via repository, reproduz via mpv.

## 8.2 `Repository`

- Singleton global (`rep`).
- Estado compartilhado de busca/episodios.
- Concorrencia em:
  - busca de anime por fonte
  - busca de episodios por URL/fonte
  - validacao tocabilidade por fonte
  - resolucao player por fonte

## 8.3 Plugins

- Cada plugin traduz HTML/DOM da fonte para contrato comum.
- Podem combinar HTTP + Selenium.
- `is_episode_playable` idealmente evita Selenium (check rapido).

## 8.4 GUI Task Model

- `_run_task` bloqueia multitarefa critica por `_busy`.
- Metadata usa workers separados e nao bloqueia fluxo principal.
- Download e update usam workers especificos/threads dedicadas.

---

## 9) System Design (visao sintetica)

## 9.1 Component graph

```text
[User]
  -> [GUI/CLI]
    -> [AnimeService]
      -> [Repository Singleton]
        -> [Plugin Loader]
        -> [Plugins: HTTP/Selenium]
      -> [Video Player (mpv)]
    -> [AniListService]
      -> [AniList GraphQL + cover cache]
    -> [HistoryService/WatchlistService]
      -> [Local JSON storage]
    -> [UpdaterService]
      -> [GitHub Releases API + updater.bat]
```

## 9.2 Responsabilidades

- UI: orquestracao de interacao e estado visual.
- Service: regras de aplicacao.
- Core/Repository: agregacao e fan-out/fan-in de fontes.
- Plugin: adaptador de fonte externa.
- Infra: reproducao/download/persistencia/atualizacao.

---

## 10) Constraints, Assumptions e Riscos

## 10.1 Constraints tecnicos

- Dependencia de estrutura HTML dos sites de fonte (instavel por natureza).
- Selenium+Firefox obrigatorios para parte dos fluxos.
- Sem backend proprio para normalizacao de catalogo.

## 10.2 Assumptions

- Fontes podem falhar ou mudar sem aviso.
- Rede do usuario pode ser intermitente.
- Usuario desktop Windows e publico principal.

## 10.3 Riscos operacionais

- Mudanca de DOM em fontes quebra plugins.
- Bloqueios anti-bot impactam Selenium.
- Validacao pesada pode aumentar muito latencia de busca.

---

## 11) Gaps conhecidos no estado atual

1. Plugin `betteranime` esta no `AVAILABLE_PLUGINS`, mas `load()` retorna sem registrar.
2. `animeplayer` existe, mas nao esta na lista default de plugins carregados.
3. Watchlist service existe, mas nao esta integrado no fluxo principal da GUI.
4. Landing referencia screenshots em `.png` no codigo, enquanto assets atuais publicados estao em `.webp`.
5. `main_window.py` concentra muita responsabilidade (candidato a modularizacao).

---

## 12) Padroes de codigo e convencoes

- Python:
  - type hints progressivos
  - services separados por responsabilidade
  - tratamento fail-soft nas fronteiras de IO/rede
- GUI:
  - componentes custom PySide6
  - overlays para operacoes longas
  - estado local central em MainWindow
- Landing:
  - componentes por secao
  - metadata por rota
  - i18n por namespace JSON

---

## 13) Checklist de onboarding tecnico (rapido)

1. Ler `animecaos/app.py` para entrypoint.
2. Ler `animecaos/ui/gui/main_window.py` para fluxo de usuario.
3. Ler `animecaos/services/anime_service.py` para regra de busca/player.
4. Ler `animecaos/core/repository.py` para orquestracao multi-fonte.
5. Ler plugins ativos para entender comportamento de cada fonte.
6. Rodar app em debug com plugin unico para validar pipeline.

---

## 14) Definicao de pronto para mudancas sem regressao

Uma mudanca em busca/reproducao e considerada segura quando:

1. Nao quebra resolucao de player em fontes validas.
2. Nao remove fallback de erro por plugin.
3. Nao bloqueia thread principal da GUI.
4. Mantem persistencia de historico compativel.
5. Preserva bloqueio de URLs invalidas/Blogger.
6. Mantem ordenacao/consistencia de resultados.

---

## 15) Resumo final do contexto

AnimeCaos e um agregador desktop orientado a plugins, com foco em UX local e resiliencia contra falhas de fonte. A arquitetura atual e modular e funcional, com fluxo critico concentrado em `AnimeService + Repository + Plugins`. O maior custo sistemico esta no acoplamento entre busca e validacao de tocabilidade, enquanto a evolucao recomendada segue para busca progressiva, melhor controle de concorrencia e cache mais agressivo.

