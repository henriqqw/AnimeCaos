# Frontend e interface Wails

## Como a interface conversa com Go

`frontend/src/main.tsx` monta o React. `api.ts` é um proxy tipado sobre `window.go.app.Service`; fora do runtime Wails, as chamadas rejeitam com uma mensagem que explica que a interface precisa ser aberta pelo aplicativo. O objeto `window.go.main.Desktop` expõe diálogos nativos. `EventsOn` é encapsulado por `on` para assinar eventos Wails e obter função de limpeza.

Não há roteador de URL no frontend. `App.tsx` mantém o estado `Route` e o histórico de navegação local, incluindo objetos selecionados. O botão Voltar e o botão lateral do mouse retornam pelo histórico interno.

## Telas e rotas locais

| `route.name` | Rótulo mostrado | Componente/fluxo | Chamadas mais relacionadas |
|---|---|---|---|
| `home` | Início | Destaque, Continuar assistindo, Em alta e Temporada atual | `Discover`, `History`, `Preview` |
| `search` | Pesquisar | Busca e paginação de opções disponíveis; mostra skeletons no primeiro carregamento e indicador discreto ao carregar mais, com cancelamento | `Search`, `Cancel`, `Details` |
| `list` | Minha Lista | Lista de animes salvos | `Library`, `Favorite` |
| `detail` | Título selecionado | Sinopse, episódios, temporadas, seleção e ações de reprodução/download | `Details`, `Favorite`, `Play`, `Enqueue` |
| `history` | Histórico | Assistidos recentemente em páginas fixas de 24 itens e recuperação de registros antigos sem ID confiável | `History`, `SaveHistoryCover`, `Resume`, `RemoveHistory`, `Search` |
| `downloads` | Downloads | Arquivos locais e downloads ativos/concluídos; ações do cabeçalho para abrir a pasta de downloads e atualizar a biblioteca aparecem apenas como ícones com nome acessível e tooltip; cada arquivo offline tem ações compactas para reproduzir/ler, abrir sua pasta e excluir | `Downloads`, `LocalFiles`, `CancelDownload`, `DeleteFile`, `PlayLocal`, `OpenLocalFolder`, `OpenDownloads` |
| `manga` | Mangás | Descoberta com banner editorial, categorias por gênero, carrosséis de ranking/atualizações/publicação, retomada e busca | `MangaDiscover`, `MangaByCategory`, `MangaSearch`, `MangaHistory` |
| `chapters` | Capítulos do mangá | Detalhe, idioma, ordem, seleção, leitura e download em lote | `Chapters`, `ChaptersLanguage`, `DownloadManga` |
| `reader` | Leitor | Rolagem contínua ou página única, página/capítulo anterior e seguinte, recuperação de falha e progresso persistente | `Pages`, `OfflinePages`, `ChaptersLanguage`, `SaveMangaProgress` |
| `accounts` | Contas | Conexão/desconexão Discord, AniList e MyAnimeList, status do perfil e estatísticas com ícones locais | `Accounts`, `Login`, `RefreshAccount`, `Logout` |
| `settings` | Configurações | Seções abertas com índice contextual, switches acessíveis, resumo das contas e salvamento automático | `SaveSettings`, diálogos nativos, cache e atualização |
| `logs` | Diagnóstico | Dependências e logs técnicos | `Diagnose`, estado de logs recebido pela UI |

Contas e Diagnóstico não aparecem como item primário da navegação; Configurações resume o estado das integrações e abre a rota Contas para gerenciá-las. Configurações é uma coluna contínua com índice que navega por Aparência, Reprodução, Downloads, Integrações e Manutenção. Os grupos mantêm controles relacionados em duas colunas quando há largura suficiente e empilham em janelas compactas. O índice indica a seção visível durante a rolagem; links quebram linha sem cortar rótulos. Rotas são estado interno, não caminhos HTTP.

## Componentes definidos hoje

Todos vivem em `App.tsx`: `NavIcon`, `SidebarToggle`, `Empty`, `Busy`, `Cards`, `Rail`, `Card`, `Home`, `Search`, `Details`, `HistoryView`, `Queue`, `DownloadsView`, `MangaCover`, `MangaView`, `ChaptersView`, `Reader`, `AccountsPanel`, `AccountsView`, `SettingsView` e `Diagnostics`. `Image.tsx` cuida de imagem via backend/fallback. A divisão em arquivos menores ainda não foi feita.

Configurações mostra um resumo compacto do estado Discord, AniList e MyAnimeList e o botão “Gerenciar contas” abre a rota Contas, onde login, atualização e desconexão são realizados. O navegador do sistema conduz OAuth; falhas e cancelamento aparecem junto às contas. Rich Presence, autoplay e fechamento automático usam switches acessíveis com estado anunciado; Rich Presence também identifica Discord pelo ícone. O progresso só é enviado ao AniList/MAL ao fim natural do episódio ou depois de 80% da duração conhecida; os serviços precisam ter IDs canônicos para o título. Configurações explica essa regra e não tenta autenticar em intervalos de polling.

Na Home, os pôsteres de “Continuar assistindo”, “Em alta” e “Temporada atual” exibem “Ver anime” quando o card recebe hover ou foco de teclado. A sobreposição é apenas visual e decorativa para leitores de tela: a capa continua sendo o mesmo botão acessível que abre o anime, e a prateleira de histórico mantém sua ação separada “Continuar”. A preferência por movimento reduzido remove a transição da sobreposição.

Preferências são aplicadas imediatamente à interface e persistidas por uma fila única no nível de `App`, com debounce de 350 ms. Chamadas `SaveSettings` são serializadas; alterações feitas durante uma gravação substituem o snapshot pendente pela versão mais recente. Falhas não revertem a seleção: o estado permanece no app e a pessoa pode tentar novamente. Ações de manutenção não usam essa fila e informam seu resultado localmente. Não há barra global nem botão de salvar.

As credenciais de cadastro OAuth do AnimeCaos não aparecem como campos para o usuário. O Client ID MAL é definido pela aplicação; Client ID e Client Secret não são configurações da conta pessoal. O app pode continuar usando um segredo anteriormente salvo no cofre do sistema, mas não expõe seu valor nem oferece edição na interface.

## Catálogo, capítulos e leitura de mangá

A rota de Mangás reutiliza o mesmo `spotlight`, largura de conteúdo, hierarquia de título, CTA e indicadores da Home; a busca fica somente no cabeçalho contextual, sem um segundo campo dentro do banner. O destaque usa a primeira obra do ranking real do catálogo, avança no mesmo intervalo da Home e pode ser controlado por indicadores ou setas do teclado; o botão abre capítulos, sem prometer reprodução ou disponibilidade de uma edição que não foi carregada. Retomada e prateleiras usam `home-shelf`, `shelf-heading` e `Rail` como na Home. As prateleiras são “Top mangás” (ordenadas por `followedCount`), “Em alta” (obras ordenadas pelo capítulo mais recentemente enviado) e “Em publicação” (status explícito `ongoing`), além de categorias filtráveis por gênero. O MangaDex não organiza mangás por temporada de anime, então a tela não atribui trimestre/temporada a obras sem esse dado.

A seção “Categorias” recebe os gêneros do MangaDex e filtra o catálogo pelo ID real da tag. A seleção mostra os resultados da categoria e pode ser limpa para voltar às prateleiras. A busca do conteúdo usa apenas o cabeçalho contextual; quando há uma consulta ou categoria, resultados e estados aparecem antes das prateleiras. A estante “Continue lendo” usa os mesmos cartões de pôster e trilho da Home, com capítulo, página e barra de progresso quando a quantidade de páginas é conhecida. A ação retoma o ponto salvo. Resultados apresentam título, status, idiomas disponíveis e sinopse curta; a seleção abre capítulos. Estados mostram carregamento, erro com retry, resultado vazio e retorno ao catálogo. A atribuição MangaDex permanece visível no rodapé.

As artes-base da mascote AnimeCaos ficam em `frontend/public/mascots/`: normal de corpo inteiro, mini superdeformed com cabeça maior e corpo simplificado, e miniatura transparente de 256 px. `poses/` guarda seis vistas de personagem e uma pose adicional; `reactions/` guarda dez expressões. A identidade usa cabelo longo vermelho liso repartido ao meio, chifres, olhos vermelhos, camiseta de caveira e saia preta lisa. Os arquivos ainda não são consumidos pela seção de categorias; a associação das variações de gênero deve preservar a identidade e a transparência.

A descoberta solicita, em paralelo, ranking, últimas atualizações e títulos em publicação; as chamadas seguem o gate do MangaDex. A resposta e consultas por gênero são cacheadas no SQLite por 15 minutos, com retenção máxima de seis horas. As capas do banner e dos cartões usam imagens carregadas sob demanda; a API de descoberta reserva a variante 512 px para o destaque e mantém a capa 256 px nas prateleiras. Falhas em uma prateleira deixam as outras utilizáveis e mostram um aviso conciso; cache ainda válido pode servir como fallback se a origem cair.

A pesquisa MangaDex só começa após o envio de um título não vazio. Uma consulta nova cancela a anterior e ignora respostas atrasadas; histórico local carrega em paralelo e continua visível durante a pesquisa. Erros ficam junto à tela e permitem nova tentativa. Resultados e itens de retomada usam capas lazy-load com placeholder.

O campo global do cabeçalho acompanha o contexto: nas rotas de catálogo, capítulos e leitor de mangá, seu rótulo e placeholder indicam pesquisa de mangás e o envio abre o catálogo MangaDex com a consulta. Em outras telas, continua pesquisando animes. O atalho `Ctrl+K` mantém a rota de mangá ativa e foca esse campo; assim a pessoa pode iniciar outra busca sem voltar ao catálogo ou cair por engano na busca de animes.

A tela de capítulos mostra identidade, sinopse e status da obra, permite trocar idioma e ordem, selecionar capítulos, mostra o grupo de tradução quando a API retorna esse relacionamento e enfileira CBZ. Erros de catálogo não são apresentados como lista vazia e têm botão de retry.

O leitor busca URLs de páginas ao abrir ou retomar um capítulo, mantém apenas as URLs em memória e salva progresso após navegação. A falha da consulta encerra o carregamento com uma ação para tentar outra atribuição do MangaDex@Home. O leitor oferece rolagem contínua ou uma página, RTL/LTR no modo paginado, atalhos de teclado, seleção de página e navegação explícita entre capítulos. `loading="lazy"` e `decoding="async"` evitam solicitar/decodificar antecipadamente todas as imagens de capítulos longos. A posição do leitor e a direção escolhida se adaptam à largura disponível.

## Busca visual e capas

O campo do cabeçalho é compartilhado pelas telas. `Ctrl+K` foca a pesquisa; submeter o campo abre ou atualiza a rota `search`. Um destaque/card da descoberta inicia busca pelo título e referência canônica em vez de abrir detalhes sem verificar disponibilidade nas fontes.

Os cartões de anime da Home e da busca carregam preview sob demanda, após atraso de hover ou foco por teclado. Quando há AniList ID confirmado, a prévia consulta esse ID; não reinterpreta apenas o título, o que poderia mostrar episódios de um remake diferente. Sem ID canônico, mantém a busca por título. O painel compacto é portal para `document.body`, tem posição fixa ao lado do card, tema copiado da raiz e z-index fora do carrossel, para evitar recorte por `overflow`. Ele escolhe o lado com espaço disponível e recalcula a posição ao rolar, redimensionar ou alterar a dimensão do card. Título e sinopse são limitados a duas e três linhas; o painel não cria rolagem interna. A tela compacta não mostra painel hover.

Os cartões das prateleiras de mangá seguem a mesma interação e o mesmo painel visual. A prévia usa o título e a sinopse já recebidos do MangaDex, sem chamada por card, metadados extras ou subtítulo; o painel aparece com atraso no hover/foco, acompanha rolagem/redimensionamento e fica fora do trilho via portal. Os cabeçalhos “Top mangás”, “Em alta”, “Em publicação”, “Categorias” e “Continue lendo” não recebem linhas explicativas adicionais.

Na busca, a tela mantém os cards da consulta anterior fora da lista ativa, mostra o estado “Buscando fontes e validando episódios…” e substitui a grade uma única vez quando `Search` devolve o lote validado. O carregamento inicial reserva 10 cards skeleton; o grid se adapta à largura disponível. Enquanto carrega, o spinner vermelho e o shimmer discreto dos skeletons dão feedback contínuo; esse feedback de progresso permanece ativo mesmo com `prefers-reduced-motion`, e termina junto com a busca. Os estados genéricos “Carregando…” usam três pontos pulsantes em vermelho, com o texto preservado para leitores de tela. Não há cards provisórios nem evento `search-item`. O selo de qualidade aparece apenas nesse fluxo; uma linha curta também mostra ano e episódios da obra quando a identidade canônica está confirmada (filmes mostram “Filme”). Esses campos vêm dos metadados em lote da busca, sem consulta por card. Home, histórico e biblioteca continuam sem selo. O resumo não contém URL nem cabeçalhos de mídia.

Capas e metadados podem vir do catálogo ou cache. Registros de histórico antigos tentam recuperar capa via metadados/cache. Falha de capa deve ficar em placeholder e não impedir a navegação.

Em detalhes do anime, a ação de Minha Lista reutiliza o ícone da navegação lateral. O ícone fica vermelho quando o anime está salvo; o estado vem da biblioteca persistida no backend e é carregado ao abrir o app. A ação atual continua disponível no nome acessível, no tooltip e em `aria-pressed`.

O Histórico ordena os registros do mais recente para o mais antigo e mostra 24 por página. Esse tamanho fixo reduz mudanças de posição ao redimensionar a janela; os controles aparecem antes e depois da grade, com o intervalo atual e páginas válidas após remoções. Em seis colunas, 24 itens ocupam quatro linhas completas. A ação “Continuar” no Histórico e no carrossel “Continuar assistindo” usa o ícone de play da família da sidebar à esquerda do texto, sem alterar o rótulo acessível nem o fluxo de retomada.

O filtro de temporada em detalhes usa um menu próprio, com opções selecionáveis, estado expandido acessível, navegação por setas/Home/End, fechamento por Escape e clique fora. A seleção continua filtrando a lista de episódios.

## Navegação e responsividade

- Desktop: sidebar vertical com controle de recolher/expandir junto à marca; estado persistido em `localStorage` pela chave `animecaos-sidebar-collapsed`.
- De 761 a 1050 px: manter 188 px na sidebar e compactar o espaçamento entre ícone e rótulo; o conteúdo reduz espaçamentos e adapta suas grades.
- Até 760 px: navegação inferior; controle da sidebar passa ao cabeçalho e recolher oculta os rótulos e reduz a barra.
- Cabeçalho, cards, banner, detalhe de anime, lista de episódios, fila de downloads e leitor de mangá adaptam a largura disponível. O CSS atende a preferência de movimento reduzido.
- O botão de destaque usa ícone de play e o rótulo “Assistir”; o fluxo do botão mantém a ação da versão anterior (pesquisar o título destacado).

As regras visuais completas e estados da experiência estão em [SYSTEM_DESIGN.md](../SYSTEM_DESIGN.md). Os testes DOM estão em `App.test.tsx`; eles não substituem inspeção em janela desktop empacotada.
