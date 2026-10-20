# Desenvolvimento e operação

## Pré-requisitos

- Go conforme `go.mod` (atualmente 1.26.0).
- Node.js/npm compatíveis com as versões travadas em `frontend/package-lock.json`.
- Wails CLI v2 e dependências nativas para desenvolvimento: WebView2 no Windows; GTK/WebKitGTK na configuração Linux usada pelo Wails. Os pacotes de produção trazem WebView2 fixo no Windows e GTK/WebKitGTK selecionados dentro do AppImage.
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

Mantenha apenas uma sessão `wails dev` para este checkout. Se a saída indicar `Port 5173 is in use`, outro Vite já está usando essa porta e o novo processo escolhe uma porta seguinte, como `5174`; encerre a sessão anterior com `Ctrl+C` e feche a instância antiga pela bandeja (`Sair`) antes de iniciar uma sessão limpa.

No Windows, o app mantém um ícone na área de notificação. Fechar pelo X oculta a janela; use o menu do ícone para abrir, minimizar, ocultar, reiniciar ou escolher `Sair` para encerrar. `Reiniciar` fecha e abre o mesmo executável após a instância anterior sair, reapresentando a splash. O ícone pode estar dentro do menu de ícones ocultos do Windows. Ao iniciar, uma posição salva fora dos monitores conectados é ignorada e a janela é centralizada. Os identificadores de instância do modo `wails dev` e do pacote instalado são distintos, para uma instância de desenvolvimento cujo Vite parou não interceptar a abertura do aplicativo instalado.

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
go run ./cmd/package -version 3.0.0
```

Esse comando executa build por padrão e exige dependências de mídia; `-skip-ui` só serve quando existe frontend compilado compatível. O script AppImage exige o stage e ferramentas nativas no host Linux. Testes unitários não são prova de instalação limpa ou de release pronta.
