# Desenvolvimento e operação

## Pré-requisitos

- Go conforme `go.mod` (atualmente 1.26.0).
- Node.js/npm compatíveis com as versões travadas em `frontend/package-lock.json`.
- Wails CLI v2 e dependências nativas: WebView2 no Windows; GTK/WebKitGTK na configuração Linux usada pelo Wails.
- MPV para reprodução e FFmpeg/FFprobe para operações de mídia.

O localizador de executáveis procura primeiro no diretório do pacote e em `bin/`, depois no `PATH`. A documentação não pressupõe que esses programas estejam instalados na máquina.

## Abrir o aplicativo em desenvolvimento

```powershell
cd frontend
npm ci
cd ..
wails dev
```

`wails.json` configura o watcher e servidor frontend. Abrir a URL do Vite diretamente não fornece os bindings `window.go`; a página informa que deve ser aberta pelo aplicativo AnimeCaos.

No Windows, o app mantém um ícone na área de notificação. Fechar pelo X oculta a janela; use o menu do ícone para abrir/minimizar/ocultar a janela ou escolher `Sair` para encerrar o processo. O ícone pode estar dentro do menu de ícones ocultos do Windows. Ao iniciar, uma posição salva fora dos monitores conectados é ignorada e a janela é centralizada.

## CLI

O entry point é `cmd/animecaos`. O binário distribuído chama-se `animecaos-cli`. Comandos aceitos: `interactive`, `doctor`, `search`, `details`, `play`, `download`, `history`, `list`, `files`, `manga`, `chapters`, `accounts`, `login` e `update`.

Flags: `--query`, `--id`, `--provider` (padrão `animefire`), `--page`, `--episode`, `--data` e `--continue`. Para `play`/`download`, use o ID do episódio retornado por `details`.

```powershell
go run ./cmd/animecaos doctor
go run ./cmd/animecaos search --query "Frieren"
go run ./cmd/animecaos details --id ID
```

## Dados e logs

Diretório de dados e estrutura SQLite estão em [DATA_AND_MIGRATIONS.md](architecture/DATA_AND_MIGRATIONS.md). Erros de inicialização Wails podem ser registrados em `startup-error.log` no diretório de dados. Falhas do helper de atualização podem ficar em `updater-error.log` perto do executável.

A tela Diagnóstico pode mostrar caminhos locais e disponibilidade de ferramentas. Antes de compartilhar logs, remova tokens, caminhos pessoais, cookies e URLs assinadas.

## Distribuição

`cmd/package` prepara o stage portátil. `deploy/go/build-appimage.sh` monta AppImage Linux e `deploy/go/windows.iss` descreve o instalador Windows. Consulte [DISTRIBUTION.md](DISTRIBUTION.md) para dependências, limitações e formatos.

```powershell
go run ./cmd/package -version 3.0.0-dev
```

Esse comando executa build por padrão e exige dependências de mídia; `-skip-ui` só serve quando existe frontend compilado compatível. O script AppImage exige o stage e ferramentas nativas no host Linux. Testes unitários não são prova de instalação limpa ou de release pronta.
