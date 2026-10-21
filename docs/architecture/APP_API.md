# API da aplicação

## Limite importante

AnimeCaos não abre um servidor REST para a UI. O frontend chama bindings Wails locais expostos em `window.go.app.Service` e `window.go.main.Desktop`. Os nomes abaixo são métodos de processo local; não são rotas HTTP. Para endpoints de terceiros consumidos pelo backend, consulte [Rede e provedores](NETWORK_AND_PROVIDERS.md) e [Integrações](INTEGRATIONS.md).

## Serviço principal Wails

As assinaturas exatas de tipos estão em `frontend/src/api.ts`; os DTOs e tags JSON estão em `frontend/src/types.ts` e `internal/domain/models.go`.

| Grupo | Métodos expostos |
|---|---|
| Inicialização e operação | `Initial() → {settings, version, accounts}`, `Settings() → Settings`, `SaveSettings(Settings)`, `Diagnose() → Diagnosis`, `Cancel(operationID)`, `ClearCache()` |
| Catálogo | `Search(operationID, query, page, preferred?) → SearchResult`, `Discover(operationID) → Discovery` (prateleiras e aviso quando usa fallback), `Details(operationID, Anime) → Detail`, `Preview(operationID, title, preferredAniListID) → Anime`, `Image(source) → data URL`, `SaveHistoryCover(key, cover)` |
| Biblioteca e histórico | `Library() → Anime[]`, `Favorite(Anime, enabled)`, `History() → History[]`, `RemoveHistory(key)`, `Resume(operationID, key)` |
| Reprodução | `Play(operationID, Anime, Episode[], index, resume)`, `PlayerCommand(command, value)`, `Adjacent(delta)`, `PlayLocal(path)`, `OfflinePages(path) → string[]` |
| Downloads e arquivos | `Enqueue(Anime, Episode[]) → Download[]`, `Downloads() → Download[]`, `CancelDownload(id)`, `LocalFiles() → LocalFile[]`, `DeleteFile(path)`, `OpenDownloads()`, `OpenLocalFolder(path)` (abre a pasta do arquivo após validar que ele está dentro da biblioteca) |
| Mangá | `MangaSearch(operationID, query) → Manga[]`, `Chapters(operationID, mangaID) → Chapter[]`, `ChaptersLanguage(operationID, mangaID, language) → Chapter[]`, `Pages(operationID, chapterID) → string[]`, `MangaHistory() → MangaProgress[]`, `SaveMangaProgress(MangaProgress)`, `DownloadManga(operationID, Manga, Chapter[])` |
| Contas | `Accounts() → Account[]`, `Login(operationID, provider)` (`anilist`, `mal`, `discord`), `Logout(provider)`, `RefreshAccount(operationID, provider) → Account` |

O DTO `Account` inclui `externalId` opcional para o ID Discord; tokens permanecem no cofre e não são enviados aos bindings. O login Discord abre o navegador e recebe o OAuth no loopback `127.0.0.1:9744`.
| Atualização | `CheckUpdate(operationID) → Update`, `DownloadUpdate(operationID, Update) → path`, `InstallUpdate(path)` |

Métodos que recebem `operationID` permitem ao frontend cancelar uma chamada ou substituir uma operação antiga. O serviço aplica timeouts próprios; consulte `internal/app/service.go` para valores e mudanças de implementação.

## Objeto Desktop

`window.go.main.Desktop` expõe:

| Método | Uso |
|---|---|
| `ChooseDirectory() → string` | Diálogo nativo de seleção de pasta |
| `ChoosePlayer() → string` | Diálogo nativo de executável do player |
| `OpenLink(url)` | Abre URL no navegador do sistema |

## Eventos Wails

| Evento | Payload aproximado |
|---|---|
| `player` | `{state, anime, episode}` |
| `download` | Um registro `Download` atualizado |
| `error` | Texto de erro assíncrono |
| `update` | `{id, percent}` |
| `quit` | Sinal de encerramento |

Os eventos não são persistidos para clientes desconectados. A UI deve carregar o estado inicial através dos métodos de consulta.

## Endpoints de terceiros

Não são endpoints internos. O catálogo e integrações chamam os hosts e caminhos documentados nas páginas [NETWORK_AND_PROVIDERS.md](NETWORK_AND_PROVIDERS.md) e [INTEGRATIONS.md](INTEGRATIONS.md). Essa separação é intencional: a UI não conhece HTML, OAuth token endpoints nem URLs assinadas de mídia.
