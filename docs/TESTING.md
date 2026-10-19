# Testes e validação

## Comandos locais

Na raiz:

```powershell
go test ./...
go test -race ./...
```

Frontend:

```powershell
cd frontend
npm ci
npm exec -- tsc --noEmit
npm test -- --run
```

`npm run build`, `wails build` e `go run ./cmd/package` compilam partes do produto. Os comandos de teste acima não geram instalador. Execute builds somente quando a etapa permitir.

## Remoção de integrações de catálogo — 18/10/2026

- `gofmt -w internal/app/service.go internal/providers/browser.go internal/providers/catalog_test.go internal/providers/live_ad_audit_test.go internal/providers/player_candidates.go internal/providers/player_candidates_test.go internal/providers/browser_test.go internal/providers/selenium.go internal/providers/selenium_test.go` — passou.
- `go test ./... -count=1` — passou em todos os pacotes Go.
- A busca textual final pela árvore ativa não encontrou referências aos adaptadores removidos nem aos seus seletores específicos.

## Testes com rede e mídia reais

Os testes live são opt-in, porque dependem de sites, conta, mídia e ferramentas fora do controle do projeto. Confirme a condição diretamente no teste antes de executar:

- `ANIMECAOS_LIVE=1 go test ./internal/providers -run TestLiveCatalogSearchAndEpisodeGroups -count=1 -v`: consulta os catálogos reais e verifica a mídia retornada. O teste tenta os cinco primeiros itens, um do meio e o mais recente; um URL encontrado não conta como episódio reproduzível.
- `ANIMECAOS_LIVE=1 go test ./internal/app -run TestLiveMultilingualSearchKeepsCanonicalIdentity -count=1 -v`: consulta busca multilíngue e metadados.
- `ANIMECAOS_LIVE=1 go test ./internal/app -run TestLivePlaybackUsesAvailableVariant -count=1 -v`: valida manifesto/stream e tentativa de episódio equivalente em outra fonte. Aceita `ANIMECAOS_LIVE_TITLE` para escolher um título; sem variável, usa Demon Slayer.
- `ANIMECAOS_LIVE=1 go test ./internal/manga -run TestLiveMangaDex -count=1 -v`: consulta MangaDex.
- `ANIMECAOS_PLAYER_TEST=1 go test ./internal/player -run TestMPVIntegration -count=1 -v`: exige MPV, FFmpeg e ambiente com saída audiovisual.
- `ANIMECAOS_MEDIA_TEST_FILE=<arquivo>` habilita o teste de mídia local quando suportado pelo teste.

Encontrar/baixar um manifesto HLS não comprova reprodução contínua, áudio ou EOF. Reprodução e dependências precisam ser validadas no sistema que será distribuído.

### Regressão da busca `hunter` e prazo do preflight — 18/10/2026

O preflight agora agenda no máximo dois trabalhos por provedor dentro do pool global de seis; workers não ficam bloqueados esperando vaga da mesma fonte. Ao atingir o limite de 12 s do lote, a busca retorna os cards cujo preflight já passou e mantém ocultos os candidatos pendentes. O resumo incompleto não entra no cache.

| Comando | Resultado |
|---|---|
| `go test ./internal/app -run 'TestSearchAvailabilityKeepsVerifiedCardsWhenPageDeadlineExpires\|TestSearchAvailabilityDoesNotLetOneProviderStarveOthers\|TestSearchAvailabilityCancellationEmitsNoUnverifiedCards\|TestSearchAvailabilityLimitsChecksPerProviderToTwo' -count=1 -v` | Passou: preservação de card válido, justiça entre provedores, cancelamento e limite de concorrência |
| `$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_LIVE_TITLE='hunter'; go test ./internal/app -run '^TestLiveSearchAvailabilityTenAnimeSamples$' -count=1 -v` | Passou: `Search` levou 15,147 s, avisou que a validação atingiu o limite e publicou nove cards com E1 aprovado, incluindo Hunter x Hunter 1999/2011 e City Hunter; qualidade permaneceu não identificada |
| `go test ./...` | Passou em todos os pacotes Go |
| `go env CGO_ENABLED` | Retornou `0`; `go test -race ./...` não foi executado porque CGO está desativado |
| `git diff --check -- internal/app/availability.go internal/app/availability_test.go internal/app/service.go docs/architecture/SEARCH_PIPELINE_PLAN.md docs/PRODUCT_FLOWS.md docs/GO_MIGRATION_MATRIX.md docs/TESTING.md CHANGELOG.md` | Sem erros de whitespace; Git avisou apenas sobre normalização LF/CRLF no `CHANGELOG.md` |

## Execuções desta atualização

Conferidas em 17/10/2026:

| Comando | Resultado |
|---|---|
| `go test ./...` | Passou em todos os pacotes |
| `go test -race ./...` | Não executado: `CGO_ENABLED=0` neste ambiente Windows |
| `ANIMECAOS_LIVE=1 go test ./internal/providers -run TestLiveCatalogSearchAndEpisodeGroups -count=1 -v` | Passou: 10 combinações de título/provedor; detalhes abaixo |
| `npm exec -- tsc --noEmit` | Passou |
| `npm test -- --run` | Passou: 18 testes de `App.test.tsx` |
| `git diff --check` | Passou; houve apenas avisos de normalização de fim de linha em arquivos preexistentes |

Na alteração iniciada em 17/10/2026 e validada em 18/10/2026, `gofmt` foi aplicado aos arquivos Go alterados, `go mod tidy` terminou sem erro e `git diff --check` não encontrou erros de whitespace. A suíte Go completa e os testes live listados abaixo foram executados; o live de catálogo terminou com falha intencional de disponibilidade: AnimeFire retornou 404/sem URL em 9 dos 10 títulos amostrados.

O teste DOM do histórico cobre a paginação em grupos de 24 itens, o intervalo exibido e a navegação para a página seguinte.

### Ícone de play no Histórico — 18/10/2026

| Comando | Resultado |
|---|---|
| `cd frontend; npm exec -- tsc --noEmit` | Passou |
| `cd frontend; npm test -- --run` | Passou: 23 testes, incluindo a retomada pelo ID salvo e a presença do ícone de play no Histórico e em “Continuar assistindo” |

O teste DOM da busca mantém a chamada pendente para verificar os oito skeletons, o indicador acessível, o cancelamento e o descarte de uma resposta que chega depois do cancelamento.

### Skeleton e carregamento da busca — validação em 18/10/2026

| Comando | Resultado |
|---|---|
| `cd frontend; npm exec -- tsc --noEmit` | Passou |
| `cd frontend; npm test -- --run` | Passou: 22 testes, incluindo cancelamento, resposta atrasada e carregamento da próxima página |

### Paginação do histórico — validação em 18/10/2026

| Comando | Resultado |
|---|---|
| `cd frontend; npm exec -- tsc --noEmit` | Passou |
| `cd frontend; npm test -- --run` | Passou: 19 testes, incluindo paginação de 24 itens por página |

### Validação da paginação do histórico — 18/10/2026

| Comando | Resultado |
|---|---|
| `cd frontend; npm exec -- tsc --noEmit` | Passou |
| `cd frontend; npm test -- --run` | Passou: 19 testes, incluindo paginação com 24 itens por página |

### Rodada live de scraping e fallback em 18/10/2026

Comando: `ANIMECAOS_LIVE=1 go test ./internal/providers -run TestLiveCatalogSearchAndEpisodeGroups -count=1 -v`. O teste consultou os 10 títulos abaixo diretamente em AnimeFire e AnimesOnlineCC. Em cada página de episódio AnimesOnlineCC, Chromium headless abriu o player renderizado; os episódios amostrados de cada título incluíram ao menos uma mídia que passou `media.Validate` ou `media.Best`.

| Anime | AnimeFire | AnimesOnlineCC |
|---|---|---|
| Demon Slayer | As amostras iniciais responderam HTTP 404 | Episódio 1 validou como arquivo |
| Frieren | As amostras responderam HTTP 404 | Episódio 1 validou como arquivo |
| Solo Leveling | As amostras responderam HTTP 404 | Episódio 1 validou como arquivo |
| Jujutsu Kaisen | As amostras responderam HTTP 404 | Episódio 1 validou como arquivo; a primeira aba Blogger não tinha renditions |
| One Piece | HLS acessível na amostra do meio (episódio 25) | Episódios 835–838 sem rendition Blogger; episódio 839 validou como arquivo |
| Hunter x Hunter (2011) | As amostras responderam HTTP 404 | Episódio 1 sem rendition Blogger; episódio 2 validou como arquivo |
| Naruto Shippuden | Os episódios amostrados estavam indisponíveis na API | Episódio 1 validou como arquivo |
| Death Note | As amostras responderam HTTP 404 | Episódio 1 validou como arquivo; opção Blogger sem renditions foi ignorada |
| Boruto | As amostras responderam HTTP 404 | Episódio 1 validou como arquivo |
| Chainsaw Man | As amostras responderam HTTP 404 | Episódio 1 validou como arquivo |

O comando completo retornou `FAIL` pelos subtestes AnimeFire que não encontraram mídia acessível; os dez subtestes AnimesOnlineCC passaram. Isso confirma indisponibilidade das amostras remotas consultadas, não erro de decodificação. O matcher do teste live exige que o título corresponda ao início ou ao nome pesquisado, então “Boruto: Naruto Next Generations” não é contado como Naruto.

### Reconsulta live de dez títulos em 18/10/2026

Comando executado nesta revisão: `ANIMECAOS_LIVE=1 go test ./internal/providers -run TestLiveCatalogSearchAndEpisodeGroups -count=1 -v`. Foram consultados os mesmos dez títulos diretamente nos dois adaptadores, com detalhes e episódios; os candidatos do AnimesOnlineCC também passaram pela extração headless de fontes renderizadas por JavaScript e pela validação de arquivo ou manifesto.

| Anime | AnimeFire nesta consulta | AnimesOnlineCC nesta consulta |
|---|---|---|
| Demon Slayer | Amostras responderam HTTP 404 | Episódio 1 validou como arquivo; navegador encontrou duas fontes renderizadas |
| Frieren | Amostras responderam HTTP 404 | Episódio 1 validou como arquivo; navegador encontrou uma fonte |
| Solo Leveling | Amostras responderam HTTP 404 | Episódio 1 validou como arquivo; navegador encontrou duas fontes |
| Jujutsu Kaisen | Amostras responderam HTTP 404 | Episódio 1 validou como arquivo; segunda fonte renderizada resolveu após falha do Blogger |
| One Piece | Episódio 25 validou como HLS; amostras anteriores retornaram 404 | Episódios 835–838 sem rendition Blogger; episódio 839 validou como arquivo |
| Hunter x Hunter (2011) | Amostras responderam HTTP 404 | Episódio 75 validou como arquivo; alguns links temporários falharam por DNS/expiração |
| Naruto Shippuden | API marcou os episódios amostrados como indisponíveis | Episódio 1 validou como arquivo |
| Death Note | Amostras responderam HTTP 404 | Episódio 1 validou como arquivo; opção sem renditions foi ignorada |
| Boruto | Amostras responderam HTTP 404 | Episódio 1 validou como arquivo |
| Chainsaw Man | Amostras responderam HTTP 404 | Episódio 1 validou como arquivo |

O teste terminou com `FAIL` apenas nos nove subtestes AnimeFire sem mídia acessível; os dez subtestes AnimesOnlineCC passaram. O fluxo agregado do aplicativo foi revalidado com `ANIMECAOS_LIVE=1` e `ANIMECAOS_LIVE_TITLE=Demon Slayer`: o primeiro episódio resolveu mídia após a indisponibilidade do catálogo primário. Para `Cyberpunk: Mercenários`, a busca atual do AnimesOnlineCC em `Cyberpunk: Mercenários`, `Cyberpunk: Edgerunners` e `Cyberpunk Edgerunners` não retornou cards. Os caminhos `/anime/cyberpunk-edgerunners/` e `/anime/cyberpunk-edgerunners-dublado/` responderam HTTP 404. Não há variante nessa fonte para mapear com segurança; por isso o erro do AnimeFire não deve ser mascarado por outro título.

Também passaram `ANIMECAOS_LIVE=1 go test ./internal/app -run TestLivePlaybackUsesAvailableVariant -count=1 -v` com `ANIMECAOS_LIVE_TITLE=Demon Slayer` (AnimeFire 404 recuperado pelo AnimesOnlineCC), além da checagem focada do Chromium para Boruto e Naruto Shippuden.

Na execução anterior, o teste live de catálogo contava a obtenção de uma URL como sucesso sem ler o manifesto. A revalidação abaixo fecha essa lacuna. O registro anterior do teste serve como histórico e não representa disponibilidade atual.

## Jornada manual de busca e reprodução

Em 17/10/2026, usei o app de desenvolvimento `AnimeCaos-dev` no Windows como uma pessoa usuária: digitei o título na busca do cabeçalho, escolhi o resultado correspondente, abri os detalhes, selecionei a temporada 1 e o episódio 1 e acionei **Assistir**. Em cada aprovação, confirmei um novo processo MPV, o controle de pausa na interface e a posição do vídeo acima de zero após alguns segundos; depois fechei o player pelo controle do app.

Os 20 títulos distintos que passaram:

| Busca | Resultado aberto | Episódio validado |
|---|---|---|
| Demon Slayer | Demon Slayer: Kimetsu no Yaiba | T1 E1 |
| Jujutsu Kaisen | Jujutsu Kaisen | T1 E1 |
| Solo Leveling | Solo Leveling | T1 E1 |
| Attack on Titan | Attack on Titan | T1 E1 |
| Sousou no Frieren | Frieren e a Jornada para o Além | T1 E1 |
| Spy x Family | SPY x FAMILY | T1 E1 |
| The Apothecary Diaries | Diários de uma Apotecária | T1 E1 |
| Vinland Saga | VINLAND SAGA | T1 E1 |
| Death Note | Death Note | T1 E1 |
| My Hero Academia | My Hero Academia | T1 E1 |
| Chainsaw Man | Chainsaw Man | T1 E1 |
| Haikyuu | HAIKYU!! | T1 E1 |
| Oshi no Ko | Oshi no Ko | T1 E1 |
| Blue Lock | BLUE LOCK | T1 E1 |
| Tokyo Revengers | Tokyo Revengers | T1 E1 |
| Dr. Stone | Dr. Stone | T1 E1 |
| Mushoku Tensei | Mushoku Tensei: Jobless Reincarnation | T1 E1 |
| The Eminence in Shadow | The Eminence in Shadow | T1 E1 |
| Re:Zero | Re:Zero - Começando uma Vida em Outro Mundo | T1 E1 |
| One Punch Man | One-Punch Man | T1 E1 |

Também selecionei Demon Slayer T2 E1 e confirmei avanço no MPV. O teste confirmou início e avanço da reprodução, não a conclusão integral dos episódios, a audição de áudio ou o EOF. Foi feito na sessão de desenvolvimento, não em um pacote instalado; a fonte selecionada não foi registrada para cada título.

### Episódios sem mídia acessível na rodada

Estas falhas foram reproduzidas pelo fluxo da interface. A tentativa de fallback entre fontes não encontrou mídia equivalente acessível nos episódios abaixo:

| Anime | Tentativas | Resultado visível |
|---|---|---|
| One Piece | T1 E1–E3 | Manifesto indisponível, HTTP 404; o catálogo alternativo observado não cobria o início da série com correspondência segura |
| Naruto | T1 E1–E3 | Manifesto indisponível, HTTP 404 |
| Fullmetal Alchemist: Brotherhood | T1 E1 | Manifesto indisponível, HTTP 404 |
| Mob Psycho 100 | T1 E1–E3 | E1: player externo retornou conteúdo não encontrado (404); E2 e E3 não avançaram no MPV |
| Bocchi the Rock | T1 E1–E3 | Manifesto indisponível, HTTP 404 nos três episódios |

Esses 404 indicam mídia ausente no servidor consultado durante a sessão, não um erro de parsing demonstrado. O app conservou os metadados e mostrou o erro do episódio. A disponibilidade pode mudar; repita as tentativas live antes de atribuir um estado permanente à fonte.

Não houve build, empacotamento ou instalação nesta rodada. Para estes testes foram usados `orca` para operar a janela e consultas do estado acessível da interface; nenhum dos arquivos temporários de automação pertence ao produto.

### Checagem live separada por fonte

O teste `TestLiveCatalogSearchAndEpisodeGroups` consultou os adaptadores diretamente e passou nos cinco títulos em cada fonte. Ele verificou busca, detalhes, IDs de episódio, temporadas explícitas e obtenção de uma URL de player entre os cinco primeiros episódios. A obtenção da URL não substitui a validação do manifesto nem a reprodução pelo MPV.

| Anime | AnimeFire | AnimesOnlineCC |
|---|---|---|
| Demon Slayer | 56 episódios, 4 temporadas explícitas; URL HLS no primeiro episódio | 56 episódios, 3 temporadas explícitas; URL de vídeo no primeiro episódio |
| Frieren | 38 episódios, 1 temporada explícita; URL HLS no primeiro episódio | 38 episódios, 2 temporadas explícitas; URL de vídeo no primeiro episódio |
| Solo Leveling | 25 episódios, 1 temporada explícita; URL HLS no primeiro episódio | 26 episódios, 2 temporadas explícitas; URL de vídeo no primeiro episódio |
| Jujutsu Kaisen | 59 episódios, 1 temporada explícita; URL HLS no primeiro episódio | 59 episódios, 3 temporadas explícitas; URL de vídeo no primeiro episódio |
| One Piece | 1180 episódios, 23 temporadas explícitas; a API retornou URL HLS, mas a validação de mídia no fluxo do app devolveu 404 nos episódios iniciais | 356 episódios, 3 temporadas explícitas; os quatro primeiros itens não resolveram; o item com número 839 retornou URL de vídeo |

As contagens são as recebidas em 17/10/2026 e podem mudar. Essa tabela registra a consulta anterior, que confirmava catálogo e URL, não mídia acessível.

### Revalidação do erro do Hunter x Hunter e da mídia HLS

Em 17/10/2026, consultei novamente o caminho completo entre API de episódio e leitura do manifesto. A resposta da API contém `is_offline=false` e uma URL HLS terminada em `.jpg`. O backend solicita essa URL sem transformar o caminho e interpreta o conteúdo da resposta, sem depender da extensão. Os testes locais `TestSelectHighestAndFallback` e `TestGatewayHLSDisguisedAsJPEG` cobrem manifestos e playlists com extensão `.jpg`.

| Fluxo | Resultado ao vivo |
|---|---|
| Pesquisa `Hunter x Hunter` na aplicação | Selecionou a adaptação de 1999, com 62 episódios e identidade AniList própria; não a mistura com a série de 2011 |
| Hunter x Hunter de 1999, episódios 1–3 | AnimeFire retornou URLs; a leitura de cada manifesto respondeu HTTP 404. A resolução falhou antes da chamada ao MPV |
| Hunter x Hunter de 2011 no AnimeFire | Os cinco primeiros episódios, ambos os áudios disponíveis em cada um, e as amostras do meio e do fim responderam HTTP 404 |
| Hunter x Hunter de 2011 no AnimesOnlineCC | O episódio 1 retornou 404; o episódio 2 resolveu para um arquivo de vídeo acessível |
| Fluxo agregado de Hunter x Hunter de 2011 | Episódio 1 falhou; o resolvedor encontrou uma alternativa válida para o episódio 2 |
| One Piece no AnimeFire | Os cinco primeiros episódios e a amostra do meio responderam HTTP 404; a amostra mais recente forneceu HLS acessível, aceito por `media.Best` |
| One Piece no AnimesOnlineCC | Os quatro primeiros itens retornaram 404; o item com número 839 forneceu vídeo acessível |

O bundle JavaScript atualmente entregue por [AnimeFire](https://animefire.one/) também exibe um aviso de manutenção do servidor de vídeo que informa que, durante esse período, somente episódios novos ficam disponíveis. Isso é compatível com o padrão observado: URLs listadas para episódios antigos falham, enquanto uma amostra recente de One Piece tem manifesto HLS válido. A API marcar `is_offline=false` não garante que o arquivo ainda exista.

Esses resultados não demonstram falha de decodificação ou de transporte do app para os casos testados. A playlist HLS `.jpg` mais recente foi lida pelo mesmo `media.Best` usado pelo serviço. Para o Hunter x Hunter da captura, o endereço retornado pela API respondeu 404 antes de o MPV ser iniciado. A disponibilidade pode mudar e esta consulta não prova o estado de todos os títulos nem a reprodução integral com áudio.

O teste do catálogo foi atualizado para validar manifesto/arquivo em vez de encerrar ao encontrar URL. O comando focado em Hunter x Hunter terminou com falha esperada no subteste AnimeFire, pois nenhuma das sete amostras de mídia estava acessível; o subteste da fonte secundária passou ao encontrar o episódio 2. O comando focado em One Piece passou nas duas fontes após encontrar mídia acessível nas amostras mais recentes. O teste do serviço para `Hunter x Hunter` de 1999 falhou nos três primeiros episódios; para `Hunter x Hunter (2011)`, falhou no episódio 1 e resolveu o episódio 2 pelo fallback.

O erro HTTP 404 de uma playlist agora informa que o servidor de vídeo não encontrou o arquivo deste episódio. `internal/media/hls_test.go` cobre esse texto. `go test ./internal/media -count=1` passou nesta revalidação.

| Comando nesta revalidação | Resultado |
|---|---|
| `go test ./...` | Passou após as alterações |
| `git diff --check` | Passou; Git emitiu avisos de normalização CRLF em `CHANGELOG.md` e `README.md` |
| Live Hunter x Hunter, catálogo por fonte | Falhou no subteste AnimeFire por falta de mídia nas sete amostras; AnimesOnlineCC passou ao encontrar E2 |
| Live One Piece, catálogo por fonte | Passou nas duas fontes ao encontrar mídia acessível nas amostras do fim da série |
| Live `Service.resolve` Hunter x Hunter 1999 | Falhou em E1–E3, todos com HTTP 404 |
| Live `Service.resolve` Hunter x Hunter 2011 | E1 falhou; E2 resolveu pelo fallback |

Não houve build nem reinício da janela aberta; as mudanças de código estão no fonte e não alteram um binário que já esteja em execução.

Essas chamadas confirmam resolução/validação de mídia, não início de processo MPV, áudio ou episódio completo. A inspeção gráfica desta revalidação não foi feita: o shell não encontrou o executável `orca` (`orca: The term 'orca' is not recognized as a name of a cmdlet, function, script file, or executable program`).

Não foram executados nesta revisão: `go vet`, testes live de MangaDex/autenticação, reprodução integral pelo MPV, build Wails, empacotamento, instaladores, login real, teste de atualização instalada ou inspeção visual nas janelas empacotadas de Windows/Linux. O race detector foi pulado porque `CGO_ENABLED=0` neste ambiente. Resultados precisam ser renovados após alterações ou mudança de ambiente.

## Anidrive e AnimeOnlineCC — validação em 18/10/2026

O teste live original foi executado com `$env:ANIMECAOS_LIVE = '1'; go test ./internal/providers -run 'TestAnidriveEmbedUsesBrowserFetchMetadata|TestLiveAnidrivePlayerPage' -count=1 -v`. Os dois testes passaram e o iframe Anidrive respondeu HTTP 200 com o documento JWPlayer. Isso isoladamente não validava a mídia.

Para confirmar a extração, usei Selenium 4.51 com Chrome 155 visível (sem headless), abri `https://animesonline.io/17864/`, entrei no iframe Anidrive, iniciei o JWPlayer e li `video.currentSrc` após o vídeo carregar. A URL assinada respondeu 206 com o User-Agent e Referer do navegador, mas 403 com o User-Agent padrão `Mozilla/5.0 AnimeCaos/3.0`. Corrigi `media.Validate` e o gateway para preservar um User-Agent fornecido pela stream, aplicando o padrão do app somente quando ausente. Em seguida, o MPV iniciado por `player.Controller` através do `media.Gateway` avançou 2 s e reportou H.264 e AAC. O teste temporário usou uma captura em arquivo temporário e foi removido; a URL assinada não foi registrada na documentação. Selenium headless recebeu um vídeo de amostra rotulado “Bot Detected” com duração de 8 s e foi descartado como falso positivo. Naquele registro, Firefox ainda não estava instalado e foi usado o ChromeDriver compatível obtido pelo Selenium Manager em ambiente virtual temporário; a configuração Firefox/GeckoDriver desta máquina foi feita posteriormente e está descrita na revalidação abaixo.

O caminho real do provedor AnimeOnlineCC foi executado com `$env:PATH='D:\AnimeCaos\bin;'+$env:PATH; $env:ANIMECAOS_LIVE_TEST='1'; $env:ANIMECAOS_PLAYER_TEST='1'; go test ./internal/providers -run '^TestLiveOnlineCCPlayback$' -count=1 -v`. Passou após a alteração de cabeçalhos: o MPV reportou H.264/AAC, avançou, fez seek e chegou ao EOF natural do episódio. O processo terminou em 9,83 s.

Para o título mostrado na captura, consultei no AnimeOnlineCC os termos “Cyberpunk: Mercenários”, “Cyberpunk: Edgerunners”, “Cyberpunk Edgerunners” e “Cyberpunk”. Os três primeiros não retornaram item correspondente; a busca ampla retornou Koukaku Kidoutai e Maou 2099, que não são correspondências válidas. Assim, o episódio Cyberpunk do AnimeFire não tem alternativa exata no AnimeOnlineCC nessa consulta e não deve ser trocado por um desses resultados.


## Revalidação de busca, FFprobe e Firefox/GeckoDriver — 18/10/2026

O Firefox foi instalado pelo WinGet e o GeckoDriver já disponível em `D:\AnimeCaos\bin` foi configurado para o usuário atual:

- Firefox `157.0.1`: `C:\Program Files\Mozilla Firefox\firefox.exe`.
- GeckoDriver `0.36.0`: `D:\AnimeCaos\bin\geckodriver.exe`.
- Variáveis persistentes: `ANIMECAOS_FIREFOX_PATH` e `ANIMECAOS_GECKODRIVER_PATH` com esses caminhos. `ANIMECAOS_BROWSER_HEADLESS=0` abre o navegador visivelmente para diagnóstico; por padrão ele é headless.
- FFprobe `9.0.2`: `D:\AnimeCaos\bin\ffprobe.exe`, configurado em `ANIMECAOS_FFPROBE_PATH`, para que a inspeção de áudio continue funcionando sem acrescentar a pasta `bin` ao `PATH` do usuário.
- Selenium executa scripts que leem iframes, elementos de vídeo e fontes do playlist/config JWPlayer. FFprobe agora inspeciona codecs e dimensões de arquivos diretos; quando identifica vídeo sem áudio, o preflight e a reprodução descartam a stream.
- Comando de instalação usado: `winget install --id Mozilla.Firefox --exact --source winget --silent --accept-package-agreements --accept-source-agreements`; instalação concluída e hash verificado.

### Busca e reprodução MPV em dez títulos

Comando: `$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_PLAYER_TEST='1'; $env:PATH='D:\AnimeCaos\bin;'+$env:PATH; go test ./internal/app -run '^TestLiveSearchAvailabilityTenAnimeSamples$' -count=1 -v`. Passou em 106,78 s. Nove títulos tiveram o episódio 1 aprovado no preflight e o MPV decodificou H.264/AAC, avançou e aceitou seek. Hunter x Hunter 2011 ficou oculto porque nenhum E1 consultado passou no preflight.

| Consulta | Selo máximo do E1 | MPV: fonte, altura e dimensões observadas | Resultado |
|---|---:|---|---|
| Hunter x Hunter 2011 | — | — | Sem card: E1 indisponível nas fontes consultadas |
| Black Clover | 720p | AnimesOnlineCC, 360p, 636×360 | H.264/AAC; seek passou |
| One Punch Man | 720p | OtakuLogia, 720p, 1280×720 | H.264/AAC; seek passou |
| Demon Slayer | 1080p | OtakuLogia, 1080p, 1920×1080 | H.264/AAC; seek passou |
| Frieren | 1080p | OtakuLogia, 1080p, 1920×1080 | H.264/AAC; seek passou |
| Solo Leveling | 1080p | OtakuLogia, 1080p, 1920×1080 | H.264/AAC; seek passou |
| Jujutsu Kaisen | 1080p | OtakuLogia, 1080p, 1920×1080 | H.264/AAC; seek passou |
| One Piece | 720p | OtakuLogia, 720p, 1280×720 | H.264/AAC; seek passou |
| Naruto Shippuden | 720p | OtakuLogia, 360p, 480×360 | H.264/AAC; seek passou |
| Death Note | 720p | OtakuLogia, 720p, 1280×720 | H.264/AAC; seek passou |

O selo é a maior qualidade observada no E1 entre as fontes validadas. A fonte efetivamente selecionada pode ter resolução menor porque a preferência de áudio tem precedência na ordenação, conforme a regra do produto. O teste verificou início, codecs, dimensões, avanço e seek; não assistiu os episódios até o fim.

### Regressão de identidade e disponibilidade do Hunter x Hunter — 18/10/2026

O histórico local identificou a entrada `HUNTER × HUNTER (2011)` como Otakulogia, com E1 salvo em posição de 495 s; a outra entrada genérica era SushiAnimes. A busca `hunter` trazia apenas a adaptação de 1999. O motivo era o resultado Otakulogia ter título principal `HUNTER × HUNTER (2011)` e alias `Hunter x Hunter`: a canonicalização tratava ambos igualmente, ficava ambígua entre AniList 136 e 11061, e o filtro rejeitava o item antes do preflight.

A correção dá precedência ao título principal do provedor e consulta aliases apenas quando ele não identifica uma obra. O teste fixture garante que a versão 2011 continua separada da de 1999. Comando live: `$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_LIVE_TITLE='hunter'; go test ./internal/app -run '^TestLiveSearchAvailabilityTenAnimeSamples$' -count=1 -v`. Passou em 8,55 s e publicou dois cards: Hunter x Hunter (AniList 136, AnimeFire/SushiAnimes) e Hunter x Hunter 2011 (AniList 11061, AnimesOnlineCC/Otakulogia). O primeiro foi aprovado pelo E1 da SushiAnimes e o segundo pelo E1 da Otakulogia; ambos tiveram qualidade não identificada nessa consulta. Os streams diretos legendado e dublado da Otakulogia também responderam à validação HTTP nesta rodada. Isso confirma inclusão no catálogo e preflight, não uma nova sessão MPV nem dimensões do arquivo.

Comando de regressão: `go test ./internal/providers -run "TestExactCanonicalPrefersProviderTitleOverAmbiguousAlias|TestSearchExpandedDoesNotCanonicalizeAmbiguousTitles" -count=1 -v`. Os dois testes passaram.

### Títulos relacionados e busca em lote — 18/10/2026

`searchResultMatchesQuery` agora aceita a sequência completa de palavras da consulta dentro do título principal, ignorando acentos e normalizando `×` como `x`. A regra inclui relações como `hunter` → `City Hunter` e permite filmes ou continuações cujo título contenha a consulta completa, sem usar essa relação como identidade canônica. Testes também garantem que `cat` não encontre `Caterpillar` e que `Mugyutto! Black Clover` continue elegível para `Black Clover`.

Comando live: `$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_LIVE_TITLE='hunter'; go test ./internal/app -run '^TestLiveSearchAvailabilityTenAnimeSamples$' -count=1 -v`. A rodada mais recente antes da correção sazonal levou 9,34 s dentro do teste. Dez cards tiveram E1 aprovado: Hunter x Hunter (AniList 136; SushiAnimes), Hunter x Hunter 2011 (AniList 11061; Otakulogia), Hunter x Hunter Dublado (AnimesOnlineCC), City Hunter (Otakulogia e SushiAnimes), Vampire Hunter, Witch Hunter ROBIN, Vampire Hunter D: Bloodlust, City Hunter: Hyakuman Doru no Inbou e Irregular Hunter X: The Day of Sigma (demais títulos via Otakulogia). Todos mostraram qualidade não identificada nesta rodada.

Limites da amostra: os dois cards City Hunter tinham IDs de provedores diferentes e nenhum AniList ID; não foram fundidos porque o título sozinho não prova que sejam a mesma adaptação. A página consultada não trouxe os filmes Hunter x Hunter como cards com E1 aprovado. O teste confirmou catálogo e preflight, não uma nova reprodução MPV desses dez resultados. A busca agora publica em lote; consulte o estado atual em [Plano do pipeline de busca](architecture/SEARCH_PIPELINE_PLAN.md).

### Consulta sazonal e publicação em lote — 18/10/2026

Diagnóstico live inicial: AniList encontrou `Tensei Shitara Ken Deshita 2nd Season` (ID 159042), mas `searchCandidates` retornou zero itens. As fontes consultam a obra pelo nome base `Tensei Shitara Ken Deshita`. AnimesOnlineCC apresentou 15 episódios, com 12 na temporada 1 e três na 2; Otakulogia apresentou 13, com 12 e um; ambos resolveram T2 E1. O AnimeFire e a SushiAnimes também tinham página base com temporada 2. A causa foi o filtro de relevância aplicar a consulta inteira com sufixo `2nd Season` ao título base, além do preflight selecionar somente E1 da temporada 1.

A correção acrescentou a busca auxiliar pelo título base e manteve a associação AniList como provisória. O preflight valida E1 da temporada explícita; somente após a aprovação o grupo recebe a identidade canônica. Os quatro candidatos foram agrupados em um card, com `T2 E1`, `sourcesVerified=animefire,animesonlinecc,otakulogia,sushianimes` e máximo observado de 1080p. O frontend passou a receber apenas a resposta final, depois de remover o evento de card progressivo.

- Busca/preflight live e MPV E2E para T2 E1 após o cache de catálogo: `$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_PLAYER_TEST='1'; $env:PATH='D:\AnimeCaos\bin;'+$env:PATH; $env:ANIMECAOS_LIVE_TITLE='Tensei Shitara Ken Deshita 2nd Season'; go test ./internal/app -run '^TestLiveSearchAvailabilityTenAnimeSamples$' -count=1 -v` — a chamada de busca levou 3,45 s e o teste completo 12,01 s. Um card `Reincarnated as a Sword`, ID AniList 159042, agrupou quatro fontes; `T2 E1` confirmou até 1080p. MPV escolheu AnimeFire, decodificou AV1/AAC em 1920×1080, avançou e completou seek para 4,1 s.

O preflight confirma acesso HTTP nas quatro fontes. A amostra MPV observou somente o fluxo AnimeFire selecionado; não afirma que os outros três provedores foram tocados pelo MPV nessa rodada. O teste não assistiu o episódio até o fim.

### Busca ampla, deduplicação e cache de identidade AniList — 18/10/2026

Comando: `$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_LIVE_TITLE='Tensei Shitara'; go test ./internal/app -run '^TestLiveSearchAvailabilityTenAnimeSamples$' -count=1 -v`. A chamada de busca levou 6,371 s e o pacote terminou em 8,289 s; publicou sete grupos com E1 aprovado. “Tensei Shitara Dai Nana Ouji” apareceu uma vez, com uma fonte principal da SushiAnimes e variantes da AnimesOnlineCC e Otakulogia; o card confirmou até 720p. Slime, Dragon no Tamago, Tensura Nikki e o filme Guren no Kizuna permaneceram como identidades separadas.

Antes de agrupar consultas de identidade em GraphQL, a mesma consulta em outra execução fria levou 12,44 s no pacote. O resultado atual é uma observação isolada, não uma medição p95. O cache AniList dura 30 min para correspondências positivas e 2 min para buscas sem resultado; a validade máxima é 24 h e 30 min, respectivamente. Páginas de catálogo ficam em cache por 30 s quando há itens e 10 s quando vazias. O cache de identidade guarda metadados; o stream continua sendo resolvido novamente ao reproduzir.

Fixtures de batching/cache `TestTitleMatchesBatchUsesOneRequestAndCachesQueries` e `TestSearchExpandedCachesProviderPageBriefly` passaram em `go test ./...`. A primeira cobre consultas em um GraphQL e cache por título; a segunda confirma que a mesma página do provedor não é buscada novamente dentro dos 30 s.

### Anidrive e AnimesOnlineCC com Firefox

- Comando: `$env:ANIMECAOS_LIVE_TEST='1'; $env:ANIMECAOS_PLAYER_TEST='1'; $env:PATH='D:\AnimeCaos\bin;'+$env:PATH; go test ./internal/providers -run '^TestLiveOnlineCCPlayback$' -count=1 -v`. Passou: MPV reportou H.264/AAC, duração de 1.415,35 s, seek e EOF natural no episódio Naruto clássico E1 do AnimesOnlineCC.
- Comando E2E: `$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_PLAYER_TEST='1'; $env:ANIMECAOS_BROWSER_HEADLESS='0'; $env:ANIMECAOS_FIREFOX_PATH='C:\Program Files\Mozilla Firefox\firefox.exe'; $env:ANIMECAOS_GECKODRIVER_PATH='D:\AnimeCaos\bin\geckodriver.exe'; $env:PATH='D:\AnimeCaos\bin;'+$env:PATH; go test ./internal/app -run '^TestLiveAnidriveMPVE2E$' -count=1 -v`. O embed Anidrive (`https://animesonline.io/17864/`) entregou um clipe VP9 de 6,876 s, 320×100, sem áudio. FFprobe identificou vídeo sem faixa de áudio; o serviço encerrou antes de iniciar MPV com `o arquivo de vídeo não contém faixa de áudio`. Isso rejeita corretamente o candidato; não confirma reprodução Anidrive. Uma confirmação anterior no Chrome avançou uma URL extraída, mas não confirma a mídia atual.

### Suítes automatizadas — correção sazonal e lote — 18/10/2026

- `go test ./...` — passou em todos os pacotes após o batching AniList e o cache curto de páginas de catálogo.
- `npm exec -- tsc --noEmit` — passou; nenhuma mudança de UI nesta otimização.
- `npm test -- --run` — a primeira execução passou em 19/20, com falha no teste de navegação por teclado; o caso isolado passou e a repetição completa passou em 20/20.
- `git diff --check` — passou; Git emitiu apenas aviso de normalização CRLF para `CHANGELOG.md` e `README.md`.
- `go env CGO_ENABLED` — `0`; `go test -race ./...` não é executável nesta configuração.
- `wails dev` — executado para reiniciar o `AnimeCaos-dev`; geração de bindings/assets, preparação do frontend e compilação de desenvolvimento concluídas. A janela `AnimeCaos` está aberta. Build de distribuição, empacotamento e instalador não foram executados.

## Cobertura de frontend

### Consolidação do histórico de reprodução baixada — 18/10/2026

- `gofmt -w internal/app/service.go internal/app/history_offline_test.go` — passou.
- `go test ./internal/app -run '^TestHistoryMergesDownloadedPlaybackAndResumesOffline$' -count=1 -v` — passou; confirma consolidação sob a identidade original, retomada do arquivo local na posição salva e manutenção de uma única entrada após atualizar o progresso.
- `go test ./...` — falhou em dois testes de `internal/providers`: `TestBrowserAdProxyBlocksKnownTrackerButPassesPlayerRequests` recebeu HTTP 403 no pedido para `tags.crwdcntrl.net/pixel`; `TestRenderedPlayerURLsReadsJWPlayerAndStartsMuted/muted_playback_exposes_video` expirou aguardando o player apesar de `readyState=complete`, JWPlayer e elemento de vídeo presentes. `internal/app` passou nesta execução.
- `cd frontend; npm exec -- tsc --noEmit` — passou.
- `cd frontend; npm test -- --run` — passou: 23 testes.
- `git diff --check` — passou; Git emitiu aviso de normalização de LF/CRLF para `CHANGELOG.md` e `README.md`.

Na inicialização do app, a consulta somente leitura ao histórico confirmou uma entrada `otakulogia:144` para HUNTER × HUNTER (2011) e nenhuma chave local duplicada. O progresso mais recente foi preservado. Entradas locais só são unificadas quando o caminho corresponde a um download concluído registrado; sem essa ligação, o histórico não é inferido pelo título.

### Ações dos arquivos offline — 18/10/2026

- `cd frontend; npm exec -- tsc --noEmit` — passou.
- `cd frontend; npm test -- --run` — passou: 23 testes.
- `go test ./...` — passou em todos os pacotes.
- `git diff --check` — passou; Git alertou sobre normalização CRLF em `CHANGELOG.md` e `README.md`.

O teste DOM confirma que as ações de arquivo são botões de ícone com nomes acessíveis e que “Abrir pasta” encaminha o caminho selecionado ao serviço. O serviço valida o caminho dentro da biblioteca e abre a pasta no gerenciador nativo (Explorer no Windows, Finder no macOS ou `xdg-open` no Linux). No Windows, uma janela existente do Explorer é ativada; se ainda não houver uma janela para a pasta, o serviço abre o diretório e aguarda a nova janela.

### Correção de abertura da pasta no Windows — 18/10/2026

- `gofmt -w internal/platform/system.go` — passou.
- `go test ./...` — passou em todos os pacotes.
- `cd frontend; npm exec -- tsc --noEmit` — passou.
- `cd frontend; npm test -- --run -t 'navega os destaques com as setas do teclado'` — passou isoladamente; na execução completa inicial o mesmo teste falhou uma vez.
- `cd frontend; npm test -- --run` — repetição completa passou: 23 testes.
- `git diff --check` — passou; Git alertou sobre normalização CRLF em `CHANGELOG.md` e `README.md`.

O Explorer recebe o diretório diretamente. A execução de desenvolvimento já ativa reiniciou o app e regenerou os bindings após a mudança no serviço.

### Ativação da pasta no Explorer — 18/10/2026

| Comando | Resultado |
|---|---|
| `gofmt -w internal/platform/system.go internal/platform/reveal_windows.go internal/platform/reveal_other.go` | Passou |
| `go test ./...` | Passou em todos os pacotes |
| `cd frontend; npm exec -- tsc --noEmit` | Passou |
| `cd frontend; npm test -- --run` | Passou: 23 testes |
| `git diff --check` | Passou; Git alertou sobre normalização LF/CRLF em `CHANGELOG.md` e `README.md` |

No Windows, o adaptador busca uma janela visível `CabinetWClass` cujo título corresponda à pasta e solicita sua ativação. Se não encontra a janela, abre o diretório e tenta ativá-la por até cinco segundos; se nenhuma janela correspondente aparecer, retorna um erro visível em vez de indicar sucesso sem abrir a pasta. A ativação do Explorer não teve uma validação por clique físico nesta rodada; os testes Go verificam compilação e comportamento de pacote, não foco real de janela.

### Indicadores animados de carregamento — 18/10/2026

- `cd frontend; npm exec -- tsc --noEmit` — passou.
- `cd frontend; npm test -- --run` — passou: 22 testes.
- `git diff --check` — passou; Git alertou sobre normalização CRLF nos arquivos já modificados `CHANGELOG.md` e `README.md`.

Spinner e shimmer da busca, além dos pontos pulsantes do estado genérico “Carregando…”, mantêm animação ativa enquanto a operação está em andamento, inclusive quando `prefers-reduced-motion` está ativo. O restante das animações continua sujeito à preferência do sistema.

O teste de carregamento inicial também confirma que a busca reserva 10 skeletons para completar a grade.

`frontend/src/App.test.tsx` cobre regressões dos fluxos de home/pesquisa, identidade e aliases, navegação, sidebar, painel de preview, downloads, histórico e ausência de rótulos de fonte. A lista exata e os nomes ficam no próprio teste; use Vitest como autoridade para a contagem.

### Isolamento do player e auditoria de anúncios nas fontes — 18/10/2026

As fixtures cobrem extração limitada à raiz do player, rejeição de iframes externos e wrappers de anúncio, fallback conservador quando não há raiz, política `no-referrer`, bloqueio do proxy em HTTP e CONNECT, preservação de redirects normais, rejeição de redirect para rastreador, HLS/gateway e iframe injetado por JavaScript. O teste fixture também passa com Firefox/GeckoDriver explicitamente configurado.

| Comando | Resultado |
|---|---|
| `go test ./internal/netx ./internal/media ./internal/providers -count=1` | Passou: transporte, HLS/gateway e todos os testes dos provedores |
| `$env:ANIMECAOS_GECKODRIVER_PATH='D:\AnimeCaos\bin\geckodriver.exe'; $env:ANIMECAOS_FIREFOX_PATH='C:\Program Files\Mozilla Firefox\firefox.exe'; go test ./internal/providers -run '^TestRenderedPlayerURLs' -count=1 -v` | Passou: Firefox extrai iframe criado por JavaScript, detecta protector, lê JWPlayer e mantém o vídeo dentro do player |
| `$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_GECKODRIVER_PATH='D:\AnimeCaos\bin\geckodriver.exe'; $env:ANIMECAOS_FIREFOX_PATH='C:\Program Files\Mozilla Firefox\firefox.exe'; $env:PATH='D:\AnimeCaos\bin;'+$env:PATH; go test ./internal/providers -run '^TestLiveProviderPlayerAdAudit$' -count=1 -v` | Auditoria Hunter x Hunter das quatro fontes concluída em 28,06 s. Otakulogia passou validação; AnimeFire retornou HLS 404; AnimesOnlineCC encontrou iframe Blogger, mas o RPC não ofereceu rendition; Sushi não retornou resultado Hunter x Hunter nessa repetição (uma execução anterior da mesma auditoria havia validado um arquivo); uma consulta live separada de Naruto Shippuden E1 passou em HLS. O `PASS` desta ferramenta de diagnóstico significa que a consulta terminou, não que todos os provedores passaram mídia |
| `$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_LIVE_PROVIDER='sushianimes'; $env:ANIMECAOS_LIVE_QUERY='Naruto'; $env:ANIMECAOS_LIVE_EXPECTED='naruto'; go test ./internal/providers -run '^TestLiveProviderPlayerAdAudit$' -count=1 -v` | Passou na SushiAnimes: Naruto Shippuden E1, arquivo HLS acessível, áudio dublado |

O proxy só bloqueia hosts conhecidos por hostname. As fixtures confirmam que intersticiais conhecidos são identificados, não aceitos como mídia e não seguidos. Hosts publicitários novos podem exigir uma atualização explícita da lista.

### Reprodução real das fontes restantes — 18/10/2026

Foi adicionado `TestLiveProviderPlayerMPVE2E`, opt-in por fonte. Ele executa busca, detalhes, resolução, validação de mídia, gateway local e MPV; exige vídeo/áudio decodificados, dimensões, avanço e seek. `ANIMECAOS_LIVE_EPISODE_NUMBER` permite escolher um episódio explícito. Os testes fixture também cobrem `data-id` na SushiAnimes, fallback para um player embutido sem botões AJAX e vídeo HTML5 que só expõe a mídia após reprodução silenciada.

| Fonte e amostra | Resultado atual |
|---|---|
| SushiAnimes — Hunter x Hunter (1999), T1 E1 | MPV passou: H.264/AAC, 1280×720, avanço até 11 s após seek |
| AnimesOnlineCC — Naruto Shippuden, T1 E1 | MPV passou: H.264/AAC, 478×360, áudio dublado |
| AnimesOnlineCC — Hunter x Hunter (2011), T1 E2 | MPV passou: H.264/AAC, 634×360, áudio legendado, 360p |
| Otakulogia — Hunter x Hunter (2011), T1 E1 | MPV passou: H.264/AAC, 1280×720, áudio legendado |
| AnimesOnlineCC — Hunter x Hunter (2011), T1 E1 | **Não passou**: a resposta RPC Blogger veio com `payload=null`; Firefox e Chrome não expuseram uma URL de mídia antes do timeout. E2 passou. Essa variante não é considerada disponível para E1; a busca agregada usou o E1 confirmado da Otakulogia. |

Comandos live executados para os quatro resultados MPV positivos:

```powershell
$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_PLAYER_TEST='1'; $env:ANIMECAOS_LIVE_PROVIDER='sushianimes'; $env:ANIMECAOS_LIVE_QUERY='Hunter x Hunter'; $env:ANIMECAOS_LIVE_EXPECTED='hunter x hunter'; $env:ANIMECAOS_GECKODRIVER_PATH='D:\AnimeCaos\bin\geckodriver.exe'; $env:ANIMECAOS_FIREFOX_PATH='C:\Program Files\Mozilla Firefox\firefox.exe'; $env:PATH='D:\AnimeCaos\bin;'+$env:PATH; go test ./internal/providers -run '^TestLiveProviderPlayerMPVE2E$' -count=1 -v
$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_PLAYER_TEST='1'; $env:ANIMECAOS_LIVE_PROVIDER='animesonlinecc'; $env:ANIMECAOS_LIVE_QUERY='Naruto'; $env:ANIMECAOS_LIVE_EXPECTED='naruto'; $env:ANIMECAOS_GECKODRIVER_PATH='D:\AnimeCaos\bin\geckodriver.exe'; $env:ANIMECAOS_FIREFOX_PATH='C:\Program Files\Mozilla Firefox\firefox.exe'; $env:PATH='D:\AnimeCaos\bin;'+$env:PATH; go test ./internal/providers -run '^TestLiveProviderPlayerMPVE2E$' -count=1 -v
$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_PLAYER_TEST='1'; $env:ANIMECAOS_LIVE_PROVIDER='animesonlinecc'; $env:ANIMECAOS_LIVE_QUERY='Hunter x Hunter'; $env:ANIMECAOS_LIVE_EXPECTED='hunter x hunter'; $env:ANIMECAOS_LIVE_EPISODE_NUMBER='2'; $env:ANIMECAOS_GECKODRIVER_PATH='D:\AnimeCaos\bin\geckodriver.exe'; $env:ANIMECAOS_FIREFOX_PATH='C:\Program Files\Mozilla Firefox\firefox.exe'; $env:PATH='D:\AnimeCaos\bin;'+$env:PATH; go test ./internal/providers -run '^TestLiveProviderPlayerMPVE2E$' -count=1 -v
$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_PLAYER_TEST='1'; $env:ANIMECAOS_LIVE_PROVIDER='otakulogia'; $env:ANIMECAOS_LIVE_QUERY='Hunter x Hunter'; $env:ANIMECAOS_LIVE_EXPECTED='hunter x hunter'; $env:PATH='D:\AnimeCaos\bin;'+$env:PATH; go test ./internal/providers -run '^TestLiveProviderPlayerMPVE2E$' -count=1 -v
```

Comando executado para o caso AnimesOnlineCC Hunter E1 sem mídia extraída (Firefox/GeckoDriver):

```powershell
$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_PLAYER_TEST='1'; $env:ANIMECAOS_LIVE_PROVIDER='animesonlinecc'; $env:ANIMECAOS_LIVE_QUERY='Hunter x Hunter'; $env:ANIMECAOS_LIVE_EXPECTED='hunter x hunter'; $env:ANIMECAOS_GECKODRIVER_PATH='D:\AnimeCaos\bin\geckodriver.exe'; $env:ANIMECAOS_FIREFOX_PATH='C:\Program Files\Mozilla Firefox\firefox.exe'; $env:PATH='D:\AnimeCaos\bin;'+$env:PATH; go test ./internal/providers -run '^TestLiveProviderPlayerMPVE2E$' -count=1 -v
```

A expansão segura do sufixo de ano também foi validada no fluxo completo do app. A consulta literal `Hunter x Hunter 2011` retornou as versões 1999 e 2011 em cards separados; E1 de 2011 passou no preflight pela Otakulogia até 1080p. O MPV selecionou 720p, decodificou H.264/AAC em 1280×720, avançou e aceitou seek. A chamada Search levou 14,43 s e avisou que outras fontes excederam o orçamento, preservando os cards aprovados.

```powershell
$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_PLAYER_TEST='1'; $env:ANIMECAOS_LIVE_TITLE='Hunter x Hunter 2011'; $env:ANIMECAOS_LIVE_EXPECTED_ANILIST_ID='11061'; $env:ANIMECAOS_GECKODRIVER_PATH='D:\AnimeCaos\bin\geckodriver.exe'; $env:ANIMECAOS_FIREFOX_PATH='C:\Program Files\Mozilla Firefox\firefox.exe'; $env:ANIMECAOS_FFPROBE_PATH='D:\AnimeCaos\bin\ffprobe.exe'; $env:PATH='D:\AnimeCaos\bin;'+$env:PATH; go test ./internal/app -run '^TestLiveSearchAvailabilityTenAnimeSamples$' -count=1 -v
```

AnimeFire não fez parte dos E2E positivos desta etapa, conforme a instabilidade remota observada anteriormente. Estes resultados certificam amostras por fonte, não todos os episódios. Em particular, nesta rodada o endpoint Blogger da página Hunter E1 da AnimesOnlineCC respondeu `null` e não forneceu mídia extraível, enquanto a Otakulogia reproduziu o mesmo E1.

Validação final desta rodada:

| Comando | Resultado |
|---|---|
| `gofmt -w internal/providers/live_player_test.go internal/providers/sushi.go internal/providers/sushi_test.go internal/providers/onlinecc.go internal/providers/player_candidates.go internal/providers/selenium_test.go internal/providers/browser_test.go internal/providers/search_intent.go internal/providers/catalog.go internal/providers/catalog_test.go internal/providers/blogger.go internal/providers/blogger_test.go internal/app/service_test.go` | Passou |
| `go test ./internal/providers -run '^TestBloggerRPC$' -count=1` | Passou; cobre payload Blogger vazio e `null` sem aceitar formatos inválidos |
| `go test ./... -count=1` | Passou em todos os pacotes |
| `cd frontend; npm exec -- tsc --noEmit` | Passou sem diagnósticos TypeScript |
| `cd frontend; npm test -- --run` | Passou: 23 testes |
| `git diff --check` | Passou; Git alertou apenas sobre normalização LF/CRLF em `CHANGELOG.md` e `README.md` |
| `go env CGO_ENABLED` | `0`; `go test -race ./...` não foi executado porque CGO está desabilitado |

## Boas práticas

- Parsers externos devem ter fixtures curtas via `httptest` e cobrir mudança de formato, timeout/cancelamento e erro HTTP relevante.
- Use IDs estáveis em testes de episódio; número visual e posição não são identidade.
- Testes live não devem conter credenciais nem tornar a suite padrão dependente de internet.
- Use `t.TempDir()` ou `ANIMECAOS_DATA_DIR` para não alterar dados reais.
- Descreva exatamente comandos e resultados; não apresente testes anteriores como se fossem desta revisão.
