# Revisão técnica — AnimeCaos

Revisão base de 20/10/2026; atualização em 21/10/2026 após as releases `v3.0.1` e `v3.0.2`. O escopo inclui os pacotes Windows/Linux com Firefox/GeckoDriver, MPV/FFmpeg/FFprobe e WebView2, CI, instaladores, update e licenças. A revisão original recompilou ZIP, instalador e AppImage; o smoke local passou, mas o instalador não foi executado no perfil de desenvolvimento por já haver uma entrada com o mesmo AppId. Os resultados das releases estão em [Distribuição](DISTRIBUTION.md) e [Testes](TESTING.md). A árvore Python antiga está preservada em `../Legacy/`.

### [P2] Windows sem Authenticode quando não há certificado configurado — risco conhecido

- **Evidência:** o repositório não tem os secrets `WINDOWS_CERTIFICATE_PFX_BASE64` e `WINDOWS_CERTIFICATE_PASSWORD`. O workflow publica ZIP e instalador sem assinatura Authenticode nesse caso e inclui um aviso nas notas e nos arquivos da release.
- **Impacto:** o Windows pode mostrar aviso de editor desconhecido e a primeira execução pode exigir confirmação adicional. A assinatura Sigstore de `SHA256SUMS` autentica o manifesto, não fornece reputação Authenticode aos executáveis.
- **Mitigação:** o atualizador valida o SHA-256 do pacote e a release identifica explicitamente a falta de assinatura. Para retirar esse aviso, será necessário configurar um certificado Authenticode válido nos secrets do GitHub.

### [P1] Pacotes não incluíam todos os runtimes que o app usa — corrigido no stage

- **Evidência:** a configuração anterior podia depender de MPV/FFmpeg no `PATH`, Firefox/GeckoDriver do computador e do WebView2 Evergreen instalado. Isso fazia um app abrir em desenvolvimento e falhar em máquinas sem ferramentas externas.
- **Correção:** o empacotador agora exige MPV, FFmpeg/FFprobe, Firefox e GeckoDriver em `bin/`; Windows também carrega WebView2 Fixed Version junto ao app, selecionado por `WebviewBrowserPath`. O AppImage inclui Firefox, mídia e suas bibliotecas GTK/WebKitGTK selecionadas. O helper Windows configura ACL de leitura AppContainer uma vez no primeiro início para cobrir Windows 10 e ZIP portátil.
- **Validação:** o stage Windows passou no Firefox/GeckoDriver com iframe dinâmico e MPV com seek; Wails reconheceu WebView2 155.0.4283.62 dentro do stage. O AppImage final passou no Ubuntu 24.04/WSL: Firefox/GeckoDriver extraídos da imagem executaram a fixture Selenium, MPV fez decode/seek e o smoke abriu, atualizou e preservou o banco.
- **Limite:** a instalação offline do Windows ainda precisa ser verificada em VM limpa, e a validação do AppImage precisa ser repetida numa VM/instalação Linux limpa. Os runtimes fixos exigem atualização e revalidação a cada release; workflows remotos e assinatura dos artefatos ainda dependem de credenciais e configuração.

### [P1] linuxdeploy alterava os binários de Firefox e GeckoDriver — corrigido no empacotamento AppImage

- **Evidência:** a imagem extraída continha GeckoDriver estático com RPATH modificado; o executável de 0,37.1 retornava `SIGSEGV`, embora a cópia do stage funcionasse. `linuxdeploy` também reescrevia o launcher/binário Firefox durante a coleta.
- **Impacto:** a aplicação Linux não conseguiria iniciar scraping dinâmico apesar de carregar Firefox e GeckoDriver dentro do AppImage.
- **Correção:** o script guarda as cópias upstream, executa a coleta de dependências e licenças, restaura Firefox/GeckoDriver sem alterações, verifica os bytes e empacota o AppDir com o `appimagetool` incluído na ferramenta, sem uma segunda varredura.
- **Cobertura:** `verify-appimage.sh` extrai e testa Firefox/GeckoDriver do próprio artefato, executa iframe JavaScript e MPV, abre o app, aplica update e confirma que `state.db` mantém o hash.
- **Limite:** a verificação ocorreu em Ubuntu 24.04/WSL; a VM limpa ainda precisa ser testada.

## Achados corrigidos nesta etapa

### [P1] Janela de vídeo do MPV podia iniciar oculta no Windows — correção publicada na v3.0.1; validação visual pendente

- **Evidência:** `internal/player/player.go` iniciava o MPV com `platform.Hide`. No Windows, esse helper define `HideWindow`, que configura a primeira janela gráfica do processo para `SW_HIDE`; o player ainda pode decodificar áudio e responder pelo IPC sem exibir o vídeo.
- **Impacto:** a interface do AnimeCaos continua mostrando o episódio e o progresso, mas o usuário só ouve o áudio e não vê a janela separada do MPV.
- **Correção:** o player agora usa `HideConsole`, que mantém `CREATE_NO_WINDOW` para não abrir console e não altera o estado inicial das janelas gráficas. O MPV/DLLs já são incluídos pelos pacotes de distribuição.
- **Limite:** a release `v3.0.1` publicou a correção e os testes automatizados passaram. O teste MPV automatizado usa saída nula, então a janela ainda precisa de validação manual numa execução Windows empacotada. A atualização de uma instalação real `v3.0.0` para `v3.0.1` também não foi observada ponta a ponta.

### [P1] O atualizador podia deixar a interface do AnimeCaos oculta no Windows — corrigido na v3.0.2

- **Evidência:** o helper de update e o relançamento após “Reiniciar” iniciavam o executável Wails com `platform.Hide`, que ativa `STARTF_USESHOWWINDOW/SW_HIDE`. A instância podia permanecer ativa sem apresentar sua janela.
- **Correção:** ambos usam `platform.HideConsole`, que evita uma janela de console sem passar estado oculto ao processo gráfico. Um teste Windows confirma esses atributos de inicialização.
- **Limite:** o teste de atributos não substitui a inspeção visual de uma instalação empacotada. Usuários que ficaram com uma instância oculta precisam encerrá-la e instalar manualmente a v3.0.2 uma vez, pois o helper da v3.0.1 é o código que executa o primeiro relançamento.

### [P2] Encerramento curto podia marcar episódio como assistido na sincronização — corrigido

- **Evidência:** `internal/player/player.go` definia `Watched` depois de 30 s de processo ativo, sem considerar duração ou posição do vídeo. `syncWatched` então gravava o número inteiro do episódio no AniList/MAL.
- **Impacto:** fechar um episódio logo no início podia avançar a lista externa como se ele tivesse sido assistido.
- **Correção:** só EOF natural ou posição de pelo menos 80% de duração conhecida produz estado `Watched`; sem duração, parar manualmente não sincroniza.
- **Cobertura:** `TestEpisodeWatchedRequiresEOFOrEightyPercent`, `TestSyncUpdatesMALListAtWatchThreshold`, `TestSyncMarksAniListCompleteOnlyAtFinalEpisode` e teste DOM das ações AniList/MAL.
- **Limite:** autenticação e escrita em conta externa real não foram feitas nesta execução.

### [P1] Leitor de mangá podia ficar sem resposta quando a fonte de páginas falhava — corrigido

- **Evidência:** a busca MangaDex vazia era disparada ao abrir a página; falha em `Pages` deixava o leitor sem um estado final visível, sem retry e sem navegação de capítulo. A interface não oferecia modo de página única, RTL/LTR ou indicação do grupo de tradução.
- **Impacto:** a pesquisa podia aparecer vazia sem ação do usuário e um erro de atribuição MangaDex@Home parecia uma tela eternamente carregando, impedindo iniciar/retomar a leitura.
- **Correção:** busca passou a ser sob demanda; o leitor mostra erro recuperável e pede nova atribuição ao repetir, valida listas `data`/`data-saver`, persiste progresso com debounce e oferece modos/controles de leitura e navegação de capítulo. O parser conserva crédito de grupos quando presente no feed.
- **Cobertura:** fluxo DOM de busca → capítulo → página, erro/retry, fixture de grupo e página apenas `data-saver`; live MangaDex de One Piece leu/baixou 53 páginas para CBZ.
- **Limite:** não houve inspeção gráfica da janela Wails nesta execução; a superfície de automação de tela não iniciou. Retomada de capítulo CBZ segue coberta apenas pelo contrato existente, não por jornada visual manual.

### [P1] Janela iniciava fora da tela após minimizar — corrigido

- **Evidência:** a janela Wails permanecia com processo responsivo e título `AnimeCaos`, mas seu retângulo era `-32000,-32000`, coordenada de janela minimizada no Windows. O `OnBeforeClose` persistia essa posição e o próximo início reaplicava como posição normal; por isso havia miniatura na barra, mas nenhuma janela visível.
- **Impacto:** o usuário não conseguia reabrir o app clicando no ícone da barra de tarefas, apesar de o processo continuar ativo.
- **Correção:** a restauração enumera as áreas úteis de todos os monitores e reaplica uma posição apenas quando uma parte utilizável da barra de título está visível. Caso contrário, centraliza. O fechamento pelo X oculta na bandeja; o menu oferece abrir, minimizar, ocultar e sair. O app não grava geometria enquanto minimizado ou fora dos monitores.
- **Limite:** a bandeja está implementada nesta etapa apenas no Windows; Linux e macOS mantêm o ciclo de janela nativo.

### [P1] Alias genérico escondia adaptação reproduzível no catálogo — corrigido

- **Evidência:** a busca live `hunter` recebia da Otakulogia o título principal `HUNTER × HUNTER (2011)` e o alias `Hunter x Hunter`. A correspondência agregava o título principal da versão 2011 e o alias da versão 1999, marcava o ID como ambíguo e depois rejeitava o resultado. O histórico local registra reprodução da Otakulogia até 495 s; na validação desta correção, os streams do E1 passaram pela validação HTTP.
- **Impacto:** a busca podia mostrar só a adaptação de 1999, embora a versão de 2011 ainda tivesse E1 reproduzível.
- **Correção:** o título principal do provedor agora é comparado primeiro; aliases só entram quando esse título não resolve a identidade. A consulta live passou a retornar 1999 e 2011 em cards separados; fixture protege contra misturar os remakes.
- **Limite:** a consulta atual identificou a qualidade dos dois E1 como desconhecida; não houve MPV nesta revalidação.

### [P1] Busca por idioma não encontrava a mesma obra nem deduplicava provedores — corrigido

- **Evidência:** `internal/providers/catalog.go` fazia busca textual igual nas fontes e `SameTitle` só comparava títulos normalizados. O modelo AniList anterior não incluía `title.native` nem `synonyms`. A API AnimeFire retorna o mesmo ID para “Kimetsu no Yaiba” e “Demon Slayer”, mas não para a consulta japonesa `鬼滅の刃`.
- **Impacto:** título em outro idioma resultava em catálogo vazio ou duplicado; pesquisa na home não podia manter identidade canônica.
- **Correção:** metadados agora incluem título nativo e sinônimos; a busca consulta um conjunto limitado de aliases, associa ID canônico somente por igualdade não ambígua e agrupa resultados equivalentes em variantes internas. Se o título regional não estiver indexado na AniList, a busca resolve nomes alternativos encontrados no primeiro resultado do catálogo e repete a consulta expandida. Similaridade textual só ordena e remove resultados muito fracos quando há referência canônica; nunca funde identidades.
- **Cobertura:** fixtures verificam expansão japonesa, deduplicação entre fontes, ambiguidade e ordenação fuzzy sem fusão.

### [P1] Clique em destaque da home pulava a escolha de resultados — corrigido

- **Evidência:** `frontend/src/App.tsx` navegava diretamente da home para detalhes usando o item do AniList, sem verificar disponibilidade de episódios nas fontes.
- **Impacto:** o detalhe podia abrir sem opções reproduzíveis e ignorava diferenças de título/temporada das fontes.
- **Correção:** clique em destaque ou card da home abre a busca preselecionada; a busca usa o ID canônico do card, expande aliases e mostra as opções disponíveis antes dos detalhes.
- **Cobertura:** teste React verifica a chamada de busca com o título escolhido e ID preferido.

### [P1] Fonte secundária inventava temporada com base na ordem da lista — corrigido

- **Evidência:** `internal/providers/onlinecc.go` atribuía `season + 1` ao índice de cada `ul.episodios`, mesmo sem nome/numero explícito.
- **Impacto:** agrupamento incorreto ou aparente temporada em especiais e alterações na ordem HTML.
- **Correção:** extrai número do cabeçalho `.se-q .se-t`; sem número explícito, grava temporada `0` (indisponível). O número de episódio vem do marcador do item ou do título; não usa o índice do item como substituto. A tela agora mostra “Sem temporada informada” e não renderiza números zero como valores reais.
- **Cobertura:** fixture confirma temporada/episódio explícitos e que ausência de metadados não produz valores inventados.

### [P2] Resultados internos expunham o nome da fonte na interface — corrigido

- **Evidência:** cards e detalhes renderizavam `anime.provider`; a navegação também listava fontes ativas e desativadas.
- **Impacto:** violava a regra de uma experiência uniforme e expunha detalhes de integração em fluxos comuns.
- **Correção:** rótulos removidos dos cards, detalhes e navegação; identificadores seguem no backend e no diagnóstico. Warnings de busca permanecem genéricos.
- Mensagens comuns também removem hosts/nomes de fonte; logs completos continuam restritos à área de diagnóstico.
- **Cobertura:** teste React garante ausência dos nomes de fontes na navegação inicial.

### [P2] Resultados de busca não tinham variantes independentes na seleção de detalhes — corrigido

- **Evidência:** cada resultado apontava para uma fonte, e a tela de detalhes usava apenas aquela listagem. Em Jujutsu Kaisen, AnimeFire fornece 59 episódios com temporada 1, enquanto a fonte secundária fornece grupos explícitos 1, 2 e 3.
- **Impacto:** uma fonte podia ocultar estrutura de temporadas disponível na outra.
- **Correção:** identidade canônica mantém variantes separadas; detalhes consultam cada variante e escolhem o conjunto com mais temporadas explícitas, desempate por quantidade de episódios. IDs e episódios não são combinados entre fontes.
- **Limite:** caso as duas fontes discordem sobre um mesmo grupo, ainda é necessário preferir a informação verificável da fonte escolhida; não há algoritmo que prove que episódios de IDs diferentes são equivalentes.

### [P2] Download podia marcar arquivo vazio existente como concluído — corrigido

- **Evidência:** `internal/downloads/queue.go` tratava qualquer destino existente como concluído sem verificar tamanho; temporadas/números desconhecidos também colidiam em `S00E0`.
- **Impacto:** arquivos vazios bloqueavam uma nova tentativa e episódios com identidade incompleta podiam sobrescrever/duplicar o mesmo caminho.
- **Correção:** arquivo existente só é reaproveitado se tiver conteúdo; arquivo vazio é removido antes de repetir. Para identificação incompleta, nome usa `??` e sufixo curto derivado do ID estável do episódio; nomes conhecidos mantêm o padrão anterior.
- **Cobertura:** `internal/downloads/queue_test.go` cobre duplicados, cancelamento e publicação; nomes com identidade incompleta ainda não têm fixture isolada.

## Achados corrigidos na execução dos documentos

### [P1] Fonte secundária não oferecia seleção de áudio — corrigido

- **Evidência nova:** a página de episódio separa `Dublado` e `Legendado` em abas com IDs de contêineres e iframes próprios.
- **Correção:** `OnlineCC.Resolve` associa cada rótulo ao player correspondente e tenta resolver cada stream individualmente; se nenhuma aba resolver, usa o caminho de player único. A escolha de áudio agora ignora caixa e aceita correspondência textual.
- **Cobertura:** fixture confirma dois manifests HLS resolvidos com áudio dublado/legendado preservado.
- **Limite:** disponibilidade real dos players depende do episódio; falha de uma aba não invalida uma alternativa que resolva.

### [P1] Busca da fonte secundária dependia de seletor HTML estreito — corrigido

- **Correção:** busca agora cobre variações comuns de cards, links de série, capas lazy-load e remove duplicatas por URL. Paginação segue detectada pelos links `next`.
- **Cobertura:** fixture simula dois formatos de card e paginação.
- **Limite:** mudanças estruturais futuras ainda devem ser monitoradas em consulta real para distinguir catálogo vazio de markup desconhecido.

### [P2] Sistema visual não estava implementado — implementado

- **Correção:** a interface usa a logo AnimeCaos, splash com versão, temas claro/escuro/sistema, skeletons, tokens monocromáticos com acento vermelho, estados focados e regras responsivas para navegação compacta, fila e player. Contas e diagnóstico agora ficam dentro de Configurações.
- **Cobertura:** teste React verifica tema padrão e opções. CSS respeita `prefers-reduced-motion`.
- **Limite:** não houve build nem inspeção visual em janela empacotada, conforme instrução para adiar builds.

### [P2] Downloads diretos usavam `http.DefaultClient` — corrigido

- **Correção:** fila injeta o cliente de transferência `netx.Client.Stream`, que aplica User-Agent, contexto, timeout de conexão/cabeçalhos e tentativas GET limitadas para falha de conexão/HTTP 5xx. Não reinicia transferências após começar a gravação do corpo.
- **Limite:** a política de tentativa após bytes recebidos não faz retomada automática, para evitar publicar conteúdo duplicado ou corrompido.

## Revisão complementar de interface

### [P1] Streams expirados eram enviados ao player sem validar uma alternativa — corrigido

- **Evidência:** antes da correção, `Service.Play` entregava o stream escolhido ao player sem verificar se a playlist de qualidade existia. Um manifesto removido podia produzir HTTP 404 no MPV, e a fonte secundária não era consultada.
- **Correção:** resolução valida HLS e prefere a maior variante acessível; diante de falha, busca correspondência de título/alias exata na outra fonte. Usa temporada e número explícitos quando coincidem; sem esse par, aceita apenas um título de episódio normalizado e único, inclusive quando os grupos de temporada divergem. A seleção também é usada pelo resolver comum da fila de downloads.
- **Cobertura automatizada:** teste garante fallback para um stream válido após 404 e testes do catálogo impedem associação por posição ou episódio ambíguo.
- **Verificação manual na interface em 17/10/2026:** 20 títulos abriram o MPV e avançaram a posição; a lista e o método estão em `docs/TESTING.md`. Também houve HTTP 404 em títulos fora desse conjunto. Com a validação atual, esses erros acontecem antes de iniciar o MPV; o fallback só é aceito quando a correspondência de título e episódio é segura.

### [P2] Teste live considerava qualquer URL resolvida como mídia reproduzível — corrigido

- **Evidência:** `TestLiveCatalogSearchAndEpisodeGroups` parava quando o adaptador retornava uma URL. O resultado podia ser contado como sucesso mesmo se a URL respondesse 404 ao carregar a playlist.
- **Correção:** o teste agora chama `media.Best` para HLS e `media.Validate` para arquivos diretos. Amostra os cinco primeiros itens, um do meio e o mais recente, porque o servidor remoto informa manutenção com disponibilidade concentrada em episódios novos.
- **Verificação ao vivo em 17/10/2026:** Hunter x Hunter (2011) retornou URLs AnimeFire para sete amostras, mas todas as playlists deram 404; a fonte secundária falhou no episódio 1 e abriu o episódio 2. One Piece teve 404 nas amostras antigas e manifesto HLS acessível na mais recente. O registro completo e os limites estão em `docs/TESTING.md`.
- **Mensagem de erro:** um 404 ao buscar a playlist agora informa que o servidor de vídeo não encontrou o arquivo do episódio, para distinguir esse caso de uma falha de leitura do manifesto. `TestBestExplainsMissingManifestAsRemote404` cobre o texto.

### [P2] Controles de player antigo permaneciam visíveis após encerrar a sessão — corrigido

- **Evidência:** depois de fechar uma reprodução, a interface podia conservar os controles da sessão anterior enquanto tentava iniciar outro episódio. Uma falha de resolução deixava os controles antigos ao lado do erro novo.
- **Correção:** `PlayerCommand("stop")` invalida a sessão, cancela a seleção pendente, libera o stream e publica estado vazio. Ao substituir uma sessão já encerrada, `Service.play` também limpa o player antes de resolver o próximo stream; o frontend interpreta o estado vazio removendo os controles.
- **Cobertura:** `TestStoppingPlayerClearsThePublishedSession` em `internal/app/service_test.go`.

### [P2] O catálogo pode manter episódios cujo arquivo remoto está indisponível — confirmado nas amostras

- **Evidência:** o catálogo AnimeFire retornou `is_offline=false` e URLs para as amostras de Hunter x Hunter e One Piece; pedidos às URLs de episódios antigos responderam HTTP 404. A amostra mais recente de One Piece retornou HLS válido. O bundle atual do site comunica manutenção do servidor de vídeo e disponibilidade temporária de episódios novos.
- **Impacto:** o título, a temporada e o episódio aparecem no catálogo, mas a opção não inicia quando as fontes não entregam mídia válida.
- **Tratamento atual:** validação prévia de HLS, seleção de variante acessível e tentativa de outra fonte quando existe uma correspondência segura. O app mostra erro por episódio quando não há stream acessível.
- **Limite:** os resultados variam por episódio e podem mudar sem alteração do app. Esta evidência não estabelece que todos os episódios antigos estejam indisponíveis; ela confirma apenas as amostras citadas em `docs/TESTING.md`. Não foi demonstrada falha de decodificação para as URLs testadas.

### [P2] Scraping dinâmico AnimesOnlineCC depende de navegador instalado — confirmado

- **Evidência:** páginas de episódio podem inserir o `iframe.src` após executar JavaScript; o scraper HTTP sozinho não enxerga essa mudança.
- **Tratamento atual:** quando o scraping estático não resolve, `browser.go` executa a página em Chromium ou Selenium/Firefox, lê `iframe`/`video` e a configuração JWPlayer, e valida mídia antes do MPV. `ANIMECAOS_BROWSER_PATH`, `ANIMECAOS_GECKODRIVER_PATH` e `ANIMECAOS_FIREFOX_PATH` configuram os binários.
- **Verificação em 18/10/2026:** fixtures locais confirmam iframe JavaScript e player HTML5 silenciado. O E2E MPV passou em Naruto Shippuden E1 e Hunter x Hunter (2011) E2, com H.264/AAC, dimensões, avanço e seek. No Hunter E1, a resposta do RPC Blogger foi `payload=null` e Firefox/Chrome não expuseram mídia antes do timeout; a busca agregada usou E1 validado pela Otakulogia.
- **Limite:** se não houver browser configurado/instalado, ou o site mudar o player, a etapa dinâmica falha com erro controlado. O embed Anidrive inspecionado pela Firefox mais recente expôs apenas um clipe sem áudio e foi rejeitado; a validação live de outros episódios/hosts não garante a disponibilidade futura. A amostra Hunter E1 confirma uma limitação dessa página, não de todos os episódios da fonte.

### [P2] Iframes de anúncio e redirects podiam ser confundidos com o player — corrigido para hosts conhecidos

- **Evidência:** em uma página de player inspecionada no Firefox, um intersticial substituiu o iframe legítimo e trackers como `t.dtscout.com` e `crwdcntrl.net` apareceram fora do contêiner de reprodução. A extração antiga podia percorrer iframes da página inteira. O cliente HTTP também seguia redirects antes de inspecionar o destino.
- **Correção:** extratores HTML/JavaScript priorizam raízes de player, ignoram wrappers de anúncio e descartam candidatos genéricos ambíguos. Chromium e Firefox usam um proxy local temporário que bloqueia hosts de anúncio/rastreamento conhecidos; Firefox ativa proteção contra rastreamento e bloqueio de pop-ups automáticos. Cliente HTTP, validação de mídia e gateway interrompem redirects para a mesma lista. Intersticiais reconhecidos falham fechados sem abrir links publicitários.
- **Verificação em 18/10/2026:** fixtures de iframe/player, proxy HTTP/CONNECT, redirects, `no-referrer`, JWPlayer e HTML5 passaram. E2E MPV confirmou SushiAnimes e Otakulogia em Hunter E1, além de AnimesOnlineCC em Naruto E1 e Hunter E2; Hunter E1 da AnimesOnlineCC ainda não oferece rendition Blogger. AnimeFire retornou HLS 404 na amostra anterior.
- **Limite:** a lista é por hostname e finita. A auditoria não remove um intersticial incorporado pelo site. Hosts publicitários novos/rotativos podem exigir atualização da lista.

### Estado dos itens solicitados em 17/10/2026

Os pontos visuais desta sequência foram conferidos em `App.tsx` e `style.css` e ganharam testes de interface quando aplicável:

- **Prévia recortada pelo carrossel — corrigido.** O `overflow-y: hidden` da rail cortava o painel de hover mesmo com `z-index`. O painel agora é portal em `document.body`, usa posição viewport-fixed, reposiciona em scroll/resize e aceita o cursor durante a transição.
- **Controle de sidebar indisponível — corrigido no layout.** O botão estava oculto abaixo de 760 px e tinha margem negativa no desktop. Há agora um controle no cabeçalho compacto e outro junto à marca no desktop, com transições e preferência persistida. Teste DOM verifica o estado persistido; visibilidade geométrica precisa ser validada na janela real.
- **Ação do destaque e carrosséis — atualizado.** Hero usa ícone play e rótulo “Assistir”; setas de rail e teclado continuam disponíveis. A ação busca as opções do anime, não inicia playback sem seleção.
- **Ícone Wails — corrigido e verificado no executável de distribuição.** A compilação anterior usava `go build` diretamente e não gerava os recursos PE do Wails. `cmd/package` agora chama a CLI Wails na versão fixada pelo módulo para compilar o executável Windows, incorporando ícone, manifesto e metadados. Em 19/10/2026, o ícone associado ao executável do novo ZIP foi extraído e comparado visualmente com a marca; o stage usado no instalador contém o mesmo executável. O instalador foi compilado pelo Inno Setup 6.7.1 oficial. A instalação e inspeção da janela em uma VM limpa ainda não foram feitas.
- **Capa antiga/histórico.** O importador aproveita cache AniList/imagens legadas e o serviço permite salvar a capa recuperada. O código tem testes de cache e persistência; não foi repetida uma migração sobre diretório real de usuário nesta revisão.

Os itens visuais acima descrevem a implementação e a validação registrada. A checagem do ícone extraído confirma o recurso PE do executável empacotado, mas não substitui uma instalação limpa para verificar título, barra de tarefas e atalhos no Windows.

## Achados pendentes

### [P2] Login Discord e Rich Presence ainda dependem de configuração e validação no Developer Portal — pendente

- **Evidência em 20/10/2026:** fixtures locais validam o callback OAuth com PKCE, leitura do perfil, cofre de credenciais e payload de Rich Presence; nenhuma autorização real nem inspeção em cliente Discord Desktop foi feita nesta rodada. O guia de cliente público do Discord demonstra a troca via SDK `Client::GetToken`; a chamada HTTP equivalente do adaptador Go ainda precisa de confirmação live.
- **Impacto:** se o Developer Portal não tiver o callback local `http://127.0.0.1:9744/`, o cliente público habilitado e a arte `logo`, o vínculo ou a imagem da presença não funcionarão corretamente.
- **Encaminhamento:** configurar nome/ícone, habilitar cliente público e cadastrar o callback exato; enviar a arte `logo`; testar autorização, reprodução, pausa, seek e parada em um Discord Desktop com compartilhamento de atividade habilitado. Se a troca HTTP for recusada, substituir por `Client::GetToken` via SDK oficial ou por um backend confidencial sem distribuir segredo no app. A conta Discord apenas identifica o perfil; progresso de episódios continua nas integrações AniList/MAL.

### [P2] Credenciais de contas em instalações antigas no SQLite — mitigado no caminho ativo; revisão de release pendente

- **Evidência atual:** tokens AniList/MAL e Client Secret MAL novos são gravados em `internal/securestore` via Windows Credential Manager ou Linux Secret Service. A migração legacy grava primeiro no cofre e só então apaga a linha antiga com `secure_delete`, checkpoint e `VACUUM`; testes verificam os dois caminhos.
- **Limite:** cópias do diretório de dados, snapshots/backup anteriores e o Client Secret MAL que foi compartilhado fora do banco ativo não podem ser limpos pelo app. O cofre Linux precisa estar desbloqueado/disponível. Não foi validada ainda uma conta real em cada sistema operacional.
- **Ação de publicação:** rotacionar no painel MyAnimeList o segredo exposto durante o suporte; remover a cópia antiga de backups sob controle do usuário; confirmar o cofre Linux em uma sessão gráfica limpa.

### [P2] Teste da home verifica navegação de busca, mas não o ciclo de resultados reais — parcialmente coberto

- **Evidência:** o teste de interface cobre o ID canônico e o início automático da consulta; ainda não cobre card resultante, temporadas expostas em detalhe e retorno ao resultado após voltar.
- **Impacto:** mudanças posteriores podem preservar o primeiro clique e quebrar a seleção ou o histórico de navegação.
- **Encaminhamento:** incluir jornada Search → escolher variante → detalhes → voltar em teste de interface e E2E empacotado quando os builds forem retomados.

### [P2] Revisão do legado Python continua ligada à matriz de paridade — pendente

- **Evidência:** `Legacy/` contém 83 módulos Python e 56 arquivos `test_*.py` (mais `conftest.py`). A matriz ainda lista funcionalidades com estado parcial e itens sem equivalente Go/TS.
- **Impacto:** não é seguro remover ou simplificar o legado antes de mapear cada comportamento residual.
- **Encaminhamento:** continuar a leitura/teste por área, marcar equivalentes em `GO_MIGRATION_MATRIX.md` e manter a árvore de referência intacta até que todos os estados pendentes tenham evidência.

### [P2] Títulos relacionados sem identidade canônica podem aparecer em mais de uma fonte — confirmado

- **Evidência em 18/10/2026:** a busca live `hunter` aprovou dois cards `City Hunter`, um da Otakulogia e outro da SushiAnimes; ambos vieram sem AniList ID. A consulta AniList pelo título não encontrou identidade para essa amostra. Na busca ampla `Tensei Shitara`, Dai Nana Ouji foi consolidado em um card com três fontes após a consulta em lote confirmar o mesmo ID AniList.
- **Impacto:** fundir cards somente pelo texto pode misturar adaptações homônimas; mantê-los separados pode exibir duplicatas quando duas fontes apontam para a mesma obra.
- **Encaminhamento:** manter títulos sem identidade canônica separados até que formato, ano, contagem ou títulos de episódios comprovem equivalência. A publicação em lote e a busca AniList agrupada já foram aplicadas; o fluxo está em `docs/architecture/SEARCH_PIPELINE_PLAN.md`.

### [P2] Numeração de temporada varia entre provedores — risco controlado

- **Evidência em 18/10/2026:** `Tensei Shitara Ken Deshita 2nd Season` só apareceu após pesquisar também o nome base. AnimesOnlineCC, Otakulogia, SushiAnimes e AnimeFire identificaram T2 E1 e passaram no preflight live. O teste MPV decodificou AV1/AAC a 1920×1080, avançou e fez seek.
- **Impacto:** uma fonte que não numera temporadas explicitamente não pode comprovar T2 E1 e ficará oculta para uma consulta sazonal, mesmo que possua a mídia.
- **Encaminhamento:** manter a exigência de número explícito para evitar validar a temporada errada; ampliar o adaptador de uma fonte somente quando houver metadado confiável que relacione seu E1 à temporada solicitada.

### [P1] Preflight não comprova todos os episódios nem todas as fontes — confirmado

- **Implementação:** a busca só retorna cards depois que E1 passa no preflight. Quando FFprobe está disponível (`ANIMECAOS_FFPROBE_PATH`, `PATH` ou `bin` do workspace), arquivos diretos têm codecs e dimensões inspecionados; uma faixa de vídeo sem áudio é rejeitada. O MPV não é aberto por card na busca. Ao tocar, o stream é resolvido novamente e o fallback só pode ocorrer antes de a posição avançar.
- **Evidência atual em 18/10/2026:** a consulta literal `Hunter x Hunter 2011` passou a encontrar a edição correta via expansão do ano e publicou o card após E1 aprovado pela Otakulogia; a edição 1999 ficou separada. O MPV selecionou Otakulogia, decodificou H.264/AAC em 1280×720 e passou avanço/seek. A busca mostrou aviso porque fontes lentas excederam o orçamento. A amostra AnimesOnlineCC Hunter E1 continua indisponível, mas não impede o card quando outra fonte valida esse episódio. A tabela e os comandos estão em `docs/TESTING.md`.
- **Limite:** o selo representa somente o E1 e a resolução máxima validada entre fontes. A ordenação de playback prioriza o áudio configurado e pode selecionar resolução inferior ao selo. A rodada não assistiu episódios completos. A qualidade/servidor remoto pode mudar entre preflight e reprodução.
- **Encaminhamento:** repetir amostras quando os provedores mudarem e manter o estado “indisponível” para títulos sem evidência do episódio 1. Não contar challenge ou URL sem mídia decodificável como sucesso.

## Verificações executadas

### Testes automatizados registrados em 18/10/2026

- `go test ./...` — passou em todos os pacotes após o batching AniList e o cache curto de páginas de catálogo.
- `go test -race ./...` — não executado; `CGO_ENABLED=0` neste ambiente Windows.
- `npm exec -- tsc --noEmit` — passou.
- `npm test -- --run` — primeira execução 19/20; o teste de navegação por teclado passou isolado e a repetição completa passou em 20/20.
- A busca live ampla `Tensei Shitara` levou 6,371 s dentro de `Search` e publicou sete grupos; Dai Nana Ouji ficou em um card com três provedores. A busca sazonal levou 3,45 s e o MPV tocou o E1 em AV1/AAC, 1920×1080, com seek. Estes são exemplos pontuais, não percentis.
- `git diff --check` — passou, com aviso de normalização CRLF em `CHANGELOG.md` e `README.md`.
- A rodada anterior de dez títulos passou com nove reproduções MPV. Testes opt-in também registram a mídia sem áudio rejeitada no embed Anidrive. Comandos e limites estão em `docs/TESTING.md`.
- `wails dev` compilou e abriu o app de desenvolvimento. Não executados: build de distribuição, empacotamento ou instalador.

### Registro live anterior (não reexecutado nesta atualização)

As seguintes observações foram registradas numa rodada anterior e servem como histórico, não como estado verificado hoje:

- As fontes responderam a consultas de Demon Slayer, Frieren, Solo Leveling, Jujutsu Kaisen e One Piece; contagens/agrupamentos variaram entre provedores.
- O parser/resolvedor secundário retornou 404 para algumas páginas de episódio, e pesquisa por “Demon Slayer” chegou a apresentar Berserk sem referência canônica; a busca por alias expandido e filtro fraco foram adicionados em resposta.
- Login em conta real AniList/MyAnimeList ainda não foi executado. O fluxo MAL chegou à página de login, mas a troca do código falso retornou `invalid_client` sem Client Secret. Os campos de credencial de desenvolvedor foram removidos da UI; antes da publicação, o cadastro precisa funcionar como cliente público para desktop ou a troca deve passar por um serviço seguro. Consulte o registro de integrações em `docs/TESTING.md`.

Consulte `docs/TESTING.md` para os comandos opt-in. Atualize esta seção somente depois de rodar de novo e registrar o dia, ambiente e resultado real.

### Integrações de conta — validação local em 19/10/2026

- `go test ./... -count=1` — passou em todos os pacotes.
- `cd frontend; npm exec -- tsc --noEmit` — passou.
- `cd frontend; npm test -- --run` — primeira execução 26/27 por falha intermitente no teste de setas do destaque; repetição completa passou em 27/27 e o teste isolado de setas também passou.
- `go env CGO_ENABLED` — retornou `0`; `go test -race ./...` não foi executado porque CGO está desabilitado.
- `git diff --check` — passou; Git emitiu somente avisos de normalização LF/CRLF nos arquivos modificados.
- As mutations do AniList e as operações MAL usam fixtures locais; nenhuma conta real foi autorizada ou alterada nesta rodada.
