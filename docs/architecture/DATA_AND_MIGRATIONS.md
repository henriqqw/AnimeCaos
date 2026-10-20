# Dados locais, cache e migração

## Diretórios de dados

`platform.DataDir()` escolhe, nesta ordem:

1. `ANIMECAOS_DATA_DIR`, se definida;
2. `%APPDATA%/AnimeCaos` no Windows (ou `%USERPROFILE%/AppData/Roaming/AnimeCaos` quando `APPDATA` não está definido);
3. `~/.local/state/AnimeCaos` nos demais sistemas suportados pelo caminho Unix atual.

O store cria o diretório com permissão restrita no sistema Unix. MPV, FFmpeg e FFprobe são localizados primeiro ao lado do executável em `bin/`, depois na pasta do executável, no diretório `bin/` relativo à execução e, por fim, no `PATH`.

## SQLite

Arquivo: `state.db`. Implementação em `internal/store/store.go`, driver SQLite sem CGO (`modernc.org/sqlite`). `PRAGMA user_version=1`; banco abre com WAL, busy timeout de cinco segundos e um único connection pool.

O esquema atual é pequeno e flexível:

| Tabela | Colunas relevantes | Papel |
|---|---|---|
| `records` | `bucket`, `key`, JSON `value`, `updated` | Preferências e registros duráveis, chaveados por grupo e identidade |
| `cache` | `key`, JSON `value`, `soft`, `hard`, `accessed` | Cache com janela de validade suave e limite rígido |

Buckets usados pelo código incluem `settings`, `watchlist`, `history`, `downloads`, `local`, `manga_history`, `accounts`, `auth`, `legacy_config`, `migration` e `verified_updates`. Não são tabelas SQL separadas; são valores da coluna `records.bucket`. `auth` é somente origem legada de migração: tokens OAuth e Client Secret MAL novos ficam fora do SQLite, no cofre de credenciais do sistema.

`CacheGet` informa se o item existe e se passou do TTL suave; itens após o TTL rígido são considerados ausentes. `Prune` remove vencidos e limita o cache aos 5.000 mais recentemente acessados.

## Migração dos dados Python

`Store.Open` executa `ImportLegacy`. A migração `python-v1` é transacional e idempotente. Lê `config.json`, `watchlist.json`, `history.json` e `manga_history.json` em diretórios conhecidos; antes de importar, faz uma cópia de cada arquivo em `legacy-backup/`. Uma lista/histórico Python sem ID atual é mantida com `provider=legacy`; o importador não inventa a identidade de temporada/episódio.

O cache de mídia tem marcador separado `python-cache-v2`. A leitura de `cache/api_cache.db` (formato antigo) e `cache/discover_cache.json` tenta enriquecer capas e aliases de biblioteca/histórico. Cache corrompido não bloqueia a abertura: o marcador fica sem concluir para uma tentativa futura e os originais permanecem. As capas antigas com hash da URL continuam acessíveis pelo resolvedor `Image`.

`legacy-backup/` é criado dentro do diretório de dados da versão Go. O importador não move o diretório de dados nem apaga os arquivos originais. A instalação Python em `Legacy/` é código de referência e é diferente dos arquivos de dados pessoais do usuário.

O histórico antigo de reprodução offline é consolidado sob a chave canônica do anime quando o caminho local corresponde a um download concluído ainda existente. A posição mais recente é mantida e o episódio continua marcado como local para retomar pelo arquivo; registros sem vínculo verificável permanecem independentes.

## Preferências e valores padrão

`Store.Defaults` usa tema `system`, escala 1, MPV, diretório `Downloads/AnimeCaos`, 2 downloads simultâneos, autoplay habilitado e geometria inicial 1280 × 820. Há opções de fechamento automático da fila e intervalo de 3.000 ms. `SaveSettings` valida tema (system/light/dark), escala 1–1,5, concorrência 1–5, modo de player (`mpv`, `custom`, `system`), caminho absoluto de downloads e intervalo 0–60.000 ms. Não confundir defaults de código com uma preferência já salva.

O token da sidebar fica em `localStorage`; preferências de tema também são refletidas nessa camada pelo frontend. A configuração de aplicação é persistida no bucket `settings` do SQLite.

## Credenciais de contas

`internal/securestore` usa o Credential Manager do Windows e o Secret Service no Linux. A primeira leitura de um token ou do Client Secret MAL legado segue esta ordem: ler o valor antigo, gravar no cofre, confirmar a gravação e só então removê-lo do bucket `auth`. A remoção ativa `PRAGMA secure_delete`, faz checkpoint/truncamento do WAL e `VACUUM` para limpar páginas livres do banco ativo. Se a gravação no cofre falhar, o valor antigo fica preservado para permitir nova tentativa; não há fallback silencioso para credenciais em texto.

O frontend não recebe o Client Secret nem um indicador de que ele existe. Um segredo MAL que já tenha sido salvo permanece no cofre e pode ser usado internamente pelo backend; desconectar remove o token OAuth, mas preserva essa credencial legada. Backups anteriores, cópias de `state.db` e segredos já expostos fora desta instalação não podem ser revogados ou apagados pelo migrador. Linux precisa de um Secret Service ativo no usuário gráfico (por exemplo, GNOME Keyring ou KWallet); sem ele, conexão e atualização de perfil retornam erro.

## Arquivos baixados

- Anime: organização em pastas de título sob o diretório configurado, nomes sanitizados e metadados locais. O arquivo final só é publicado após conclusão.
- Mangá: `Manga/<título>/...cbz`, arquivo ZIP com páginas sequenciais.
- Perfil/resumo de conta e estado de biblioteca ficam no banco, não misturados com o executável. Tokens e Client Secret ficam no cofre do sistema operacional.

Use `platform.SafeName` para criar nomes e `platform.Within` para validar caminhos. Não apague manualmente dados do usuário para testar migração; use `ANIMECAOS_DATA_DIR` em testes isolados.
