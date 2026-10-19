# AnimeCaos Go — distribuição em validação

O aplicativo usa Go, Wails 2, React e TypeScript. Os pacotes gerados por
`go run ./cmd/package` contêm somente os executáveis, dependências de mídia,
ícones, documentação e um manifesto SHA-256. Python, Selenium, geckodriver e
yt-dlp não são usados pelo aplicativo Go nem por esse comando de build.

## Execução

- Windows: execute `AnimeCaos.exe`. É necessário Microsoft Edge WebView2 Runtime.
  Quando presente no pacote, `bin/MicrosoftEdgeWebview2Setup.exe` é o instalador
  oficial do runtime. O portátil usa os mesmos dados da instalação normal.
- Linux: GTK 3 e WebKitGTK 4.1 são necessários para o binário sem empacotamento.
  A validação de AppImage/Flatpak e das dependências incluídas ainda está pendente.
- Terminal: `animecaos-cli doctor`, `search --query naruto`, `interactive`,
  `interactive --continue`. Use `details --id ID` para obter IDs dos episódios.

Dados: `%APPDATA%/AnimeCaos` no Windows e `~/.local/state/AnimeCaos` no Linux.
Os JSON antigos são preservados, copiados para `legacy-backup` e importados
uma vez em `state.db`. Use `ANIMECAOS_DATA_DIR` para uma instalação isolada.

## Build sem Python

Requer a versão do Go declarada em `go.mod` e Node.js/npm compatíveis com Vite/TypeScript travados no lockfile. Na raiz:

```
go run ./cmd/package -version 3.0.0-dev
```

O build precisa encontrar MPV, FFmpeg e FFprobe em `bin/` ou no PATH. Os
binários são copiados para o pacote, nunca baixados ou substituídos em silêncio.
O arquivo `release-manifest.json` registra o hash de cada arquivo distribuído.

## Dependências de terceiros

- Wails: https://github.com/wailsapp/wails (MIT).
- React: https://github.com/facebook/react (MIT).
- MPV: https://mpv.io/ e https://github.com/mpv-player/mpv (GPL/LGPL conforme build).
- FFmpeg: https://ffmpeg.org/ (GPL/LGPL conforme build). O build Windows usado
  nos testes veio de https://www.gyan.dev/ffmpeg/builds/, indicado pelo projeto
  FFmpeg. FFmpeg/FFprobe 9.0.2 essentials; SHA-256 do ZIP original:
  `60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba`.
- Microsoft Edge WebView2: https://developer.microsoft.com/microsoft-edge/webview2/.

Antes de publicar uma release, anexar as licenças e os fontes correspondentes
aos builds exatos das dependências. O pacote local é de desenvolvimento;
não representa conclusão da matriz de paridade nem validação de instalação limpa.

## Contas

MyAnimeList usa Client ID público e PKCE, sem Client Secret embutido.
Callback cadastrado: `http://localhost:9743/`.
AniList usa o fluxo implícito para cliente público, callback
`http://localhost:9742`. Os tokens permanecem no diretório de dados local.

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
`ANIMECAOS_PLAYER_TEST=1` para o MPV com mídia audiovisual gerada pelo FFmpeg,
e `ANIMECAOS_MEDIA_TEST_FILE` para reprodução offline com seek e EOF.
Esses testes abrem o player e requerem as dependências no PATH.
