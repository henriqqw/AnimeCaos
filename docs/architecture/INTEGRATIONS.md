# Integrações externas

Esta página lista integrações chamadas pelo backend. O app não mantém proxy público nem API de servidor próprio.

## AniList

- GraphQL em `https://graphql.anilist.co`.
- Fornece descoberta (Em alta e Temporada atual), títulos em idiomas diferentes, sinônimos, IDs de AniList/MAL, capa/banner, score, quantidade de episódios e descrição.
- Busca e lookups são limitados por `Gate` e cacheados. Lookups por títulos podem ser agrupados/coalescidos e há limite de concorrência definido em `Metadata`.
- Tradução de sinopse, quando necessária, consulta o endpoint público `translate.googleapis.com/translate_a/single` configurado para `pt-BR`; erro de tradução não é identidade de anime e não deve impedir reprodução.
- Login usa navegador do sistema e callback local na porta `9742`, com `state` aleatório e timeout de dois minutos. A implementação atual usa o fluxo implícito do cliente público AniList.
- Sincronização grava progresso/status pela mutation GraphQL `SaveMediaListEntry` após o estado do player.

## MyAnimeList (MAL)

- OAuth/API base: `myanimelist.net/v1/oauth2` e `api.myanimelist.net/v2`.
- O Client ID é dado público de cliente desktop e existe como configuração/padrão no código; **não documentar o valor aqui nem incluir Client Secret**. O app não contém fluxo que use segredo embutido.
- O login abre callback local em `http://localhost:9743/`, verifica `state`, troca o `code` usando o verifier da sessão e expira em dois minutos. O perfil usa `/v2/users/@me`; sincronização atualiza `/v2/anime/{id}/my_list_status`.
- O fluxo e a configuração estão implementados, mas a autenticação completa não consta como validada com sucesso no estado registrado. Em tentativas anteriores desta conversa, a API retornou `invalid_client`; o usuário adiou essa investigação. Trate login real como pendente até teste atual bem-sucedido.

## MangaDex

- API base `https://api.mangadex.org`; arquivos de capa em `https://uploads.mangadex.org/covers`.
- Pesquisa de título consulta inicialmente tradução `pt-br`; em seguida tenta busca sem filtro de idioma se não encontrou itens.
- Capítulos percorrem `pt-br`, `en`, `es-la`, `es` por padrão; o frontend também permite pedir um idioma específico. A paginação usa lotes de 500.
- Páginas vêm de `/at-home/server/{chapterID}` com URL principal e alternativa `data-saver`. Conteúdo é compactado em CBZ para leitura offline.
- O Gate do serviço define intervalo mínimo de 250 ms por requisição nesta implementação.

## Discord Rich Presence

O estado de reprodução é enviado ao cliente Discord por IPC local. Os arquivos específicos por plataforma ficam em `discord_windows.go` e `discord_unix.go`; conexão, heartbeat, reconexão e limpeza ficam no serviço. A integração é opcional (`Settings.Discord`). Os testes usam transporte controlado; presença contra cliente real não está marcada como validação de release.

## Atualizador

- Consulta `https://api.github.com/repos/henriqqw/animecaos/releases/latest`.
- Seleciona ZIP Windows `windows-amd64.zip` ou AppImage Linux x86_64, além de `SHA256SUMS`.
- Confere checksum antes de publicar pacote local. O helper valida caminhos do ZIP, rejeita symlinks/duplicatas e limita conteúdo descompactado. Atualizações Flatpak são identificadas como gerenciadas e não aplicadas pelo helper.
- O helper copia/substitui os arquivos de aplicativo e conserva dados do usuário; rollback é tentado quando inicialização ou troca falha.
- A verificação e os testes unitários não significam que uma atualização instalada tenha sido executada ponta a ponta nesta máquina.

## Configuração e credenciais

Tokens OAuth ficam no bucket local `auth` e não são enviados nos DTOs de configuração da interface. Sessões de conta são removidas por `Logout`. Nunca registrar valores de tokens ou URLs assinadas. Consulte a página de [dados e migrações](DATA_AND_MIGRATIONS.md) para local e persistência.
