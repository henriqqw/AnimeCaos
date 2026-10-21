# Testes e validação

## Banners do GitHub e do X — 21/10/2026

- Revisão visual direta de `assets/readme-banner.png` e `assets/x-profile-banner.png` — concluída.
- Dimensões da capa X — conferidas: 1500 × 500 px.
- `git diff --check` — passou; os avisos de conversão CRLF existentes não indicaram erros de whitespace.

O X recomenda 1500 × 500 px para cabeçalhos e informa que até 60 px das bordas superior e inferior podem ser cortados em alguns casos. A capa mantém lettering e texto fora do canto inferior esquerdo, ocupado pela sobreposição da foto de perfil. A guia dimensional foi consultada em [Ajuda oficial do X](https://help.x.com/en/managing-your-account/common-issues-when-uploading-profile-photo.html).

## Splash animada e reinício em desenvolvimento — 20/10/2026

O PNG de poster foi removido da splash. O HTML antecipa o carregamento do WebM;
vídeo e wordmark só iniciam juntos o fade de 560 ms após o primeiro quadro ser
decodificado e a logo carregar. Se houver falha, a página tenta o vídeo outra
vez e oferece retry manual, mantendo a logo oculta. O progresso soma vídeo e
wordmark (10% cada), `Initial()` (60%), o tempo mínimo (18%) e o fade-out (2%).
O relógio normaliza os primeiros 3,4 s; o fade-out dura mais 600 ms. A splash
fica visível por pelo menos 4 s e pode demorar mais se o vídeo, o backend ou o
fade-in ainda estiverem em andamento. O layout adapta a composição a janelas
estreitas e baixas. O listener da bandeja não termina após um reinício, então
`wails dev` pode recarregar a interface várias vezes sem encerrar o Vite.

| Comando/inspeção | Resultado |
|---|---|
| `cd frontend; npm exec -- tsc --noEmit` | Passou após a remoção do poster e a implementação do retry de vídeo. |
| `cd frontend; npm test -- --run` | Passou: 34/34, incluindo a entrada sincronizada, ausência de poster e retry após falha do vídeo. |
| `go test ./... -count=1` no Windows | Passou em todos os pacotes, incluindo `internal/platform`. |
| `go test -tags dev . -run '^TestAppInstanceIDUsesDevelopmentNamespace$' -count=1` | Passou; o build `dev` seleciona recarregamento no mesmo processo. |
| `wsl -d Ubuntu-24.04 -- bash -lc 'export PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin; cd /mnt/d/AnimeCaos; go test -race ./... -count=1'` | Passou em todos os pacotes. |
| `git diff --check` | Passou; Git mostrou apenas avisos de conversão LF/CRLF no checkout Windows. |
| Build/empacotamento depois desta revisão | Não executado conforme a pausa solicitada. A reprodução visual e os reinícios repetidos ainda precisam de inspeção manual na janela Wails. |

## Auto-update na inicialização e correção do CI — 21/10/2026

Builds instaladas no Windows e AppImage Linux agora consultam a release durante
a splash. A checagem tem limite de 8 s; pacote mais novo é baixado, validado
com SHA-256 e aplicado antes de a interface ser liberada. Download, instalação,
erro de rede e pacote Flatpak não bloqueiam a versão atual. Os testes cobrem
Windows/AppImage/Flatpak e a falha de consulta. A edição Windows v2.0.0 tem um
atualizador Python que pede confirmação e migra pelo ZIP, sem validar SHA-256.
A antiga edição Flatpak exige migrar manualmente para AppImage. O auto-update
Go/Wails valida o pacote e passa a operar após a migração.

| Comando/inspeção | Resultado |
|---|---|
| `npm ci` em `frontend` | Passou depois de encerrar a sessão `wails dev` que mantinha o binário Rollup aberto. Instalou 99 pacotes; `npm audit` informou 0 vulnerabilidades. |
| `cd frontend; npm run build` | Passou; TypeScript e Vite geraram `frontend/dist`. |
| `go test ./... -count=1` | Passou em todos os pacotes, incluindo os testes do auto-update na inicialização. |
| `cd frontend; npm exec -- tsc --noEmit` | Passou. |
| `cd frontend; npm test -- --run` | Passou: 34/34. |
| Parser YAML do Python (`yaml.safe_load`) nos dois workflows | Passou depois de corrigir a indentação das notas da release. |
| CI `39529315094` no GitHub | Ubuntu passou em Go, `-race`, TypeScript e Vitest. Windows passou instalação/build frontend e falhou em `TestHistoryMergesDownloadedPlaybackAndResumesOffline`: alias 8.3 `RUNNER~1` e caminho longo identificavam o mesmo arquivo, mas a associação do download comparava apenas texto. Corrigido com `os.SameFile`; CI será repetido no próximo commit. |
| CI `39529998556` no GitHub | Passou em `windows-latest` e `ubuntu-24.04`; Ubuntu também passou `go test -race ./...`. |
| Workflow de release `39530287789` | Os testes de release passaram em Windows e Ubuntu. O job Linux falhou porque o teste Firefox recebeu o caminho relativo do stage, mas `go test` executa a partir de `internal/providers`. Corrigido para usar o caminho absoluto e validar Firefox/GeckoDriver no stage. |
| Workflow de release `39531224201` | Os testes passaram nos dois sistemas; o pacote Linux ultrapassou o teste do Firefox e entrou na construção do AppImage. O job Windows parou ao verificar `widevinecdm.dll`: o CAB oficial contém esse componente assinado pelo Google, enquanto o script exigia certificado Microsoft em todo EXE/DLL. Corrigido para exigir Microsoft no executável principal e assinatura Authenticode válida nos demais componentes; nova execução da tag pendente. |
| Workflow de release `39533700847` | Testes de código, pacotes Windows/Linux e smoke de instalar/atualizar/desinstalar passaram. A publicação falhou porque o job não fazia checkout do repositório antes de gerar notas com `gh release create`; corrigido no commit `b46e5d3`. |
| Workflow de release `39535484688` | Os testes Go/race/TypeScript/Vitest e o smoke do AppImage passaram; o ZIP Windows também foi construído. O smoke Windows falhou ao conferir o processo depois do update. O script agora espera o encerramento do app/WebView2 antes da troca, aguarda o relançamento e imprime `updater-error.log`/`startup-error.log` em caso de falha. Reexecução após essa correção ainda pendente. |
| Workflow de release `39537337764` | Testes de release passaram nos dois sistemas e o AppImage passou pelo smoke test. O runner Windows recebeu HTTP 504 do feed do Chocolatey ao instalar `mpvio.install`, antes de empacotar. A etapa agora repete a instalação dos pacotes fixados até três vezes com espera progressiva; nova execução pendente. |
| Workflow de release `39538571500` | Passou em `windows-latest` e `ubuntu-24.04`: Go/race/TypeScript/Vitest; empacotamento Windows e AppImage; smoke de instalação, atualização, reinício, desinstalação e preservação do banco no Windows; smoke do AppImage; checksums Sigstore; publicação da release `v3.0.0`. |

## Release pública v3.0.0 — 21/10/2026

A [release `v3.0.0`](https://github.com/henriqqw/AnimeCaos/releases/tag/v3.0.0)
foi publicada às 03:43 UTC pelo
[workflow `39538571500`](https://github.com/henriqqw/AnimeCaos/actions/runs/39538571500).
O GitHub `/releases/latest` retorna `v3.0.0`. A pipeline publicou os três
pacotes, `SHA256SUMS`, `SHA256SUMS.sigstore.json` (8.377 bytes) e
`WINDOWS-AUTHENTICODE-STATUS.txt`. O arquivo de hashes foi baixado da release;
seus três valores correspondem aos digests SHA-256 dos assets reportados pela
API do GitHub. O job que executou `cosign sign-blob` passou.

| Asset | Tamanho | SHA-256 |
|---|---:|---|
| `AnimeCaos-3.0.0-windows-amd64.zip` | 669.956.620 bytes | `ffe5763dc1ff627b69dd5953741db1f19f2c2100547ccda64723ed38823a4f0b` |
| `AnimeCaos-3.0.0-windows-setup.exe` | 489.729.270 bytes | `0ff74ab5b19b6698a52b813a5121975af31d48a01e25cb3fbf613e50224a15dc` |
| `AnimeCaos-3.0.0-x86_64.AppImage` | 342.960.632 bytes | `a73c2ed323eaf1c0cd0396c0e16ed1054cb8973a92053ea545540e0ca42450da` |

O ZIP e o instalador Windows não têm Authenticode: os secrets de certificado
não estavam configurados. Essa condição está nas notas da release e em
`WINDOWS-AUTHENTICODE-STATUS.txt`; o Windows pode mostrar aviso de editor
desconhecido. A assinatura Sigstore de `SHA256SUMS` foi criada no workflow,
mas não substitui Authenticode.

Os smoke tests foram feitos nos runners GitHub, não em VMs limpas. A aplicação
do update foi exercitada com os artefatos da própria versão `3.0.0`; uma
atualização real de uma instalação `3.0.0` para uma futura `3.0.1` ainda não
foi testada porque essa versão ainda não existe. Também falta validação em VM
limpa e o login MAL continua sem teste com conta real.

Comandos usados para conferir o estado remoto:

```powershell
gh run view 39538571500 --repo henriqqw/AnimeCaos --json conclusion,url,headSha,createdAt
gh release view v3.0.0 --repo henriqqw/AnimeCaos --json url,isDraft,tagName,publishedAt,assets,body
$verifyDir = Join-Path $env:TEMP 'animecaos-release-verify-20261021'
gh release download v3.0.0 --repo henriqqw/AnimeCaos --pattern SHA256SUMS --pattern SHA256SUMS.sigstore.json --pattern WINDOWS-AUTHENTICODE-STATUS.txt --dir $verifyDir
gh api repos/henriqqw/AnimeCaos/releases/latest --jq .tag_name
```

Na rodada local interrompida de 20/10/2026, o empacotador Windows já havia escrito um ZIP
`AnimeCaos-3.0.0-windows-amd64.zip` de 673.047.323 bytes. O compilador Inno
escreveu um arquivo `AnimeCaos-3.0.0-windows-setup.exe` de 235.083.780 bytes,
mas a execução foi interrompida e o código de saída não foi registrado. Esses
dois arquivos foram gerados antes da correção atual do fade sincronizado e do
reinício dev; não são builds finais nem foram verificados para distribuição.
O AppImage citado nesta validação local era da rodada anterior. Naquele momento, nenhuma release tinha sido publicada; a v3.0.0 foi publicada em 21/10/2026 conforme a seção acima.

## Pacotes locais de release — 20/10/2026

Os pacotes `3.0.0` para Windows x64 e Ubuntu 24.04 x86_64 foram recompilados
localmente. Esta rodada não publicou uma release.

| Verificação | Resultado em 20/10/2026 |
|---|---|
| `go test ./... -count=1` no Windows e em Ubuntu 24.04/WSL | Passou. |
| `go test -race ./... -count=1` em Ubuntu 24.04/WSL | Passou. |
| `cd frontend; npm exec -- tsc --noEmit` | Passou. |
| `cd frontend; npm test -- --run --reporter=default` | Passou: 32/32. O harness agora espera a splash inicial carregar antes de testar a interface; uma expectativa de categoria foi alinhada à classe atual do componente. |
| `cd frontend; npm run build` e build disparado pelo empacotador Windows | Passaram; Vite gerou os assets de produção. `npm audit` informou 0 vulnerabilidades. |
| ZIP portátil Windows | Gerado como `AnimeCaos-3.0.0-windows-amd64.zip` (656.458.709 bytes); `zipfile.testzip()` leu todos os arquivos e aprovou CRC. |
| Smoke do executável Windows no stage | Passou: iniciou, criou `state.db` em diretório descartável e usou o WebView2 155.0.4283.62 embarcado. Firefox/GeckoDriver, identificação do WebView2 e MPV com seek também passaram nos testes de runtime. |
| Instalador Inno Setup 6.7.1 | Compilação passou; `AnimeCaos-3.0.0-windows-setup.exe` tem 476.601.378 bytes. Authenticode está `NotSigned`. O teste de instalar/atualizar/desinstalar não foi executado porque já existe uma entrada de desinstalação com o mesmo AppId neste perfil; o script de CI substituiria esse registro. Validar em VM limpa. |
| Firefox/GeckoDriver e MPV no stage Linux | Passaram: fixture de iframe JavaScript; reprodução sintética H.264/AAC, seek e EOF. |
| AppImage | `verify-appimage.sh` passou no Ubuntu 24.04/WSL: inicialização, atualização, testes Firefox/MPV e preservação de `state.db`. A VM/instalação Linux limpa ainda não foi testada. |
| Checksums externos | `sha256sum -c SHA256SUMS` passou para os três pacotes. |

| Arquivo | SHA-256 |
|---|---|
| `AnimeCaos-3.0.0-windows-amd64.zip` | `361bcca5948dad1d220415ce02e75cf99a32601f293827d1f9082f48b1a95f97` |
| `AnimeCaos-3.0.0-windows-setup.exe` | `cb63eae618bae704dbb516a58a9778179d5ac9ea717ee9fdb10f7213760c6a58` |
| `AnimeCaos-3.0.0-x86_64.AppImage` | `67f5eb5dc2fdafc47dd20acd59745560092f1d00ca71c448e3196aefb0300fb0` |

Os relatórios de licenças Go/npm foram regenerados; o inventário npm agora
inclui Three.js. `go-licenses` avisou que não analisa dependências dentro de
alguns arquivos C/assembly, então os relatórios refletem os módulos e avisos
das bibliotecas, mas não substituem uma auditoria manual de código nativo.

Estes são candidatos locais, não pacotes aprovados para publicação pública:
falta assinar os binários Windows, fazer a validação do instalador e dos dois
formatos em máquinas limpas, executar os workflows remotos e resolver o fluxo
OAuth do MyAnimeList/rotacionar o segredo exposto, conforme
[`DISTRIBUTION.md`](DISTRIBUTION.md). Portanto, os testes desta rodada não
garantem ausência absoluta de falhas em todo hardware ou distribuição Linux.

## Prévia local da splash

Para abrir a página de iteração contínua, execute `cd frontend; npm run dev` e
acesse `http://127.0.0.1:5173/splash-preview.html` (ou a porta que o Vite
informar se a padrão estiver ocupada). O ciclo de 8 s simula a barra, faz fade
da mascote e da logo e recomeça sem chamar o backend Wails. “Ajustes da prévia”
permite regular amplitude/velocidade e reiniciar o ciclo. Alterações em TSX/CSS
entram via hot reload. A página serve para comparação visual no navegador; não
substitui medição de desempenho nem inspeção Wails/WebView2.

Em 20/10/2026, a renderização foi migrada para Three.js. A camada base e as
duas mechas laterais são máscaras extraídas do PNG original em runtime; franja,
rosto, chifres e corpo permanecem imóveis. A inspeção visual no navegador
confirmou o enquadramento e a identidade da arte nessa prévia. O balanço é
contínuo e reduz sua amplitude em `prefers-reduced-motion`; não foi feita uma
medição de 60 fps nem uma inspeção no Wails/WebView2.

Na validação dessa alteração, `cd frontend; npm exec -- tsc --noEmit` passou.
As requisições `HEAD` locais para a página, os módulos TSX e as imagens usadas
pela prévia retornaram HTTP 200. `cd frontend; npm test -- --run` terminou com
27 falhas e 5 aprovações em 32 testes: as falhas não encontram os elementos da
interface porque a árvore do app está `aria-hidden` e `inert` enquanto a splash
de produção está ativa no JSDOM. A alteração ficou restrita ao preview e não
foi executado build ou empacotamento.

Na implementação da página em 20/10/2026, `npm exec -- tsc --noEmit` passou.
As requisições locais para a página, os módulos TSX, a arte e a wordmark
retornaram HTTP 200. `npm test -- --run` não passou: 27 de 32 testes em
`App.test.tsx` não encontram os elementos porque a árvore principal permanece
`aria-hidden`/`inert` sob a splash durante a execução no JSDOM; 5 testes passaram.
Essa rodada não mediu 60 fps nem inspecionou a janela Wails.

## Preparação para publicação — 19/10/2026

Esta seção registra a rodada de release sem confundir arquivos de automação com
execuções concluídas. O workflow `.github/workflows/ci.yml` executa testes Go,
race no Ubuntu 24.04, TypeScript e Vitest em runners Windows e Linux. O workflow
`.github/workflows/release.yml` constrói pacotes somente em tags `v*`, valida
assinatura/checksums e roda smoke tests. Os resultados da execução local desta
rodada estão registrados na tabela; o workflow remoto só conta como validado
quando um run real estiver concluído.

O smoke test empacotado cobre inicialização do executável, criação do banco,
importação de um histórico legado por JSON e preservação do backup, update do
ZIP, reinício do processo, preservação byte a byte do banco e desinstalação.
O pipeline testa ainda o MPV empacotado com um vídeo audiovisual sintético,
seek e EOF natural. O smoke do AppImage testa MPV/FFmpeg/FFprobe e
Firefox/GeckoDriver extraídos da imagem, abre o aplicativo, aplica atualização
e confere a preservação de `state.db`. As fixtures Go/TS cobrem busca,
capítulos/leitor, conta OAuth e mutations contra servidores locais; não são
login real, sincronização de conta real nem uma jornada visual em janela
instalada.

| Verificação de release | Resultado nesta rodada |
|---|---|
| `go test ./... -count=1` | Passou no Windows em 19/10/2026 após a correção do teste de timeout. |
| `CGO_ENABLED=1 go test -race ./... -count=1` | Primeira execução identificou leitura concorrente de um timeout global mutável; o timeout foi tornado constante e o teste passou na repetição no Ubuntu 24.04/WSL. |
| `cd frontend; npm exec -- tsc --noEmit` | Passou numa cópia temporária isolada do frontend em 19/10/2026. |
| `cd frontend; npm test -- --run` | Passou: 27/27 testes numa cópia temporária isolada do frontend. |
| ZIP portátil Windows — reconstruído com recursos PE Wails, 19/10/2026 | `AnimeCaos-3.0.0-windows-amd64.zip`, 612.758.558 bytes; SHA-256 `caea18f996575df07d5c68444e52e4557337ffcd51f4bc3f401de6ce680f6938`. Inclui MPV, FFmpeg/FFprobe, Firefox 157.0.1, GeckoDriver 0.37.1 e WebView2 fixo 155.0.4283.62. |
| Instalador Inno Setup — recompilado com o stage novo, 19/10/2026 | `AnimeCaos-3.0.0-windows-setup.exe`, 433.118.388 bytes; SHA-256 `60a83095241671d6fb535e389b5949dbba40bee373a7aa3c673edef19df8b6df`. Compilado por Inno Setup 6.7.1 oficial; sem assinatura Authenticode. A jornada Inno install/update/uninstall e VM limpa não foram executadas nesta rodada. |
| WebView2 do Windows | Wails usou o runtime local 155.0.4283.62 incluído no pacote. A instância empacotada abriu uma janela e renderizou a tela inicial; o teste não substitui uma VM limpa. |
| Firefox e MPV do stage Linux | Firefox/GeckoDriver resolveu o iframe criado por JavaScript; MPV/FFmpeg decodificou H.264/AAC, avançou a posição e fez seek no vídeo de teste. |
| AppImage Ubuntu 24.04 x86_64 — reconstruído, 19/10/2026 | `AnimeCaos-3.0.0-x86_64.AppImage`, 283.871.736 bytes; SHA-256 `5fe8bfcfdf71317e1599527d8fcb56fc1a6f5cb15ce2803fa9bc24a22967cd42`. Firefox 157.0.1, GeckoDriver 0.37.1, MPV e FFmpeg/FFprobe estão incluídos. |
| Startup/update AppImage + banco — reconstruído, 19/10/2026 | `verify-appimage.sh` passou em Ubuntu 24.04/WSL: a imagem abriu, testou iframe JavaScript e MPV H.264/AAC com seek, aplicou atualização e preservou `state.db`. É um smoke local, não validação numa VM limpa. |
| Ícone Windows no executável e instalador | O PE do executável extraído do ZIP e o ícone associado ao instalador Inno foram extraídos com `System.Drawing.Icon.ExtractAssociatedIcon`; inspeção visual confirmou o logo AnimeCaos nos dois. Stage do instalador usa o mesmo executável Wails. A janela após instalação em VM limpa ainda não foi inspecionada. |
| Inno Setup local | Instalador oficial 6.7.1 baixado do GitHub oficial, assinatura Authenticode `Valid` (Pyrsys B.V.) e compilação concluída com `ISCC.exe`. |
| Checksums dos pacotes | `cd /mnt/d/AnimeCaos/release && sha256sum -c SHA256SUMS` passou para o ZIP Windows, instalador Windows e AppImage. |
| AniList/MAL reais | Não executado; fixtures validam o protocolo sem alterar contas externas |

Comandos da reconstrução desta rodada:

```powershell
go run ./cmd/package -version 3.0.0 -skip-ui
& 'D:\AnimeCaos\build\tools\inno-setup-6.7.1\ISCC.exe' '/DPackageDir=D:\AnimeCaos\release\stage-windows-4195403612' '/DAppVersion=3.0.0' 'deploy/go/windows.iss'
```

```bash
export PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export ANIMECAOS_FIREFOX_BUNDLE_DIR=/mnt/d/AnimeCaos/bin/release-linux/firefox
export ANIMECAOS_GECKODRIVER_BUNDLE_PATH=/mnt/d/AnimeCaos/bin/release-linux/geckodriver
cd /mnt/d/AnimeCaos
go run ./cmd/package -version 3.0.0 -skip-ui
bash deploy/go/build-appimage.sh release/stage-linux-1455756168 3.0.0
cd release
sha256sum AnimeCaos-3.0.0-windows-amd64.zip AnimeCaos-3.0.0-windows-setup.exe AnimeCaos-3.0.0-x86_64.AppImage > SHA256SUMS
sha256sum -c SHA256SUMS
```

O compilador Inno Setup 6.7.1 foi baixado do GitHub do fornecedor e a
assinatura Authenticode foi conferida antes da instalação local. Os scripts de
empacotamento substituíram os artefatos e stages anteriores de mesma plataforma
e versão; versões diferentes na pasta `release/` não são removidas.

Comando usado para validar o AppImage final (o executável testado corresponde
ao mesmo hash do arquivo copiado para `release/`):

```bash
wsl -d Ubuntu-24.04 -- bash -lc 'set -e; export PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin; cd /mnt/d/AnimeCaos; bash deploy/go/verify-appimage.sh release/AnimeCaos-3.0.0-x86_64.AppImage /tmp/animecaos-build-verify-20261019-instanceid'
```

O AppImage foi construído com bibliotecas/runtime para Ubuntu 24.04, mas ainda
precisa passar por uma VM/instalação limpa. A compatibilidade declarada não
inclui outras distribuições Linux. A validação do instalador Windows em VM
limpa, a primeira execução remota dos workflows, assinatura de código e
assinatura Sigstore de uma release continuam pendentes.

O cofre Linux exige Secret Service em sessão de usuário; o smoke AppImage em
CI sem daemon de segredos valida a abertura do app, mas não prova criação de
credenciais em GNOME Keyring/KWallet. Rotacione o Client Secret MAL que foi
exposto no suporte antes de qualquer release.

## HTTP 502 ao abrir o instalador Windows — 19/10/2026

A janela de erro era a instância antiga `AnimeCaos-dev.exe`, não o WebView2 do
instalador: dev e produção compartilhavam `com.animecaos.App`, e o processo dev
continuava aberto depois que seu servidor Vite parou. O endpoint local do dev
em `127.0.0.1:34115` respondia HTTP 502. O segundo lançamento da build instalada
foi encaminhado para essa janela pelo mutex compartilhado. Agora os build tags
`dev` e produção selecionam, respectivamente, `com.animecaos.App.dev` e
`com.animecaos.App.production`.

| Comando/validação | Resultado |
|---|---|
| `go test ./... -count=1` | Passou em todos os pacotes Go. |
| `go test -tags desktop,production . -run '^TestAppInstanceIDUsesProductionNamespace$' -count=1` | Passou; a configuração exata de tags do executável empacotado usa o ID de produção. |
| `go test -tags dev . -run '^TestAppInstanceIDUsesDevelopmentNamespace$' -count=1` | Passou; a build `dev` usa seu próprio ID. |
| `Invoke-WebRequest -Uri 'http://127.0.0.1:34115/' -TimeoutSec 4 -UseBasicParsing` | Reproduziu HTTP 502 no servidor Vite da instância dev antiga. |
| Executável Windows do stage iniciado com `ANIMECAOS_DATA_DIR` isolado enquanto o PID dev 105132 permanecia ativo | Processo empacotado separado (PID 107500), banco de teste criado e homepage renderizada em janela 1280×820. A janela usada era a cópia do executável incluído no instalador, não uma instalação Inno; a jornada de instalação permanece pendente. |
| `bash deploy/go/verify-appimage.sh release/AnimeCaos-3.0.0-x86_64.AppImage /tmp/animecaos-build-verify-20261019-instanceid` | Passou em Ubuntu 24.04/WSL: app abriu, atualização aplicada e banco preservado. |

Smoke Windows usado para separar o diretório de dados da instalação real:

```powershell
$env:ANIMECAOS_DATA_DIR='D:\AnimeCaos\build\instance-id-smoke-20261019'
Start-Process -FilePath 'D:\AnimeCaos\release\stage-windows-3181843791\AnimeCaos.exe'
```

## AniList e MyAnimeList — conta e sincronização automática — 19/10/2026

Configurações e a tela Contas compartilham cards com os favicons locais, estado da conexão, login pelo navegador, atualizar perfil, desconectar e erro de OAuth. Os campos de Client ID/Secret MAL foram removidos da interface; o Client ID é configuração do app, e um segredo previamente salvo continua no cofre para compatibilidade. O teste de integração frontend foi ajustado para o Rich Presence como switch e não configura segredo pela tela. O jogador só marca o episódio como assistido no EOF natural ou quando encerra com pelo menos 80% da duração conhecida; a sincronização consulta a lista antes de escrever, não regride o progresso e mantém obras concluídas. As gravações de lista foram verificadas contra fixtures HTTP, sem utilizar uma conta real.

| Comando/validação | Resultado |
|---|---|
| `go test ./... -count=1` (reexecução em 19/10/2026) | Passou em todos os pacotes. A tentativa anterior descrita abaixo recebeu `net::ERR_UNSAFE_PORT` em fixture Chromium e passou na repetição. |
| `cd frontend; npm exec -- tsc --noEmit` (19/10/2026) | Passou sem diagnósticos. |
| `cd frontend; npm test -- --run` (19/10/2026) | A primeira execução teve 26/27: falhou o teste de navegação das setas do destaque. A repetição completa passou com 27/27; o teste isolado também passou. O teste de integrações conferia logos, configuração local do Client Secret, conexão AniList e perfil antes da remoção dos campos. |
| `TestSyncUpdatesMALListAtWatchThreshold`, `TestSyncMarksAniListCompleteOnlyAtFinalEpisode`, `TestSyncDoesNotMoveMALProgressBackwards`, `TestMALTokenExchangeUsesBasicClientAuthentication` e `TestMALRefreshUsesBasicAuthenticationAndPreservesRefreshToken` | Passaram dentro do pacote `internal/integrations`; verificam leitura prévia, headers, HTTP Basic com segredo, renovação, progresso, status, proteção contra regressão e mutations contra `httptest`. |
| `TestEpisodeWatchedRequiresEOFOrEightyPercent` | Passou dentro do pacote `internal/player`; fechar aos 31 s ou sem duração não marca como assistido. |
| Download de `https://anilist.co/favicon.ico` e `https://myanimelist.net/favicon.ico` | Ambos responderam HTTP 200; os favicons foram guardados em `frontend/public/`. |
| OAuth com uma conta real e confirmação das listas externas | Não executado: exige autorização da conta do usuário e altera dados nas listas. A atualização HTTP está coberta por fixtures locais. |

`go env CGO_ENABLED` retornou `0`; `go test -race ./...` não foi executado neste ambiente. `git diff --check` passou com avisos de normalização LF/CRLF nos arquivos modificados.

O endpoint OAuth do MAL redirecionou o Client ID do app para a página de login (HTTP 303). A troca do código falso no endpoint de token com autenticação Basic e senha vazia retornou `invalid_client`. Os controles de credenciais foram removidos da tela do usuário; o login de primeira conexão continua pendente até o cadastro OAuth do AnimeCaos suportar cliente público para desktop ou usar um intermediário seguro. Não foi usado código real nem conta autenticada.

### Interface de integrações — 20/10/2026

Os campos MAL de cadastro OAuth saíram de Configurações e o Client ID passou a ser resolvido internamente pelo serviço. Um segredo que já esteja no cofre permanece disponível para a integração nesta instalação. O controle de Rich Presence Discord foi convertido para switch e as instruções do Developer Portal foram retiradas da interface. A suíte TypeScript/frontend não foi executada nesta alteração.

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

## Catálogo e leitor de mangá — 19/10/2026

O catálogo não consulta títulos vazios ao abrir. A pesquisa tem estado local de erro/retry e cancela a operação anterior. O leitor busca novamente as URLs ao abrir/retomar um capítulo, salva a página atual e oferece rolagem contínua, página única, direção RTL/LTR, atalhos, controles de página e capítulo; falhas de rede e de imagem exibem retry. Capítulos exibem o grupo de tradução quando a API retorna esse relacionamento. URLs temporárias não entram no histórico.

| Comando/validação | Resultado |
|---|---|
| `ANIMECAOS_LIVE=1 go test ./internal/manga -run '^TestLiveMangaDex$' -count=1 -v` | Passou em 6,34 s: MangaDex retornou One Piece, 61 capítulos em português; páginas foram consultadas, a primeira página `data-saver` respondeu e um CBZ legível com 53 páginas foi criado. Foi executado em Windows via PowerShell com `$env:ANIMECAOS_LIVE='1'`. |
| `go test ./...` | Passou em todos os pacotes após redirecionar `TEMP`, `TMP`, `GOTMPDIR` e `GOCACHE` para `D:\AnimeCaos\.task-cache`, pois o temporário padrão no C: não tinha espaço livre. |
| `cd frontend; npm exec -- tsc --noEmit` | Passou após implementar o fluxo de leitor. |
| `cd frontend; npm test -- --run` | Passou: 26 testes, incluindo pesquisa → capítulos → páginas, progresso salvo e retry de erro de páginas. |
| Inspeção visual da janela Wails | Não executada nesta sessão: a inicialização de automação de tela falhou antes de disponibilizar a janela. A inspeção manual permanece pendente. |

## Pesquisa contextual de mangás — 19/10/2026

O campo global muda o nome acessível e o placeholder para “Buscar mangás...” no catálogo, na lista de capítulos e no leitor. Enviar uma consulta a partir dessas telas abre o catálogo com essa busca; `Ctrl+K` foca o mesmo campo sem trocar para a área de animes. Fora das rotas de mangá, a busca de animes mantém seu fluxo atual.

| Comando/validação | Resultado |
|---|---|
| `cd frontend; npm exec -- tsc --noEmit` | Passou em 19/10/2026 numa cópia isolada do frontend; dependências não estavam instaladas no `frontend/node_modules` do projeto. |
| `cd frontend; npm test -- --run` | Passou: 27/27 testes em 19/10/2026 na mesma cópia. O teste de interface percorre catálogo → capítulos → leitor, envia a busca pelo cabeçalho e verifica o atalho `Ctrl+K`. |

O teste Go inicial falhou ao tentar criar o temporário em `C:\Users\caosdev\AppData\Local\Temp` (C: sem espaço). Usar temporários/cache no D: permitiu executar o live. O acesso HTTPS direto pelo `Invoke-WebRequest`/Schannel também falhou com `ProtocolVersion`, mas o cliente Go do aplicativo consultou MangaDex com sucesso. O usuário não precisa mudar DNS por causa desse resultado local.

## Restauração da janela e menu da bandeja Windows — 19/10/2026

A janela `AnimeCaos` estava fora da tela nas coordenadas `-32000,-32000` enquanto o processo permanecia responsivo. No Windows, a posição salva agora é comparada às áreas úteis de todos os monitores; uma barra de título sem área visível faz o app centralizar a janela. Fechar pelo X oculta a janela na bandeja, cujo menu oferece abrir, minimizar, ocultar e sair.

| Comando/ação | Resultado |
|---|---|
| `gofmt -w main.go internal/platform/window_position.go internal/platform/window_position_windows.go internal/platform/window_position_other.go internal/platform/window_position_test.go internal/platform/tray_windows.go internal/platform/tray_other.go` | Passou |
| `go mod tidy` | Passou; incluiu `github.com/getlantern/systray` para o adaptador Windows |
| `go test ./internal/platform -count=1` | Passou, incluindo casos dentro do monitor, monitor lateral, barra parcialmente visível, coordenadas minimizadas e título abaixo da área útil |
| `go test ./...` | Passou em todos os pacotes |
| `cd frontend; npm exec -- tsc --noEmit` | Passou |
| `cd frontend; npm test -- --run` | Passou: 24 testes |
| `go env CGO_ENABLED` | Retornou `0`; `go test -race ./...` não foi executado |
| `git diff --check` | Passou sem erros de whitespace; Git emitiu avisos de normalização LF/CRLF em arquivos alterados |
| Sessão `wails dev` no Windows | Processo `AnimeCaos-dev` permaneceu responsivo; a janela foi iniciada em coordenadas visíveis após rejeitar a posição antiga |
| Fechar via `WM_CLOSE` e abrir pelo menu da bandeja | Fechamento ocultou a janela sem encerrar o processo. O menu nativo foi exibido com as quatro ações; selecionar `Abrir AnimeCaos` restaurou a janela visível em `350,130`, tamanho `900×600` |

A bandeja foi verificada na sessão local Windows de desenvolvimento; não houve build de distribuição. Linux e macOS ainda não têm adaptador de bandeja nesta etapa.

## Remoção de integrações de catálogo — 18/10/2026

- `gofmt -w internal/app/service.go internal/providers/browser.go internal/providers/catalog_test.go internal/providers/live_ad_audit_test.go internal/providers/player_candidates.go internal/providers/player_candidates_test.go internal/providers/browser_test.go internal/providers/selenium.go internal/providers/selenium_test.go` — passou.
- `go test ./... -count=1` — passou em todos os pacotes Go.
- A busca textual final pela árvore ativa não encontrou referências aos adaptadores removidos nem aos seus seletores específicos.

## Identificação de adaptações nos cards de busca — 18/10/2026

Uma consulta live `hunter` confirmou que as duas adaptações continuavam no resultado apesar do aviso de prazo: AniList 136 (1999), aprovada pela SushiAnimes, e AniList 11061 (2011), aprovada pela Otakulogia. O título sozinho deixava os cards visualmente ambíguos. A UI passou a mostrar ano e número de episódios a partir da identidade canônica. Não há consulta adicional por card para esses campos; `startDate.year`, `format` e `episodes` vêm na mesma resposta GraphQL em lote. A prévia em hover usa o AniList ID quando confirmado, evitando consultar o remake de 1999 apenas porque ambas as obras aparecem como “Hunter x Hunter”.

| Comando | Resultado |
|---|---|
| `$env:ANIMECAOS_LIVE='1'; $env:ANIMECAOS_LIVE_TITLE='hunter'; go test ./internal/app -run '^TestLiveSearchAvailabilityTenAnimeSamples$' -count=1 -v` | Passou em 16,152 s: 8 cards reproduzíveis; Hunter x Hunter 1999 (AniList 136) validado pela SushiAnimes e 2011 (AniList 11061) pela Otakulogia. Aviso de prazo permaneceu para outros candidatos. |
| `gofmt -w internal/domain/models.go internal/integrations/anilist.go internal/integrations/anilist_test.go internal/providers/catalog.go internal/providers/catalog_test.go internal/providers/otakulogia.go internal/app/service.go internal/app/service_test.go` | Passou. |
| `go test ./...` | Primeira execução encontrou falha no teste novo por falta de alias no fixture; após completar o título canônico, reexecução passou em todos os pacotes. |
| `npm exec -- tsc --noEmit` | Primeira execução apontou matcher DOM indisponível no teste; após trocar para a asserção nativa de `textContent`, passou. |
| `npm test -- --run` | Primeira execução: 23/24 passaram; a única falha usava o mesmo matcher DOM ausente. Após ajuste, 24/24 passaram. |
| `go env CGO_ENABLED` | Retornou `0`; `go test -race ./...` não foi executado porque CGO está desativado. |
| `git diff --check` | Passou sem erros de whitespace; Git avisou que normalizará LF para CRLF nos arquivos editados. |

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

### Refatoração de Configurações — 18/10/2026

- `cd frontend; npm exec -- tsc --noEmit` — passou.
- `cd frontend; npm test -- --run` — passou: 24 testes.
- `git diff --check` — passou; Git emitiu avisos de normalização LF/CRLF nos arquivos modificados, sem erros de whitespace.

Os testes automatizados incluem o acesso semântico ao tema na tela de Configurações. A checagem confirma tipos e regressões existentes; inspeção visual em diferentes tamanhos de janela desktop não foi realizada nesta rodada.

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

## Responsividade em janela compacta — 19/10/2026

A janela de desenvolvimento foi inspecionada em 900×600 px na tela Configurações. A correção removeu a largura de 145 px da sidebar e compactou o espaçamento entre ícone e rótulo até 1050 px; a captura confirmou que “Configurações” e os demais itens aparecem completos. Abaixo de 760 px permanece a navegação inferior. Não houve alteração de componentes nem de cobertura automatizada.

| Verificação | Resultado |
|---|---|
| Inspeção visual da janela `AnimeCaos-dev` em 900×600 | Rótulos da sidebar completos; painel de Configurações continuou rolável e os cartões de integração permaneceram lado a lado |
| `cd frontend; npm exec -- tsc --noEmit` | Passou sem diagnósticos TypeScript |
| `git diff --check` | Passou; Git avisou apenas que normalizará LF para CRLF nos arquivos alterados |
| Testes automatizados | Não executados nesta alteração de CSS |

## Integração visual e OAuth Discord — 20/10/2026

A tela de integrações agora exibe o símbolo local do Discord, um controle de Rich Presence com indicação Ativo/Desativado e instruções curtas para configurar o nome, ícone e asset `logo` no Developer Portal. Os cartões de Discord/AniList/MAL ajustam as colunas ao espaço disponível. A tela Contas explica que o Discord identifica o perfil; o histórico assistido é sincronizado apenas pelo AniList/MAL.

O OAuth Discord usa callback loopback, `state`, `iss`, PKCE S256 e gravação no cofre seguro. Fixtures validam o fluxo de sucesso e a recusa/cancelamento com retorno imediato. O teste de presença valida payload, anime/episódio, relógio MPV, pausa e retomada.

| Comando | Resultado |
|---|---|
| `go test ./internal/integrations ./internal/app ./internal/netx` | Passou |
| `go test ./...` | Passou em todos os pacotes |
| `cd frontend; npm exec -- tsc --noEmit` | Passou sem diagnósticos TypeScript |
| `cd frontend; npm test -- --run` | Passou: 27 testes |
| `go env CGO_ENABLED` | `0`; `go test -race ./...` não foi executado porque CGO está desabilitado |
| `git diff --check` | Passou; Git avisou sobre normalização LF/CRLF em arquivos modificados |

Não foi possível validar a autorização com uma conta real nem a presença no Discord Desktop nesta rodada. Para testar o fluxo externo, o Developer Portal precisa ter o cliente público habilitado e a URI `http://127.0.0.1:9744/` registrada. Para a imagem no perfil, configure o nome/ícone da aplicação e a arte com a chave `logo`. Até essa validação, o estado de conta real e a apresentação da arte permanecem pendentes.

## Refatoração de Configurações — 20/10/2026

A tela agora usa seções abertas em uma coluna, índice contextual, resumo de integrações e persistência automática. A fila de Configurações pertence ao `App`: aplica alterações imediatamente, aguarda 350 ms para agrupar edições, serializa chamadas Wails e mantém a escolha quando há falha. Manutenção tem feedback independente. Os testes DOM cobrem debounce/coalescência, ausência de gravação ao abrir, gravações em sequência, retry, navegação ao índice e Contas, ativação de switch pela barra de espaço e campos condicionais.

| Verificação | Resultado nesta rodada |
|---|---|
| Executado no diretório `frontend/`: `npm exec -- tsc --noEmit` | Passou sem diagnósticos TypeScript em 20/10/2026. |
| Executado no diretório `frontend/`: `npm test -- --run` | Passou: 30/30 testes DOM em 20/10/2026. |
| `git diff --check` na raiz | Passou sem erros de whitespace; o Git emitiu avisos de normalização LF/CRLF em arquivos já modificados na árvore de trabalho. |
| Inspeção visual Wails em 1440×900, 1280×720, 960×600, 760 px e largura móvel | Pendente. A tentativa de iniciar o helper Computer Use falhou ao criar os assets do kernel (`The system cannot find the path specified`); nenhuma ação foi feita na janela do app. O CSS responsivo e os testes DOM foram revisados. |

## Descoberta da página de Mangás — 20/10/2026

A entrada de Mangás agora segue a descoberta da Home: destaque manual com navegação, prateleiras de títulos populares, capítulos adicionados recentemente e obras em publicação, gêneros do catálogo MangaDex e retomada de leitura. A API MangaDex é a fonte dos metadados; o bloco “Em alta” mede atividade de publicação recente, não audiência. O catálogo MangaDex não fornece uma temporada de anime confiável para classificar mangás, então a tela não inventa essa relação.

| Comando/verificação | Resultado nesta rodada |
|---|---|
| `go test ./...` | Passou em todos os pacotes. |
| Executado em `frontend/`: `npm exec -- tsc --noEmit` | Passou sem diagnósticos TypeScript. |
| Executado em `frontend/`: `npm test -- --run` | Passou: 31 testes. |
| `go env CGO_ENABLED` | Retornou `0`; `go test -race ./...` não foi executado porque CGO está desabilitado. |
| `git diff --check` | Passou sem erros de whitespace; Git avisou que arquivos alterados com LF podem ser normalizados para CRLF. |
| Consulta live das novas prateleiras e inspeção visual na janela Wails | Pendentes. Os testes usam fixtures e DOM; não comprovam disponibilidade live nem acabamento visual em cada resolução. |

## Paridade visual entre Mangás e Home — 20/10/2026

A rota de Mangás passou a reutilizar o banner `spotlight`, os cabeçalhos `shelf-heading`, os trilhos `home-shelf`/`Rail`, os cartões de pôster para retomada e a largura de conteúdo da Home. A busca embutida no destaque foi removida; o cabeçalho contextual é o campo único para buscar mangás. O teste DOM confirma o banner compartilhado, uma única caixa de busca, cartão de retomada, descoberta por gênero e abertura do fluxo de capítulo.

| Comando/verificação | Resultado nesta rodada |
|---|---|
| Executado em `frontend/`: `npm exec -- tsc --noEmit` | Passou sem diagnósticos TypeScript. |
| Executado em `frontend/`: `npm test -- --run` | Passou: 31 testes. |
| `git diff --check` | Passou sem erros de whitespace; avisos de normalização LF/CRLF podem aparecer nos arquivos já modificados. |
| Inspeção visual Wails em janela | Pendente; a revisão desta correção comparou a estrutura JSX/CSS compartilhada e validou o contrato pelo DOM. |

## CTA das capas na Home — 20/10/2026

As capas de “Continuar assistindo”, “Em alta” e “Temporada atual” revelam “Ver anime” no hover e no foco de teclado. A sobreposição não é um controle separado: ativar o card preserva o destino e a ação já existentes. A animação da sobreposição é desligada com `prefers-reduced-motion`. Um teste DOM cobre as três prateleiras e a navegação de um card para a busca.

| Comando/verificação | Resultado nesta rodada |
|---|---|
| Executado em `frontend/`: `npm exec -- tsc --noEmit` | Passou sem diagnósticos TypeScript. |
| Executado em `frontend/`: `npm test -- --run` | Passou: 32 testes. |
| `git diff --check` | Passou sem erros de whitespace. Git avisou que arquivos já alterados na árvore de trabalho podem ser normalizados de LF para CRLF. |

## Prévia de sinopse nas capas de mangá — 20/10/2026

As capas das prateleiras de descoberta exibem um painel com título e sinopse após hover ou foco. A implementação usa o campo `description` já carregado pelo catálogo e não consulta `Preview` nem outro endpoint por card. Os textos auxiliares dos cabeçalhos das seções foram removidos; a ficha mantém o status junto ao título do card.

| Comando/verificação | Resultado nesta rodada |
|---|---|
| Executado em `frontend/`: `npm exec -- tsc --noEmit` | Passou sem diagnósticos TypeScript. |
| Executado em `frontend/`: `npm test -- --run` | Passou: 32 testes DOM; inclui painel, sinopse, associação `aria-describedby`, ausência de chamada por card e remoção dos subtítulos de seção. |
| `git diff --check` | Passou sem erros de whitespace; avisos de normalização LF/CRLF foram emitidos para arquivos já modificados na árvore. |

## Artes da mascote AnimeCaos — 20/10/2026

As artes v3 registram a personagem com cabelo vermelho longo, liso e repartido ao meio, saia preta lisa e contorno preto. A versão mini é superdeformed, com cabeça maior e corpo simplificado; a cópia de 256×256 px foi derivada dela. O diretório `poses/` contém seis vistas (frente, perfis, fisheye e costas) e uma pose adicional de piscada. O diretório `reactions/` contém dez expressões. A integração visual aos cards de categoria ainda não foi feita.

| Verificação | Resultado nesta rodada |
|---|---|
| Inspeção PowerShell com `System.Drawing.Bitmap` (`Width`, `Height`, alpha de `(0,0)` e pixel central) | Normal e mini v3: 1254×1254, alpha 0 no canto e 253 no centro. Miniatura: 256×256, alpha 0 no canto e 252 no centro. As sete poses e dez reações também têm alpha 0 no canto e conteúdo visível no centro. |
| Testes TypeScript e DOM | Não executados: esta rodada altera apenas PNGs e documentação, sem componentes ou comportamento. |
