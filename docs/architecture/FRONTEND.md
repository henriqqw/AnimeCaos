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
| `downloads` | Downloads | Arquivos locais e downloads ativos/concluídos; cada arquivo offline tem ações compactas para reproduzir/ler, abrir sua pasta e excluir | `Downloads`, `LocalFiles`, `CancelDownload`, `DeleteFile`, `PlayLocal`, `OpenLocalFolder`, `OpenDownloads` |
| `manga` | Mangás | Pesquisa sob demanda, cartões com placeholder, histórico de leitura e retomada | `MangaSearch`, `MangaHistory` |
| `chapters` | Capítulos do mangá | Detalhe, idioma, ordem, seleção, leitura e download em lote | `Chapters`, `ChaptersLanguage`, `DownloadManga` |
| `reader` | Leitor | Rolagem contínua ou página única, página/capítulo anterior e seguinte, recuperação de falha e progresso persistente | `Pages`, `OfflinePages`, `ChaptersLanguage`, `SaveMangaProgress` |
| `accounts` | Contas | Conexão/desconexão AniList e MyAnimeList, status do perfil e estatísticas com ícones locais | `Accounts`, `Login`, `RefreshAccount`, `Logout` |
| `settings` | Configurações | Preferências em grupos compactos e responsivos; estado de alteração/salvamento; ações de integração e manutenção | `SaveSettings`, diálogos nativos, cache e atualização |
| `logs` | Diagnóstico | Dependências e logs técnicos | `Diagnose`, estado de logs recebido pela UI |

Contas e Diagnóstico não aparecem como item primário da navegação; são acessados a partir de Configurações. A tela agrupa aparência, reprodução, downloads, integrações e manutenção em cartões com duas colunas em telas largas e uma coluna em telas estreitas. Mudanças ficam pendentes até “Salvar alterações”; a tela anuncia o estado e impede uma segunda submissão durante o salvamento. Rotas são estado interno, não caminhos HTTP.

## Componentes definidos hoje

Todos vivem em `App.tsx`: `NavIcon`, `SidebarToggle`, `Empty`, `Busy`, `Cards`, `Rail`, `Card`, `Home`, `Search`, `Details`, `HistoryView`, `Queue`, `DownloadsView`, `MangaCover`, `MangaView`, `ChaptersView`, `Reader`, `AccountsPanel`, `AccountsView`, `SettingsView` e `Diagnostics`. `Image.tsx` cuida de imagem via backend/fallback. A divisão em arquivos menores ainda não foi feita.

Configurações mostra o estado de AniList e MyAnimeList e permite conectar, atualizar perfil e desconectar sem sair da tela. A rota Contas reutiliza o mesmo painel. O browser do sistema conduz OAuth; falhas e cancelamento aparecem junto às contas. O progresso só é enviado ao fim natural do episódio ou depois de 80% da duração conhecida; os serviços precisam ter IDs canônicos para o título. A tela explica essa regra e não tenta autenticar em intervalos de polling.

O Client Secret do MyAnimeList é um controle de senha separado do formulário geral: a UI só recebe um booleano de configuração, limpa o campo após gravar e nunca lê o valor salvo de volta. Cliente público pode deixar o segredo vazio; o Client ID é salvo pelo botão geral de Configurações.

## Catálogo, capítulos e leitura de mangá

A pesquisa MangaDex só começa após o envio de um título não vazio. Uma consulta nova cancela a anterior e ignora respostas atrasadas; histórico local carrega em paralelo e continua visível durante a pesquisa. Erros ficam junto à tela e permitem nova tentativa. Resultados e itens de retomada usam capas lazy-load com placeholder.

A tela de capítulos mostra identidade, sinopse e status da obra, permite trocar idioma e ordem, selecionar capítulos, mostra o grupo de tradução quando a API retorna esse relacionamento e enfileira CBZ. Erros de catálogo não são apresentados como lista vazia e têm botão de retry.

O leitor busca URLs de páginas ao abrir ou retomar um capítulo, mantém apenas as URLs em memória e salva progresso após navegação. A falha da consulta encerra o carregamento com uma ação para tentar outra atribuição do MangaDex@Home. O leitor oferece rolagem contínua ou uma página, RTL/LTR no modo paginado, atalhos de teclado, seleção de página e navegação explícita entre capítulos. `loading="lazy"` e `decoding="async"` evitam solicitar/decodificar antecipadamente todas as imagens de capítulos longos. A posição do leitor e a direção escolhida se adaptam à largura disponível.

## Busca visual e capas

O campo do cabeçalho é compartilhado pelas telas. `Ctrl+K` foca a pesquisa; submeter o campo abre ou atualiza a rota `search`. Um destaque/card da descoberta inicia busca pelo título e referência canônica em vez de abrir detalhes sem verificar disponibilidade nas fontes.

Os cartões da home e da busca carregam preview sob demanda, após atraso de hover ou foco por teclado. Quando há AniList ID confirmado, a prévia consulta esse ID; não reinterpreta apenas o título, o que poderia mostrar episódios de um remake diferente. Sem ID canônico, mantém a busca por título. O painel compacto é portal para `document.body`, tem posição fixa ao lado do card, tema copiado da raiz e z-index fora do carrossel, para evitar recorte por `overflow`. Ele escolhe o lado com espaço disponível e recalcula a posição ao rolar, redimensionar ou alterar a dimensão do card. Título e sinopse são limitados a duas e três linhas; o painel não cria rolagem interna. A tela compacta não mostra painel hover.

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
