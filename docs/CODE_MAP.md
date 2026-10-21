# Mapa do código

Mapa conferido em 21/10/2026. Atualize junto com mudanças de responsabilidade, telas, métodos ou scripts. O conteúdo de `Legacy/` não entra no runtime Go.

## Raiz e empacotamento

| Caminho | Responsabilidade |
|---|---|
| `main.go` | Entry point Wails, embed do frontend/ícone, janela com fundo preto para evitar flash antes da splash, prioridade em primeiro plano sincronizada com a splash, reexibição da splash na segunda instância, geometria visível, diálogos, ciclo da bandeja Windows, reinício por reload no modo dev e relançamento visível no pacote, início do auto-update em builds instaladas, single-instance e helper de atualização |
| `build_identity_dev.go`, `build_identity_production.go` | IDs de mutex e seleção do comportamento de reinício conforme os build tags dev/produção |
| `build_identity_dev_test.go`, `build_identity_production_test.go` | Testes dos IDs de instância e da estratégia de reinício selecionados pelos build tags |
| `go.mod`, `go.sum` | Versão do Go e dependências |
| `wails.json` | Configuração do projeto Wails e comandos do frontend |
| `cmd/animecaos/main.go` | CLI e navegação interativa com os mesmos serviços do app |
| `cmd/package/main.go` | Criação do stage; compilação do app via CLI Wails no Windows para incorporar ícone, manifesto e metadados PE; inclusão de MPV/FFmpeg/Firefox/GeckoDriver/WebView2, licenças e manifestos SHA-256 |
| `deploy/go/download-browser-runtime.ps1`, `download-browser-runtime-linux.sh` | Baixar e conferir versões/hashes oficiais de Firefox e GeckoDriver usados na release |
| `deploy/go/download-webview2-runtime.ps1` | Baixar o CAB oficial WebView2 fixo, conferir assinatura/versão e montar `bin/webview2` para o pacote Windows |
| `deploy/go/build-appimage.sh` | Geração de AppImage com Firefox/GeckoDriver preservados sem RPATH reescrito, executáveis, licenças e bibliotecas GTK/WebKitGTK |
| `deploy/go/com.animecaos.App.desktop` | Desktop entry Linux |
| `deploy/go/windows.iss` | Definição Inno Setup |
| `deploy/go/verify-windows-install.ps1` | Smoke test do portátil/instalador, verifica que o processo WebView2 vem do bundle, testa updater, reinício e preservação de dados |
| `deploy/go/verify-appimage.sh` | Testa os MPV/FFmpeg/FFprobe/Firefox/GeckoDriver extraídos do AppImage, iframe JS, abertura, aplicação do update e preservação de `state.db` |
| `deploy/go/bootstrap-appimage-tools.sh` | Obtém ferramentas AppImage com versões e SHA-256 fixados |
| `scripts/write-release-manifest.ps1` | Gera inventário SHA-256 e tamanho dos arquivos do stage após assinatura |
| `.github/workflows/ci.yml`, `.github/workflows/release.yml` | CI multiplataforma, builds de release com smoke tests, checksums assinados com Sigstore e Authenticode Windows quando os secrets de certificado existem; a release registra explicitamente quando Windows não tem assinatura Authenticode |
| `THIRD-PARTY-NOTICES.md`, `licenses/` | Avisos, textos de licença e fontes/metadados de dependências distribuídas |
| `build/appicon.png`, `build/windows/icon.ico` | Recursos-fonte de ícone do Wails |
| `build/windows/info.json` | Metadados de identidade usados pela integração Windows do Wails |
| `build/windows/wails.exe.manifest` | Manifesto do executável Windows |
| `assets/icons/icon.png`, `assets/icons/icon.ico` | Fonte do ícone quadrado da janela e dos pacotes |
| `assets/icons/wordmark.png` | Lettering AnimeCaos recortado com fundo transparente |
| `assets/readme-banner.png` | Banner de marca do README com slogan em lettering pixelado e retículas/linhas de mangá discretas |
| `assets/x-profile-banner.png` | Capa de perfil do AnimeCaos no X, exportada em 1500 × 500 px com área inferior esquerda reservada para a foto de perfil |
| `assets/readme/` | Capturas da Home, busca, detalhes, lista, histórico, downloads e catálogo/leitor de mangás exibidas no README |
| `assets/x-profile-banner.png` | Banner horizontal da identidade AnimeCaos para perfil social |
| `public/icon.png`, `public/icon.ico` | Ícones copiados para pacotes |
| `assets/screenshots/` | Capturas usadas como material visual do projeto; não são telas do runtime |
| `README.md`, `CHANGELOG.md` | Apresentação do app, galeria de telas, instalação, uso, arquitetura e histórico da aplicação Go |
| `AGENTS.md` | Regras de trabalho e atualização da documentação para futuras sessões |
| `docs/architecture/SEARCH_PIPELINE_PLAN.md` | Arquitetura, comportamento implementado e próximos alvos para busca em lote, latência, identidade e preflight |
| `docs/architecture/CATALOG_EXPANSION.md` | Contrato, registro, fluxo e critérios para integrar novos provedores de anime |
| `.gitignore` | Exclusões do repositório; os ícones-fonte Wails têm exceções explícitas |

## Frontend

| Arquivo | Conteúdo |
|---|---|
| `frontend/package.json`, `frontend/package-lock.json` | Dependências e scripts npm |
| `frontend/tsconfig.json` | Configuração TypeScript |
| `frontend/index.html` | Documento HTML de entrada do Vite/Wails; inicia o preload do vídeo da splash |
| `frontend/public/animecaos-icon.png` | Ícone quadrado usado na sidebar recolhida e na identidade web |
| `frontend/public/animecaos-wordmark.png` | Lettering transparente da sidebar expandida e da tela de carregamento |
| `frontend/public/avatar_loop.webm` | Único asset da mascote na splash: loop VP9 local de 8 s/60 fps, pré-carregado no HTML; sem poster PNG ou fallback estático |
| `frontend/public/anilist.ico`, `frontend/public/myanimelist.ico`, `frontend/public/discord.svg` | Ícones locais oficiais para identificar as integrações de conta e Rich Presence |
| `frontend/public/mascots/` | Artes PNG transparentes da mascote: versão normal, mini superdeformed, miniatura 256 px, poses e reações para busca/lista vazias, erros recuperáveis, feedback, piscadela na Home e leitura no catálogo de mangás. A splash de produção usa o WebM; Home e Mangás exibem suas reações no fim do conteúdo rolável |
| `frontend/src/main.tsx` | Inicialização do React |
| `frontend/src/App.tsx` | Splash de inicialização com vídeo local e wordmark em fade sincronizado, retry de vídeo, barra de progresso responsiva e estado de download do auto-update enquanto a interface fica bloqueada; navegação local, sidebar com links sociais, cabeçalho com busca contextual de anime/mangá, telas, estados vazios com reações e atalhos externos por ícones, cards com ano/episódios e preview de sinopse local-first, CTA “Ver anime” na Home e mascotes no fim do conteúdo rolável, descoberta de mangás com banner/categorias/prateleiras, busca compartilhada, reações contextuais em erros, retomada, capítulos/leitor, contas e Configurações com autosave e feedback via GitHub |
| `frontend/splash-preview.html`, `frontend/src/splash-preview.tsx`, `frontend/src/splash-preview.css` | Página Vite separada para revisar a animação da splash continuamente, com progresso simulado, ajustes de amplitude/velocidade e reinício do ciclo; não é usada pelo app |
| `frontend/src/StartupMascot.tsx` | Componente local de preview com Three.js; cria uma camada base e recortes alinhados das mechas laterais a partir dos pixels da arte original, deformando as pontas sem mover rosto ou corpo |
| `frontend/src/api.ts` | Proxy tipado para Wails, métodos Desktop e eventos, incluindo sinal de fim da splash, status do auto-update, descoberta MangaDex, filtro de categoria, AniList ID na prévia e operações de contas sem setters de credenciais MAL |
| `frontend/src/types.ts` | Tipos dos DTOs compartilhados com Go, incluindo manga/categoria/prateleiras, metadados de ano/formato e ID externo das contas; configurações não contêm Client ID MAL editável |
| `frontend/src/Image.tsx` | Imagens com carregamento via backend e fallback |
| `frontend/src/style.css` | Temas, splash responsiva com fade-in/fade-out sincronizado entre vídeo e wordmark, barra de progresso espessa com percentual e estado de retry, componentes, layout responsivo, sidebar com atalhos sociais, carrosséis, previews, tiles monocromáticos responsivos de categorias, selo de qualidade, reações da mascote e atalhos iconográficos de links externos, descoberta de mangás e Configurações com switches, autosave e feedback |
| `frontend/src/App.test.tsx` | Testes DOM da interface; busca, CTA das capas na Home, prévia de sinopse MangaDex, leitor, integrações e configurações (autosave, debounce, serialização, retry, índice e navegação Contas) |

As telas e suas chamadas estão em [FRONTEND.md](architecture/FRONTEND.md). Atualmente, várias telas ainda vivem no mesmo `App.tsx`.

## Backend Go: `internal/app`

| Arquivo | Conteúdo |
|---|---|
| `service.go` | Composição, casos de uso, cancelamento, busca com limites por fase, prévia de metadados ancorada opcionalmente no AniList ID, descoberta MangaDex com cache, filtro por categoria, reprodução, consolidação do histórico de downloads offline, abertura segura da pasta de arquivos locais, ciclo de sessão do player, sincronização com Client ID MAL interno e eventos |
| `updater.go` | Checagem automática na inicialização para Windows/AppImage, progresso/status da splash, validação e instalação do pacote, além do fluxo manual e saída para reinício |
| `updater_test.go` | Cobertura das plataformas elegíveis e do comportamento de seguir com a inicialização se a checagem de release falhar |
| `images.go` | Busca/cache de imagem e recuperação de capas |
| `service_test.go` | Busca canônica, cancelamento, autoplay concorrente, limpeza da sessão do player, mídia offline e live opt-in; o teste de stream registra o título/episódio de entrada e a resolução real |
| `availability_test.go` | Preflight de disponibilidade: concorrência, cancelamento, cache, prazos e publicação parcial sem cards não validados |
| `history_cover_test.go` | Aliases legados e persistência de capa recuperada |
| `history_offline_test.go` | Consolidação de progresso duplicado de arquivo baixado e retomada offline pela identidade canônica |
| `images_test.go` | Cache de falhas e imagens legadas offline |

## Domínio, provedores e integrações

| Caminho | Conteúdo |
|---|---|
| `internal/domain/models.go` | Modelos de anime, metadados canônicos de ano/formato/episódios, agrupamento provisório interno por consulta sazonal, títulos principais internos do AniList, episódio, stream, histórico, configurações sem credencial OAuth MAL editável, mangá/categoria/descoberta, capítulo com crédito do grupo de tradução, downloads e `AnimeProvider` |
| `internal/providers/animefire.go` | Busca, detalhes e streams AnimeFire |
| `internal/providers/onlinecc.go` | Busca HTML, episódios, temporadas, opções de áudio, resolução de páginas estáticas/dinâmicas e fallback do RPC Blogger para mídia renderizada |
| `internal/providers/sushi.go` | Busca HTML, episódios, temporadas e players AJAX; aceita `data-embed`/`data-id` e usa o extrator filtrado de player embutido como fallback |
| `internal/providers/otakulogia.go` | Busca GraphQL, detalhes, grupos de temporada, variantes de áudio e verificação de acesso antes de retornar streams |
| `internal/providers/player_candidates.go` | Escopo ao contêiner de player, seleção conservadora de iframes, filtragem de anúncios conhecidos, política de Referer e detecção de intersticial |
| `internal/providers/browser_ad_proxy.go` | Proxy HTTP loopback temporário para navegadores de scraping; bloqueia hosts de anúncios/rastreadores conhecidos e encaminha normalmente o restante |
| `internal/providers/browser.go` | Extração de players após execução de JavaScript; prefere Firefox/GeckoDriver empacotados e usa Chromium como fallback de desenvolvimento |
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
| `internal/integrations/mal_catalog.go` | Descoberta pública MyAnimeList para ranking e temporada, conversão de metadados, cache e rate gate |
| `internal/integrations/accounts.go` | OAuth AniList/MAL/Discord, perfil, logout e sync AniList/MAL; Discord usa PKCE e cofre seguro |
| `internal/integrations/accounts_test.go` | Fixtures HTTP para AniList, OAuth/renovação MAL, OAuth Discord/PKCE, recusa/cancelamento e atualização de progresso |
| `internal/integrations/discord.go` | Rich Presence baseada em estado do MPV, relógio/pausa/seek, conexão e heartbeat |
| `internal/integrations/discord_windows.go`, `discord_unix.go` | IPC Discord por sistema operacional |
| `internal/integrations/anilist_test.go` | Cache/coalescência, consulta de títulos em lote, parcialidade e aliases |
| `internal/integrations/discord_test.go` | IPC simulado, atualização e reconexão |

## Persistência, rede e serviços

| Caminho | Conteúdo |
|---|---|
| `internal/store/store.go` | SQLite, records, cache TTL e cópia de backup |
| `internal/securestore/keyring.go` | Credenciais via cofre do SO: Windows Credential Manager e Linux Secret Service |
| `internal/store/migrate.go` | Importação de JSON/cache da instalação antiga |
| `internal/store/migrate_test.go` | Idempotência, cache legado, imagens e arquivos inválidos |
| `internal/netx/client.go` | Cliente HTTP, JSON, streaming, erros e rate gate |
| `internal/manga/service.go` | MangaDex: descoberta de prateleiras e tags, busca de títulos, capítulos/grupo de tradução, fontes de página validadas e CBZ |
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
| `internal/platform/process_windows.go`, `process_unix.go` | Inicialização de processos sem console; player, atualizador e helper de reinício preservam a visibilidade das janelas gráficas no Windows |
| `internal/platform/process_windows_test.go` | Confirma que `HideConsole` não passa estado `SW_HIDE` ao processo gráfico |
| `internal/platform/reveal_windows.go`, `reveal_other.go` | Abre ou reutiliza a pasta no gerenciador nativo; no Windows localiza e ativa a janela do Explorer |
| `internal/platform/window_position*.go` | Valida posição salva contra as áreas de trabalho dos monitores no Windows; teste da interseção da barra de título |
| `internal/platform/webview.go`, `webview_windows.go`, `webview_other.go`, `webview_runtime_windows_test.go` | Descoberta do WebView2 junto ao executável, configuração do Wails para usar o runtime empacotado, ACL AppContainer e validação pelo loader Wails no Windows |
| `internal/platform/tray_windows.go`, `tray_other.go` | Menu de notificação Windows para abrir, minimizar, ocultar na bandeja, reiniciar e sair; implementação sem ação nas demais plataformas |
| `internal/platform/process_windows.go`, `process_unix.go` | Opções de subprocesso e espera pelo processo anterior durante reinicialização |
| `internal/platform/publish.go` | Publicação de arquivo temporário |
| `internal/platform/publish_test.go` | Não sobrescrever arquivo já existente |
| `internal/update/update.go` | Releases, checksum, staging, substituição e relançamento visível do app |
| `internal/update/parent_windows.go`, `parent_unix.go` | Espera do processo pai por plataforma |
| `internal/update/update_test.go` | Regras de versão, staging e atualização |

## Legado

`Legacy/README.python.md` descreve o arquivo do produto antigo. `Legacy/` contém app Python, testes, recursos de distribuição e assets históricos. O changelog antigo está em `Legacy/CHANGELOG.python.md`. Não execute seus scripts para desenvolver ou distribuir o produto Go.

Para conferir a lista de arquivos após uma mudança, execute `rg --files internal frontend/src cmd deploy/go` na raiz. Este mapa enumera todos os arquivos de código vigentes dessa árvore; resultados novos devem ganhar descrição aqui.

## Artefatos locais e gerados

Pastas como `bin/`, `dist/`, `release/`, `installer/` e partes de `build/` podem conter executáveis, bibliotecas de terceiros, logs, stages ou pacotes produzidos durante desenvolvimento. Elas não substituem os fontes em `internal/`, `frontend/`, `cmd/` e `deploy/go/`. O conteúdo pode variar entre máquinas e não é enumerado arquivo a arquivo neste mapa. Confira `.gitignore` e o script de empacotamento antes de tratar um artefato local como parte do produto.

O arquivo local `frontend/package.json.md5` não está versionado e não tem consumidor encontrado no código atual; não é uma fonte de versão nem uma dependência do runtime.
