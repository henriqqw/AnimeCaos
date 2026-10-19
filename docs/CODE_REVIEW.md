# Revisão técnica — AnimeCaos

Data: 18/10/2026. Escopo desta etapa: backend Go, interface React/TypeScript, busca com disponibilidade, scraping/MPV, fila de downloads e legado Python mantido como referência. `wails dev` foi executado para reiniciar o app após as mudanças; não houve build de distribuição nem empacotamento. A árvore antiga está preservada em `../Legacy/`.

## Achados corrigidos nesta etapa

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
- **Ícone Wails — fonte atualizada, binário pendente.** `build/appicon.png` e `build/windows/icon.ico` agora são cópias da marca e foram liberados de `build/` no `.gitignore`. O executável não foi reconstruído nesta etapa; o ícone mostrado por um binário já existente não muda e a incorporação efetiva ainda precisa de validação quando builds forem retomados.
- **Capa antiga/histórico.** O importador aproveita cache AniList/imagens legadas e o serviço permite salvar a capa recuperada. O código tem testes de cache e persistência; não foi repetida uma migração sobre diretório real de usuário nesta revisão.

Esse trecho registra o estado de código. Não é uma inspeção visual de um executável empacotado.

## Achados pendentes

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
- Login MyAnimeList foi adiado pelo usuário após erro `invalid_client` na troca de token; não marcar autenticação como validada.

Consulte `docs/TESTING.md` para os comandos opt-in. Atualize esta seção somente depois de rodar de novo e registrar o dia, ambiente e resultado real.
