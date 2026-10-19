# Integrações externas

Esta página lista integrações chamadas pelo backend. O app não mantém proxy público nem API de servidor próprio.

## AniList

- GraphQL em `https://graphql.anilist.co`.
- Fornece descoberta (Em alta e Temporada atual), títulos em idiomas diferentes, sinônimos, IDs de AniList/MAL, capa/banner, score, ano de lançamento, formato, quantidade de episódios e descrição. A busca já solicita esses metadados na consulta GraphQL em lote; cards de provedores só os recebem quando a identidade AniList é inequívoca. A chave de cache de títulos inclui versão para renovar entradas anteriores que não armazenavam ano e formato.
- Busca e lookups são limitados por `Gate` e cacheados. Lookups por títulos podem ser agrupados/coalescidos e há limite de concorrência definido em `Metadata`.
- Tradução de sinopse, quando necessária, consulta o endpoint público `translate.googleapis.com/translate_a/single` configurado para `pt-BR`; erro de tradução não é identidade de anime e não deve impedir reprodução.
- Login abre o navegador do sistema e recebe o retorno em `http://localhost:9742/`, valida um `state` aleatório e expira após dois minutos. O fluxo implícito é suportado pela API; o token longo (até um ano) fica no banco local e não é enviado à interface.
- Depois que o MPV termina, o app consulta a entrada atual e só envia progresso via `SaveMediaListEntry` se houve EOF natural ou se a posição chegou a 80% da duração conhecida. Uma interrupção antecipada não avança a lista; a leitura antes da gravação impede que um episódio repetido regrida a lista ou reabra uma obra concluída. O envio usa o AniList ID canônico associado à obra; sem ID inequívoco, nada é sincronizado.

## MyAnimeList (MAL)

- OAuth/API base: `myanimelist.net/v1/oauth2` e `api.myanimelist.net/v2`.
- O Client ID é dado público de cliente desktop e existe como configuração/padrão no código; **não documentar o valor aqui nem incluir Client Secret**. O app não contém fluxo que use segredo embutido.
- O login abre callback local em `http://localhost:9743/`, valida `state`, troca o `code` com PKCE `plain` e expira em dois minutos. A troca/refresh autenticam o cliente por HTTP Basic (`client_id:` para clientes públicos; `client_id:client_secret` se a aplicação registrada exigir segredo). O perfil usa `/v2/users/@me`; sincronização consulta `/v2/anime/{id}?fields=my_list_status` antes de enviar `PATCH /v2/anime/{id}/my_list_status` com status e número de episódios assistidos. O progresso não diminui e uma entrada concluída permanece concluída.
- O MyAnimeList Client ID pode ser alterado em Configurações e precisa ser salvo antes de iniciar o login. Um Client Secret opcional pode ser digitado e salvo separadamente; o valor não é devolvido ao frontend e fica no bucket local `auth`. Não existe segredo embutido no executável. O refresh do token ocorre antes de chamadas quando o acesso está perto de expirar.
- A tela de Configurações permite conectar/desconectar as duas contas e mostra o perfil; a rota Contas oferece as mesmas ações. As imagens locais `frontend/public/anilist.ico` e `frontend/public/myanimelist.ico` são favicons obtidos dos domínios oficiais e evitam requisições externas para identificação visual.
- Os testes locais cobrem a mutation GraphQL do AniList, o PATCH do MAL, leitura prévia e HTTP Basic na troca/renovação de token usando servidores de fixture. A verificação do endpoint MAL com o Client ID configurado redirecionou ao login, mas o endpoint de token retornou `invalid_client` quando testado sem segredo. Login e gravação em contas reais continuam pendentes; será necessário configurar o Client Secret correspondente se a aplicação MAL exigir um.

## MangaDex

- API base `https://api.mangadex.org`; arquivos de capa em `https://uploads.mangadex.org/covers`.
- Pesquisa de título consulta inicialmente tradução `pt-br`; em seguida tenta busca sem filtro de idioma se não encontrou itens.
- Capítulos percorrem `pt-br`, `en`, `es-la`, `es` por padrão; o frontend também permite pedir um idioma específico. A paginação usa lotes de 500.
- Páginas vêm de `/at-home/server/{chapterID}`: `data` é a qualidade original e `data-saver` é a alternativa comprimida. O leitor registra ambas no gateway e oferece repetir a consulta ao `at-home` se uma atribuição falhar, sem persistir URLs temporárias.
- A montagem das páginas aceita resposta com apenas `data-saver`, exige base HTTP(S) e hash válido, e descarta nomes vazios. Conteúdo é compactado em CBZ para leitura offline.
- O Gate do serviço define intervalo mínimo de 250 ms por requisição nesta implementação.
- A tela local oferece busca sob demanda, capítulos por idioma, progresso retomável, leitor contínuo/paginado e direção RTL/LTR. MangaDex é creditado na tela e o grupo de tradução é mostrado em cada capítulo quando o relacionamento vier na resposta da API.

## Discord Rich Presence

O estado de reprodução é enviado ao cliente Discord por IPC local. Os arquivos específicos por plataforma ficam em `discord_windows.go` e `discord_unix.go`; conexão, heartbeat, reconexão e limpeza ficam no serviço. A integração é opcional (`Settings.Discord`). Os testes usam transporte controlado; presença contra cliente real não está marcada como validação de release.

## Atualizador

- Consulta `https://api.github.com/repos/henriqqw/animecaos/releases/latest`.
- Seleciona ZIP Windows `windows-amd64.zip` ou AppImage Linux x86_64, além de `SHA256SUMS`.
- Confere checksum antes de publicar pacote local. O helper valida caminhos do ZIP, rejeita symlinks/duplicatas e limita conteúdo descompactado. Atualizações Flatpak são identificadas como gerenciadas e não aplicadas pelo helper.
- O helper copia/substitui os arquivos de aplicativo e conserva dados do usuário; rollback é tentado quando inicialização ou troca falha.
- A verificação e os testes unitários não significam que uma atualização instalada tenha sido executada ponta a ponta nesta máquina.

## Configuração e credenciais

Tokens OAuth e o Client Secret MAL configurado ficam no bucket local `auth` e não são enviados nos DTOs de configuração da interface. Sessões de conta são removidas por `Logout`; o Client Secret permanece salvo para reconexões até ser removido explicitamente em Configurações. Nunca registrar valores de tokens, segredos ou URLs assinadas. Consulte a página de [dados e migrações](DATA_AND_MIGRATIONS.md) para local e persistência.
