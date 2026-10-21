# AnimeCaos Go — preparação de release

O aplicativo usa Go, Wails 2, React e TypeScript. Os pacotes gerados por
`go run ./cmd/package` incluem MPV, FFmpeg/FFprobe, Firefox, GeckoDriver, DLLs
de runtime do MPV no Windows, ícones, documentação, avisos e manifesto SHA-256.
O build não inclui o código Python legado, yt-dlp ou ambientes Python.

## Execução

- Windows: o instalador e o ZIP portátil levam MPV, FFmpeg/FFprobe,
  Firefox/GeckoDriver e o runtime WebView2 fixo em `bin/`. O app aponta o Wails
  para essa cópia; não exige Firefox, MPV, Edge ou WebView2 previamente
  instalados nem conexão com a internet para baixar esses componentes. No
  primeiro uso, o app concede leitura ao AppContainer do Windows para que o
  WebView2 fixo funcione também em instalações portáteis e no Windows 10.
  Como essa cópia não se atualiza sozinha, a pipeline precisa incorporar um
  runtime WebView2 corrigido em cada ciclo de release.
- Linux x86_64: o alvo definido para release é AppImage criado em Ubuntu 24.04
  LTS. O pacote inclui Firefox, GeckoDriver, MPV e FFmpeg/FFprobe e suas
  bibliotecas de execução; GTK/WebKitGTK e bibliotecas selecionadas também são
  incorporados pelo pipeline. O Linux ainda depende do kernel, do servidor
  gráfico e da compatibilidade glibc definida pelo AppImage. Flatpak não é
  distribuído.
- Terminal: `animecaos-cli doctor`, `search --query naruto`, `interactive`,
  `interactive --continue`. Use `details --id ID` para obter IDs dos episódios.

Dados: `%APPDATA%/AnimeCaos` no Windows e `~/.local/state/AnimeCaos` no Linux.
Os JSON antigos são preservados, copiados para `legacy-backup` e importados
uma vez em `state.db`. Use `ANIMECAOS_DATA_DIR` para uma instalação isolada.

## Build sem Python

Requer a versão do Go declarada em `go.mod` e Node.js/npm compatíveis com Vite/TypeScript travados no lockfile. No Windows, o empacotador executa a CLI Wails na mesma versão fixada em `go.mod`; isso gera os recursos PE de ícone, manifesto e versão antes de montar o ZIP e o instalador. O `go run` baixa a CLI se necessário. Na raiz:

```
go run ./cmd/package -version 3.0.1
```

Sem `-skip-ui`, o empacotador executa `npm ci` e `npm run build` antes de compilar o executável. `main.go` incorpora `frontend/dist` no app, incluindo a tela e as imagens da splash; portanto, o pacote padrão apresenta a splash ao abrir. `-skip-ui` reutiliza o diretório compilado existente e só deve ser usado quando ele já contém a versão desejada da interface.

O empacotador remove stages antigos da mesma plataforma antes de criar o novo
e substitui o ZIP/instalador ou AppImage de mesmo nome e versão. Entradas
anteriores desses nomes são removidas do manifesto SHA-256. Arquivos de outras
versões continuam preservados.

Antes do build, o pipeline baixa Firefox 157.0.1, GeckoDriver 0.37.1 e WebView2
Fixed Version 155.0.4283.62 dos fornecedores oficiais, valida hashes ou
assinaturas digitais e instala os runtimes em `bin/`. MPV, FFmpeg e FFprobe
também são obtidos nas versões fixadas da pipeline. O empacotador falha se
qualquer runtime estiver ausente; não usa PATH para preencher pacotes
incompletos. `release-manifest.json` registra o hash de cada arquivo
distribuído. No WebView2, o executável principal precisa ter assinatura
Microsoft válida; todos os EXEs/DLLs do CAB oficial precisam ter uma assinatura
Authenticode válida do fornecedor correspondente. O pacote inclui
`widevinecdm.dll`, assinado pelo Google, por isso a verificação não exige que
esse componente de terceiros use o certificado Microsoft.

No AppImage, o Firefox e o GeckoDriver são copiados com os bytes originais. O
`linuxdeploy` altera RPATH de executáveis durante a coleta; por isso o script
restaura os dois runtimes depois dessa etapa e gera a imagem final diretamente
com o `appimagetool` incluído na ferramenta. `verify-appimage.sh` abre o
AppImage, extrai e testa os próprios executáveis distribuídos e valida uma
atualização com preservação do banco. O workflow resolve o stage para caminho
absoluto antes de executar testes Go: `go test` muda o diretório de trabalho
para o diretório do pacote, portanto caminhos relativos ao repositório não
identificam corretamente os runtimes no stage.

## Dependências de terceiros

- Wails: https://github.com/wailsapp/wails (MIT).
- React: https://github.com/facebook/react (MIT).
- MPV: https://mpv.io/ e https://github.com/mpv-player/mpv (GPL/LGPL conforme build).
- FFmpeg: https://ffmpeg.org/ (GPL/LGPL conforme build). O build Windows usado
  nos testes veio de https://www.gyan.dev/ffmpeg/builds/, indicado pelo projeto
  FFmpeg. FFmpeg/FFprobe 9.0.2 essentials; SHA-256 do ZIP original:
  `60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba`.
- Microsoft Edge WebView2 Fixed Version 155.0.4283.62 x64: o runtime completo
  está no pacote Windows; versão, URL oficial, validação de assinatura e aviso
  de atualização ficam em [`licenses/SOURCE-OFFERS.md`](../licenses/SOURCE-OFFERS.md).
- Firefox 157.0.1 e GeckoDriver 0.37.1, com hashes e termos MPL em
  [`licenses/SOURCE-OFFERS.md`](../licenses/SOURCE-OFFERS.md).

O estágio exige `THIRD-PARTY-NOTICES.md` e `licenses/`. O pipeline recolhe
avisos de dependências Go/npm, metadados/licenças dos pacotes MPV/FFmpeg e a
configuração/hash de cada binário. A saída AppImage também carrega avisos dos
pacotes Debian que fornecem as bibliotecas empacotadas. As fontes e proveniência
de mídia estão em [`licenses/SOURCE-OFFERS.md`](../licenses/SOURCE-OFFERS.md).

## CI, assinatura e publicação

- `.github/workflows/ci.yml` roda `go test ./...`, `go test -race ./...` no
  Linux, TypeScript e Vitest em runners Windows e Ubuntu 24.04.
- `.github/workflows/release.yml` só inicia em uma tag `v*`, repete as
  validações, gera portátil/instalador Windows e AppImage, executa os smoke
  tests de instalação/update e publica checksums assinados com Sigstore.
- Com os secrets `WINDOWS_CERTIFICATE_PFX_BASE64` e
  `WINDOWS_CERTIFICATE_PASSWORD`, o workflow assina EXE e instalador com
  Authenticode e verifica as assinaturas. Sem os dois secrets, publica os
  pacotes Windows sem Authenticode e registra essa condição nas notas e num
  arquivo da release. A assinatura Sigstore de `SHA256SUMS` continua ativa;
  ela não substitui o certificado Authenticode nem elimina o aviso de editor
  desconhecido do Windows.
- A versão da tag deve coincidir com `wails.json` e com o `-version` do pacote.
  A versão padrão atual é `3.0.1`. O atualizador verifica a release no começo
  da splash, usa um limite de 8 s para a consulta, baixa o pacote com limite de
  30 min, confere `SHA256SUMS` e aplica ZIP Windows/AppImage antes de liberar a
  interface. O fluxo não vale para `wails dev` ou Flatpak.
- A release histórica `v2.0.0` para Windows tem um atualizador Python que
  consulta a mesma API e escolhe o ZIP Windows. Na primeira versão 3.x, ela
  detecta a versão nova e pede confirmação para copiar o ZIP. Depois da
  migração, as próximas versões 3.x são aplicadas automaticamente. O atualizador
  legado não valida SHA-256; releases precisam ser servidas pela API oficial do
  GitHub via HTTPS. A linha Go/Wails valida SHA-256 antes de substituir os
  arquivos. A antiga edição Flatpak não sabe instalar o AppImage e exige
  migração manual para esse formato.

## Release v3.0.0 publicada — 21/10/2026

A release [v3.0.0](https://github.com/henriqqw/AnimeCaos/releases/tag/v3.0.0)
foi publicada pelo workflow
[39538571500](https://github.com/henriqqw/AnimeCaos/actions/runs/39538571500),
com os testes Windows e Ubuntu, o smoke do AppImage e a jornada Windows de
instalação, update, reinício, desinstalação e preservação do banco aprovados.
O workflow criou `SHA256SUMS` e a assinatura Sigstore keyless; o manifesto e
seu bundle estão anexados à release. O endpoint `/releases/latest` retorna
`v3.0.0`, que passa a ser a versão consultada pelo atualizador.

Os três arquivos de distribuição e seus hashes publicados são:

| Arquivo | Tamanho | SHA-256 |
|---|---:|---|
| `AnimeCaos-3.0.0-windows-amd64.zip` | 669.956.620 bytes | `ffe5763dc1ff627b69dd5953741db1f19f2c2100547ccda64723ed38823a4f0b` |
| `AnimeCaos-3.0.0-windows-setup.exe` | 489.729.270 bytes | `0ff74ab5b19b6698a52b813a5121975af31d48a01e25cb3fbf613e50224a15dc` |
| `AnimeCaos-3.0.0-x86_64.AppImage` | 342.960.632 bytes | `a73c2ed323eaf1c0cd0396c0e16ed1054cb8973a92053ea545540e0ca42450da` |

Os hashes do manifesto correspondem aos digests SHA-256 dos três assets no
GitHub. A publicação também contém `SHA256SUMS.sigstore.json` e
`WINDOWS-AUTHENTICODE-STATUS.txt`. Sem os secrets de certificado, o ZIP e o
instalador Windows não têm Authenticode; o Windows pode exibir aviso de editor
desconhecido. A assinatura Sigstore comprova a origem/integridade do manifesto,
mas não substitui Authenticode.

O smoke da release foi executado em runners GitHub, não em VMs limpas. A
checagem e a aplicação do update foram exercitadas com os pacotes da própria
versão `3.0.0`; uma atualização real de uma instalação `3.0.0` para uma futura
`3.0.1` ainda precisa ser observada quando houver essa release. O fluxo de
primeira conexão MAL também permanece sem validação com conta real.

## Validação manual ainda exigida

O script Windows testa execução do portátil, confirmação de que o processo
WebView2 veio de dentro do pacote, GeckoDriver/Firefox empacotados, MPV, banco
de dados, update, reinício, desinstalação e preservação de dados. A validação
em VM limpa do instalador Windows ainda é necessária para confirmar a jornada
offline numa instalação sem WebView2 prévio. Em uma futura versão, validar
atualização de N para N+1, recuperação depois de download corrompido e dados
antigos reais em cópia descartável.

O alvo Linux da release é Ubuntu 24.04 LTS x86_64. O AppImage passou no runner
24.04; deve ser repetido numa instalação limpa de Ubuntu 24.04. Compatibilidade
com outras distribuições ainda não é declarada.

## Contas

MyAnimeList usa o Client ID interno da aplicação e PKCE, sem pedir credenciais de desenvolvedor ao usuário nem embutir Client Secret no pacote. O fluxo real ainda não foi confirmado sem segredo: a troca de token retornou `invalid_client`. Antes da publicação, use um cadastro público compatível com desktop ou um serviço intermediário que proteja eventual segredo.
Antes de outra release, resolva a validação do login real. Callback cadastrado:
`http://localhost:9743/`.
AniList usa o fluxo implícito para cliente público, callback
`http://localhost:9742`. Tokens e segredos ficam no cofre de credenciais do
sistema operacional; as instalações antigas migram os valores do SQLite para
esse cofre na primeira execução.

## Validação disponível

```
go test ./...
go test -race ./internal/...
cd frontend
npm ci
npm test
npm run build
```

Testes externos são opt-in: `ANIMECAOS_LIVE=1` para as fontes e MangaDex,
`ANIMECAOS_BROWSER_TEST=1` para iframe JavaScript em Firefox/GeckoDriver, e
`ANIMECAOS_PLAYER_TEST=1` para decodificação/seek MPV com mídia gerada pelo
FFmpeg. Nos testes do pacote, os caminhos apontam para os runtimes dentro do
stage; o usuário final não precisa de versões previamente instaladas no PATH.
