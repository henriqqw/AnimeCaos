# Mapa do código

Mapa conferido em 19/10/2026. Atualize junto com mudanças de responsabilidade, telas, métodos ou scripts. O conteúdo de `Legacy/` não entra no runtime Go.

## Raiz e empacotamento

| Caminho | Responsabilidade |
|---|---|
| `main.go` | Entry point Wails, embed do frontend/ícone, janela, geometria visível, diálogos, ciclo da bandeja Windows, single-instance e entrada do helper de atualização |
| `go.mod`, `go.sum` | Versão do Go e dependências |
| `wails.json` | Configuração do projeto Wails e comandos do frontend |
| `cmd/animecaos/main.go` | CLI e navegação interativa com os mesmos serviços do app |
| `cmd/package/main.go` | Criação do stage, compilação, cópia de dependências e manifestos SHA-256 |
| `deploy/go/build-appimage.sh` | Geração de AppImage a partir do stage Linux |
| `deploy/go/com.animecaos.App.desktop` | Desktop entry Linux |
| `deploy/go/windows.iss` | Definição Inno Setup |
| `build/appicon.png`, `build/windows/icon.ico` | Recursos-fonte de ícone do Wails |
| `build/windows/info.json` | Metadados de identidade usados pela integração Windows do Wails |
| `build/windows/wails.exe.manifest` | Manifesto do executável Windows |
| `assets/icons/icon.png`, `assets/icons/icon.ico` | Fonte do ícone quadrado da janela e dos pacotes |
| `assets/icons/wordmark.png` | Lettering AnimeCaos recortado com fundo transparente |
| `public/icon.png`, `public/icon.ico` | Ícones copiados para pacotes |
| `assets/screenshots/` | Capturas usadas como material visual do projeto; não são telas do runtime |
| `README.md`, `CHANGELOG.md` | Apresentação, comandos de entrada e histórico da aplicação Go |
| `AGENTS.md` | Regras de trabalho e atualização da documentação para futuras sessões |
| `docs/architecture/SEARCH_PIPELINE_PLAN.md` | Arquitetura, comportamento implementado e próximos alvos para busca em lote, latência, identidade e preflight |
| `docs/architecture/CATALOG_EXPANSION.md` | Contrato, registro, fluxo e critérios para integrar novos provedores de anime |
| `.gitignore` | Exclusões do repositório; os ícones-fonte Wails têm exceções explícitas |

## Frontend

| Arquivo | Conteúdo |
|---|---|
| `frontend/package.json`, `frontend/package-lock.json` | Dependências e scripts npm |
| `frontend/tsconfig.json` | Configuração TypeScript |
| `frontend/index.html` | Documento HTML de entrada do Vite/Wails |
| `frontend/public/animecaos-icon.png` | Ícone quadrado usado na sidebar recolhida e na identidade web |
| `frontend/public/animecaos-wordmark.png` | Lettering transparente da sidebar expandida e da tela de carregamento |
| `frontend/public/anilist.ico`, `frontend/public/myanimelist.ico` | Favicons dos domínios oficiais usados para identificar as integrações de conta |
| `frontend/src/main.tsx` | Inicialização do React |
| `frontend/src/App.tsx` | Navegação local, sidebar, cabeçalho, telas, cards com ano/episódios, prévia vinculada à identidade canônica, catálogo/capítulos/leitor de mangá, painel AniList/MAL e configurações com estado de salvamento |
| `frontend/src/api.ts` | Proxy tipado para Wails, Desktop e eventos, incluindo AniList ID na prévia |
| `frontend/src/types.ts` | Tipos dos DTOs compartilhados com Go, incluindo metadados de ano e formato |
| `frontend/src/Image.tsx` | Imagens com carregamento via backend e fallback |
| `frontend/src/style.css` | Temas, componentes, layout responsivo, carrosséis, previews, selo de qualidade da busca e grade responsiva de configurações |
| `frontend/src/App.test.tsx` | Testes de regressão da interface, incluindo pesquisa, leitura MangaDex e conexão visual das contas AniList/MAL |

As telas e suas chamadas estão em [FRONTEND.md](architecture/FRONTEND.md). Atualmente, várias telas ainda vivem no mesmo `App.tsx`.

## Backend Go: `internal/app`

| Arquivo | Conteúdo |
|---|---|
| `service.go` | Composição, casos de uso, cancelamento, busca com limites por fase, prévia de metadados ancorada opcionalmente no AniList ID, reprodução, consolidação do histórico de downloads offline, abertura segura da pasta de arquivos locais, ciclo de sessão do player, sincronização e eventos |
| `updater.go` | Instalação de pacote já baixado/validado e saída para reinício |
| `images.go` | Busca/cache de imagem e recuperação de capas |
| `service_test.go` | Busca canônica, cancelamento, autoplay concorrente, limpeza da sessão do player, mídia offline e live opt-in; o teste de stream registra o título/episódio de entrada e a resolução real |
| `availability_test.go` | Preflight de disponibilidade: concorrência, cancelamento, cache, prazos e publicação parcial sem cards não validados |
| `history_cover_test.go` | Aliases legados e persistência de capa recuperada |
| `history_offline_test.go` | Consolidação de progresso duplicado de arquivo baixado e retomada offline pela identidade canônica |
| `images_test.go` | Cache de falhas e imagens legadas offline |

## Domínio, provedores e integrações

| Caminho | Conteúdo |
|---|---|
| `internal/domain/models.go` | Modelos de anime, metadados canônicos de ano/formato/episódios, agrupamento provisório interno por consulta sazonal, títulos principais internos do AniList, episódio, stream, histórico, configurações, mangá/capítulo com crédito do grupo de tradução, downloads e `AnimeProvider` |
| `internal/providers/animefire.go` | Busca, detalhes e streams AnimeFire |
| `internal/providers/onlinecc.go` | Busca HTML, episódios, temporadas, opções de áudio, resolução de páginas estáticas/dinâmicas e fallback do RPC Blogger para mídia renderizada |
| `internal/providers/sushi.go` | Busca HTML, episódios, temporadas e players AJAX; aceita `data-embed`/`data-id` e usa o extrator filtrado de player embutido como fallback |
| `internal/providers/otakulogia.go` | Busca GraphQL, detalhes, grupos de temporada, variantes de áudio e verificação de acesso antes de retornar streams |
| `internal/providers/player_candidates.go` | Escopo ao contêiner de player, seleção conservadora de iframes, filtragem de anúncios conhecidos, política de Referer e detecção de intersticial |
| `internal/providers/browser_ad_proxy.go` | Proxy HTTP loopback temporário para navegadores de scraping; bloqueia hosts de anúncios/rastreadores conhecidos e encaminha normalmente o restante |
| `internal/providers/browser.go` | Extração de players após execução de JavaScript via Chromium ou delegação a Selenium; instala proxy temporário no navegador |
| `internal/providers/selenium.go` | Sessão WebDriver local para ler iframes/vídeos/JWPlayer renderizados, encerrar a árvore do GeckoDriver com limite e bloquear pop-ups |
| `internal/netx/advertising.go` | Lista de hosts conhecidos de anúncios/rastreadores e guarda contra redirecionamento HTTP a esses destinos |
| `internal/media/hls.go`, `gateway.go` | Rejeição de redirects de anúncios em manifesto, validação de mídia e proxy local usado pelo MPV |
| `internal/providers/selenium_test.go` | Preferências do Firefox, envelope WebDriver e inspeção de players renderizados |
| `internal/providers/blogger.go` | Parser RPC e renditions Blogger |
| `internal/providers/catalog.go` | Busca paralela, cache curto de páginas por consulta/provedor, aliases, expansão de temporada/ano com filtro de identidade, metadados visuais aplicados apenas a IDs canônicos exatos, correspondência por sequência de palavras, ranking, deduplicação, variantes e correspondência segura de episódios entre fontes |
| `internal/providers/search_intent.go` | Reconhece sufixos explícitos de temporada e ano de lançamento, produzindo consulta base sem remover esses qualificadores da correspondência final |
| `internal/app/availability.go` | Preflight do E1 da temporada consultada, FFprobe opcional para faixas de áudio, pool 6/2, cache separado por temporada e comparação de qualidade para a resposta em lote |
| `internal/providers/animefire_test.go` | Contrato, streams offline, cancelamento/recuperação e live opt-in |
| `internal/providers/onlinecc_test.go` | Números/temporadas explícitos, markup alternativo, áudio e política `no-referrer` |
| `internal/providers/player_candidates_test.go` | Isolamento do player, filtragem de wrappers/trackers e seleção conservadora sem raiz de vídeo |
| `internal/providers/browser_ad_proxy_test.go` | Bloqueio de hosts de anúncio em HTTP/CONNECT e passagem de requisições normais |
| `internal/netx/advertising_test.go`, `internal/media/hls_test.go`, `gateway_test.go` | Redirecionamento normal preservado; redirects conhecidos de anúncio param antes da validação e do MPV |
| `internal/providers/live_ad_audit_test.go` | Auditoria live opt-in da busca, player e validação de mídia nas quatro fontes registradas |
| `internal/providers/live_player_test.go` | Teste live opt-in específico por fonte: busca, detalhes, resolução, gateway local, codecs/dimensões, avanço e seek real no MPV |
| `internal/providers/browser_test.go` | Fixtures locais que injetam iframe por JavaScript, isolam tracker externo, rejeitam protector e simulam mídia HTML5 disponível após reprodução silenciada |
| `internal/providers/blogger_test.go` | Parser Blogger e testes live opt-in |
| `internal/providers/otakulogia_test.go` | Agrupamento de variantes de áudio, bloqueio de acesso VIP e rejeição de episódio malformado |
| `internal/providers/catalog_test.go` | Títulos relacionados, aliases, ano/adaptação, cache de página, ambiguidade, ranking, paginação, cancelamento e fallback de episódio por título único entre grupos de temporada |
| `internal/providers/sushi_test.go` | Busca/detalhes, AJAX com `data-id`, URL HLS em `srcdoc` e fallback para player embutido sem opção AJAX |
| `internal/providers/live_catalog_test.go` | Busca, detalhes, grupos de episódios e validação live opt-in de manifesto HLS/arquivo em amostras do início, meio e fim |
| `internal/integrations/anilist.go` | GraphQL, descoberta, aliases, consultas de título em lote/cache AniList (incluindo ano, formato e episódios), coalescência e tradução |
| `internal/integrations/accounts.go` | OAuth, perfil, logout e sync AniList/MAL |
| `internal/integrations/accounts_test.go` | Fixtures HTTP para mutation AniList, OAuth/renovação MyAnimeList e atualização de progresso nas listas |
| `internal/integrations/discord.go` | Rich Presence, conexão e heartbeat |
| `internal/integrations/discord_windows.go`, `discord_unix.go` | IPC Discord por sistema operacional |
| `internal/integrations/anilist_test.go` | Cache/coalescência, consulta de títulos em lote, parcialidade e aliases |
| `internal/integrations/discord_test.go` | IPC simulado, atualização e reconexão |

## Persistência, rede e serviços

| Caminho | Conteúdo |
|---|---|
| `internal/store/store.go` | SQLite, records, cache TTL e cópia de backup |
| `internal/store/migrate.go` | Importação de JSON/cache da instalação antiga |
| `internal/store/migrate_test.go` | Idempotência, cache legado, imagens e arquivos inválidos |
| `internal/netx/client.go` | Cliente HTTP, JSON, streaming, erros e rate gate |
| `internal/manga/service.go` | MangaDex: títulos, capítulos e grupo de tradução, fontes de página validadas e CBZ |
| `internal/manga/service_test.go` | CBZ, falha parcial, atribuição de grupo, páginas somente data-saver e live opt-in |
| `internal/downloads/queue.go` | Fila de anime/mangá, slots, cancelamento e persistência |
| `internal/downloads/library.go` | Biblioteca local, descoberta e exclusão de arquivo |
| `internal/downloads/queue_test.go` | Cancelamento/concorrência e interrupção em restart |
| `internal/media/gateway.go` | Proxy de streams, cabeçalhos do provedor (incluindo User-Agent), ranges e rewrite de playlists HLS |
| `internal/media/hls.go` | Reconhecimento e manipulação HLS |
| `internal/media/probe.go` | Leitura de codecs, dimensões, bitrate e duração com FFprobe opcional; configuração por `ANIMECAOS_FFPROBE_PATH` |
| `internal/media/probe_test.go` | Parser de saída do FFprobe e rejeição de mídia sem faixas de áudio/vídeo válidas |
| `internal/media/hls_test.go` | Diagnóstico claro de manifesto remoto ausente |
| `internal/media/archive.go` | Conteúdo compactado offline |
| `internal/media/gateway_test.go` | Cabeçalhos e resposta Range |
| `internal/player/player.go` | Processo MPV, JSON IPC, estado, sessão, posição, codecs e dimensões |
| `internal/player/ipc_windows.go`, `ipc_unix.go` | IPC por sistema operacional |
| `internal/player/player_test.go` | EOF natural, sessão, regra de 80% para episódio assistido e integração audiovisual opt-in |
| `internal/player/offline_test.go` | Reprodução offline |
| `internal/platform/system.go` | Diretórios, busca de binário, abertura no sistema e segurança de caminhos; encaminha revelação de arquivo para o adaptador nativo |
| `internal/platform/reveal_windows.go`, `reveal_other.go` | Abre ou reutiliza a pasta no gerenciador nativo; no Windows localiza e ativa a janela do Explorer |
| `internal/platform/window_position*.go` | Valida posição salva contra as áreas de trabalho dos monitores no Windows; teste da interseção da barra de título |
| `internal/platform/tray_windows.go`, `tray_other.go` | Menu de notificação Windows para abrir, minimizar, ocultar na bandeja e sair; implementação sem ação nas demais plataformas |
| `internal/platform/process_windows.go`, `process_unix.go` | Opções de subprocesso por plataforma |
| `internal/platform/publish.go` | Publicação de arquivo temporário |
| `internal/platform/publish_test.go` | Não sobrescrever arquivo já existente |
| `internal/update/update.go` | Releases, checksum, staging e substituição |
| `internal/update/parent_windows.go`, `parent_unix.go` | Espera do processo pai por plataforma |
| `internal/update/update_test.go` | Regras de versão, staging e atualização |

## Legado

`Legacy/README.python.md` descreve o arquivo do produto antigo. `Legacy/` contém app Python, testes, recursos de distribuição e assets históricos. O changelog antigo está em `Legacy/CHANGELOG.python.md`. Não execute seus scripts para desenvolver ou distribuir o produto Go.

Para conferir a lista de arquivos após uma mudança, execute `rg --files internal frontend/src cmd deploy/go` na raiz. Este mapa enumera todos os arquivos de código vigentes dessa árvore; resultados novos devem ganhar descrição aqui.

## Artefatos locais e gerados

Pastas como `bin/`, `dist/`, `release/`, `installer/` e partes de `build/` podem conter executáveis, bibliotecas de terceiros, logs, stages ou pacotes produzidos durante desenvolvimento. Elas não substituem os fontes em `internal/`, `frontend/`, `cmd/` e `deploy/go/`. O conteúdo pode variar entre máquinas e não é enumerado arquivo a arquivo neste mapa. Confira `.gitignore` e o script de empacotamento antes de tratar um artefato local como parte do produto.

O arquivo local `frontend/package.json.md5` não está versionado e não tem consumidor encontrado no código atual; não é uma fonte de versão nem uma dependência do runtime.
