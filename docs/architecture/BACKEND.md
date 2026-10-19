# Backend Go

## Composição

`internal/app.Service` é o ponto de entrada da aplicação. `New` abre a base SQLite, cria o gateway de mídia e um cliente HTTP compartilhado; instancia o catálogo com AnimeFire, AnimesOnlineCC, SushiAnimes e Otakulogia, além de AniList, contas, Discord, MangaDex, player, fila e atualizador. Wails e CLI recebem a mesma instância de serviço e, portanto, compartilham as regras de negócio.

| Pacote | Responsabilidade atual |
|---|---|
| `internal/domain` | Modelos JSON e interface `AnimeProvider` |
| `internal/app` | Casos de uso, operações canceláveis, coordenação de reprodução e eventos |
| `internal/providers` | Fontes de anime, parser e agregação/busca canônica |
| `internal/providers/browser.go`, `selenium.go` | Chromium ou Selenium/Firefox para ler player criado por JavaScript quando o scraping HTTP não encontra uma fonte |
| `internal/integrations` | AniList, OAuth/contas e Discord Rich Presence |
| `internal/manga` | Catálogo, capítulos, imagens e arquivo CBZ MangaDex |
| `internal/downloads` | Fila concorrente, persistência de tarefas e biblioteca local |
| `internal/media` | Proxy/gateway de mídia, HLS e arquivos locais/compactados |
| `internal/player` | Processo MPV, IPC e estado de playback |
| `internal/netx` | Cliente HTTP, limites, timeout e erros de rede |
| `internal/store` | SQLite, cache TTL, buckets e importação do legado |
| `internal/platform` | Caminhos, processos e operações do sistema operacional, incluindo revelar arquivos no gerenciador nativo |
| `internal/update` | Verificação, download validado, staging e helper de substituição |

O detalhe por arquivo está em [CODE_MAP.md](../CODE_MAP.md).

## Serviço Wails

O binding é a API do aplicativo desktop, não uma API de rede. Métodos exportados presentes em `internal/app.Service`:

`Initial`, `Settings`, `SaveSettings`, `Cancel`, `Search`, `Discover`, `Details`, `Preview`, `SaveHistoryCover`, `Library`, `Favorite`, `History`, `RemoveHistory`, `Resume`, `Play`, `PlayerCommand`, `Adjacent`, `Enqueue`, `Downloads`, `CancelDownload`, `LocalFiles`, `DeleteFile`, `OpenDownloads`, `OpenLocalFolder`, `PlayLocal`, `MangaSearch`, `Chapters`, `ChaptersLanguage`, `Pages`, `MangaHistory`, `SaveMangaProgress`, `DownloadManga`, `Accounts`, `Login`, `Logout`, `RefreshAccount`, `CheckUpdate`, `DownloadUpdate`, `InstallUpdate`, `ClearCache`, `Diagnose` e `OfflinePages`.

Os tipos e argumentos visíveis para o frontend estão definidos em `frontend/src/api.ts` e `frontend/src/types.ts`. Os métodos do objeto `Desktop` em `main.go` abrem diálogo para pasta/player e navegador. Para assinaturas completas, use o código como referência.

### Eventos enviados do Go ao frontend

| Evento | Conteúdo | Uso |
|---|---|---|
| `player` | `PlayerEvent`: estado, anime e episódio | Atualiza player, histórico e progresso de reprodução |
| `download` | `domain.Download` | Atualiza fila e estado de cada tarefa |
| `error` | texto de erro | Exibe falhas não associadas ao retorno de uma chamada normal |
| `update` | mapa com `id` e `percent` | Progresso do download do pacote de atualização |
| `quit` | sem payload relevante | Fecha a janela após preparar a troca de versão |

Não há contrato de replay dos eventos; a UI consulta `Initial`, `Downloads`, `History` etc. para obter estado inicial.

## Operações, cancelamento e concorrência

Operações de busca, descoberta, preview, detalhes e fluxo de player recebem um identificador opaco da UI. `Service.operation` substitui a operação anterior com o mesmo identificador e cria contexto com timeout. `Cancel(id)` encerra a operação associada. O código também protege a sessão de reprodução contra callbacks antigos.

A fila de downloads tem concorrência configurável entre 1 e 5. Tarefas possuem estado próprio e são persistidas; ao reabrir, operações interrompidas são recuperadas como não concluídas. Cancela-se pela identidade do trabalho. A fila de mangá mantém o slot ocupado até o worker finalizar, mesmo depois do cancelamento.

## Erros e logs

Erros de métodos Wails retornam como rejeição de Promise. Erros assíncronos de player e integração podem chegar como evento. O frontend sanitiza mensagens comuns para não mostrar URL nem nome de fonte; diagnósticos técnicos ficam na tela Diagnóstico. Não inclua credenciais em logs nem copie tokens para documentação.

## Regras de domínio importantes

- A chave de anime e episódio inclui fonte e ID: `provider:id`.
- Um índice de episódio antigo não é identidade suficiente para retomar. A UI exige escolha quando `needsResolve` indica essa incerteza.
- O catálogo preserva variantes de provedor; episódios de IDs diferentes não são concatenados como se fossem o mesmo conjunto.
- O player dinâmico AnimesOnlineCC usa Chrome/Chromium/Edge ou Selenium com Firefox/GeckoDriver. `ANIMECAOS_BROWSER_PATH`, `ANIMECAOS_GECKODRIVER_PATH` e `ANIMECAOS_FIREFOX_PATH` selecionam executáveis. Selenium lê a configuração JWPlayer e não tenta resolver telas de verificação. Para arquivos diretos, FFprobe identifica codecs/dimensões e a app rejeita vídeo sem áudio quando a inspeção é possível.
- Temporada não informada fica em `0` no backend e não deve ser apresentada como temporada 0.
- Autoplay é disparado por término natural de reprodução e não pelo fechamento manual do processo.
- Downloads gravam em temporário e só publicam arquivo final quando a operação conclui com sucesso.
- Ao abrir a pasta de um arquivo offline no Windows, a plataforma reutiliza uma janela existente do Explorer quando encontra a pasta e a traz para frente; caso contrário, abre o diretório e aguarda a janela aparecer.
- Reprodução offline de um download mantém a identidade canônica do anime e do episódio. Ao consultar o histórico, uma entrada antiga `local:<caminho>` só é consolidada quando o registro de download concluído aponta para o mesmo arquivo existente; a posição mais recente é preservada e a retomada usa o arquivo local.

Mais regras e limites estão em [PRODUCT_FLOWS.md](../PRODUCT_FLOWS.md).
