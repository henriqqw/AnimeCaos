# System design — AnimeCaos

Status: a especificação orienta o visual e vários padrões já estão presentes na interface React. Conferida em 20/10/2026. A extração futura de telas de `App.tsx` em componentes menores e a validação visual no app empacotado continuam pendentes; builds permanecem adiados.

## Comportamentos registrados nesta revisão

- O resumo de hover usa primeiro a sinopse já carregada no card e recebe metadados complementares sob demanda. Ele é criado como portal em `document.body`, com posição fixa acima do carrossel, e reposiciona ao rolar/redimensionar; em larguras compactas fica oculto porque não há hover útil em toque.
- Desktop tem botão de recolher/expandir junto à marca. Até 760 px, o botão aparece no cabeçalho e o recolhimento reduz a navegação inferior. A preferência de sidebar fica em `localStorage`.
- No desktop, a base da sidebar mantém links por ícone para GitHub, site, Instagram e Twitter/X; na navegação recolhida, os quatro atalhos usam uma grade 2×2. Em telas até 760 px, eles ficam ocultos para preservar a barra inferior de navegação.
- Configurações inclui uma seção final “Found a bug?” com uma variação ampliada da mascote detetive de cabelo mais simples e arredondado à direita do texto e das ações. A arte reduz gradualmente em telas menores. O reporte de bugs e melhorias abre o GitHub Issues; perguntas abrem a categoria Q&A do Discussions. O cabeçalho não usa eyebrow nem ícone ao lado do título.
- Os carrosséis têm setas laterais quando há conteúdo fora da área visível e também respondem às setas do teclado quando o foco está no trilho.
- O destaque usa ação “Assistir” com ícone de play, mas mantém o fluxo de pesquisa pelo título selecionado; ele não começa reprodução direta sem seleção de uma opção disponível.
- Descoberta usa descrição traduzida para pt-BR pelo serviço de metadados. Falha ou indisponibilidade da tradução deve permanecer tolerável.
- Categorias de mangá aparecem logo abaixo do banner e antes de “Continue lendo”. Mostram apenas o título e o contador no cabeçalho, com tiles monocromáticos de profundidade discreta. Por padrão, duas fileiras ficam visíveis; “+ Ver mais” revela as restantes e “− Ver menos” recolhe a grade. As linhas preenchem a largura disponível para não deixar lacunas na última fileira; cor por gênero, brilho e ornamentos não fazem parte do tratamento visual.
- Os arquivos de ícone e o lettering da interface foram atualizados com a marca enviada. A sidebar expandida e a tela de carregamento usam o lettering recortado; a versão quadrada permanece nos ícones do aplicativo. Aplicações abertas precisam ser reiniciadas para atualizar o ícone da janela/taskbar; o pacote distribuído não foi recompilado.

## Objetivos de experiência

- A pessoa identifica rapidamente onde está, o que pode fazer e como voltar.
- Pesquisa e reprodução têm prioridade; listas, histórico e downloads permanecem acessíveis em um único nível de navegação.
- Estados de carregamento, vazio, erro, indisponibilidade e sucesso são explícitos e oferecem uma ação seguinte útil.
- A interface não exibe nomes, marcas ou URLs das fontes de catálogo nos fluxos comuns. Diagnósticos técnicos podem manter esses dados em uma área avançada.
- Reduzir decisões concorrentes, texto decorativo e controles repetidos. Preferir rótulos concretos a ícones sem legenda.

## Identidade visual

Usar a marca AnimeCaos em `assets/icons/icon.png` e `assets/icons/wordmark.png`. O ícone quadrado preserva a arte enviada; o lettering é creme sobre transparência e aparece na sidebar expandida e na tela de carregamento. A cópia web fica em `frontend/public/`. Os antigos `public/zinnes_logo.webp` e `assets/zinnes_logo.webp` foram arquivados em `Legacy/` porque pertencem à Zinnes e não são a identidade do aplicativo.

Preservar o desenho e a proporção das letras. A versão da interface remove o fundo vermelho e mantém os vazios internos das letras transparentes; no tema claro, o lettering é invertido para manter contraste. O ícone quadrado usa o arquivo original como fundo da janela/taskbar. Não deformar o lettering nem acrescentar efeitos.

### Tokens

| Token | Claro | Escuro |
|---|---|---|
| Fundo principal | `#F7F7F5` | `#151515` |
| Superfície | `#FFFFFF` | `#1D1D1D` |
| Superfície elevada | `#F0F0EE` | `#252525` |
| Texto principal | `#171717` | `#F2F2F0` |
| Texto secundário | `#666663` | `#A7A7A2` |
| Borda | `#E4E4E0` | `#333330` |
| Acento | `#C83232` | `#E04A4A` |
| Acento hover | `#AA2525` | `#F06464` |
| Erro | `#B42318` | `#F97066` |
| Sucesso | `#26734D` | `#64B987` |

Usar o acento vermelho em ações primárias, foco selecionado e progresso. Vermelho não deve ser o único canal para comunicar erro ou estado. Não usar gradientes luminosos, glow, neon ou sombras decorativas. Sombras são reservadas a menus e diálogos sobrepostos, com baixa opacidade e deslocamento curto.

### Tipografia e espaçamento

- Fonte preferencial: Inter quando instalada; fallback para Segoe UI, SF Pro e sans-serif do sistema.
- Escala: título de página 24/32 px; título de seção 18/26 px; corpo 14/22 px; apoio 12/18 px. Evitar texto abaixo de 12 px.
- Escala de espaço baseada em múltiplos de 4: `4, 8, 12, 16, 24, 32, 48, 64 px`.
- Usar 8 px dentro de controles, 12–16 px entre controles relacionados, 24–32 px entre seções e 48 px para separar áreas principais.
- Alvos interativos de pelo menos 40 × 40 px; controles primários preferencialmente 44 px de altura.
- Cantos moderados e consistentes: 6 px para controles, 10 px para cartões, 14 px para diálogos. Evitar arredondar tudo como cápsula.

### Ícones e movimento

Usar uma família vetorial única, com traço consistente e alinhamento óptico. Ícone sem rótulo só é permitido para uma ação universal quando houver `aria-label` e tooltip. Não usar emoji como ícone funcional. Transições breves (120–180 ms), sem parallax e sem animação contínua fora de estados de progresso ativos. Respeitar `prefers-reduced-motion`; manter apenas o feedback explícito e temporário de carregamento da busca (spinner e shimmer de baixo contraste), encerrando-o quando a operação termina.

## Temas, splash e carregamento

- Preferência persistida no SQLite: `Sistema`, `Claro` ou `Escuro`. `Sistema` é o padrão inicial e acompanha a preferência atual do sistema operacional. A splash mantém fundo preto para integrar o WebM opaco; o tema escolhido é aplicado à interface principal antes de ela aparecer.
- O tema fica no elemento raiz e é aplicado antes de mostrar o conteúdo principal.
- Splash: usa a composição horizontal aprovada da mascote à esquerda e do lettering AnimeCaos à direita, em fundo preto e com rótulo estático “INICIANDO”. A mascote aparece somente pelo WebM local, pré-carregado no documento HTML; não há poster ou fallback PNG. O fade-in de 560 ms da mascote e da wordmark começa junto quando o primeiro quadro está decodificado e a logo carregada. Erros de vídeo causam uma tentativa automática de reload e permitem retry manual sem mostrar a logo sozinha. Mascote e logo fazem fade-out de 600 ms. A barra responsiva tem 10 px de altura, exibe o percentual à direita e considera vídeo, wordmark, resposta de `Initial()` e duração; conclui durante a saída. A splash permanece por pelo menos 4 s — 3,4 s antes do fade-out e mais 600 ms da saída — e aguarda a inicialização. A interface sob a camada fica indisponível até o fade-out terminar, mesmo com `prefers-reduced-motion`. O layout compacta a altura e muda a composição em janelas estreitas. A sidebar expandida usa o mesmo lettering e a recolhida usa o ícone quadrado.
- Skeletons usam superfícies neutras próximas à tela final, com brilho animado muito sutil ou sem animação. Reservar o espaço final para evitar layout shift; aplicar movimento apenas se não houver preferência de movimento reduzido.
- Carregamento de busca oferece cancelar. Operações antigas canceladas não podem substituir resultados novos.

## Arquitetura de navegação

Navegação principal: Início, Pesquisar, Minha Lista, Histórico, Downloads, Mangás e Configurações. Contas e Diagnóstico ficam em Configurações. Em telas largas, usar sidebar compacta com texto; abaixo de 760 px, a implementação atual usa navegação inferior. A ação voltar deve respeitar a pilha atual e o botão de navegação do sistema.

### Mapa de telas e estados

| Tela | Conteúdo e hierarquia | Estados e ações |
|---|---|---|
| Início | Continuar assistindo, destaque e carrosséis; capa, título e metadados curtos | Skeleton; vazio com ação Pesquisar; erro recuperável; tocar em um título inicia pesquisa por aliases e mostra as opções disponíveis |
| Pesquisa | Campo único compartilhado no cabeçalho; esta tela mostra resultados e paginação, sem repetir outro formulário de pesquisa | Vazio inicial; digitando; skeleton de cards com indicador sutil de acento e cancelar; carregamento adicional preserva resultados; nenhum resultado com sugestão de alias; falha parcial; erro de rede com tentar novamente |
| Resultados | Título comum, imagem, áudio/idioma quando conhecido e formato/ano quando útil | Não mostrar a fonte; títulos ambíguos permanecem opções separadas; ação abre detalhes da opção escolhida |
| Detalhes | Capa, título canônico, sinopse curta, status e ações principais; episódios agrupados por temporada quando essa informação for explícita | Temporada desconhecida como “Sem temporada informada”; episódios indisponíveis não escondem o anime; alternar lista e episódios sem perder contexto |
| Reprodução | Vídeo dominante, barra de reprodução, título e episódio atual, anterior/próximo e controles acessíveis | Inicializando; carregando; reproduzindo; pausado; erro de stream; fim natural; fechamento manual. Autoplay somente no fim natural |
| Minha Lista | Grade compacta com busca/filtro e remoção direta reversível | Skeleton, lista vazia com chamada para pesquisar, erro recuperável |
| Histórico | Continuar assistindo em primeiro plano, progresso e data em apoio; lista paginada em blocos de 24 itens | Controles anterior/próxima mostram intervalo e página; item sem ID seguro oferece busca; remover item atualiza os resultados e mantém uma página válida |
| Downloads | Fila ativa separada dos concluídos, progresso, velocidade, estimativa e espaço | Aguardar, baixar, concluir, cancelar, duplicado, falha parcial, arquivo indisponível e offline |
| Mangás | Mesmo banner spotlight, largura, CTA e prateleiras da Home; categorias por gênero; Top mangás/Em alta/Em publicação e leitura retomável | Busca única no cabeçalho; categorias filtram pelo ID da tag; ranking usa seguidores; “Em alta” usa capítulos enviados recentemente; status de publicação vem do MangaDex; erro com retry e cache |
| Leitor de mangá | Página ocupa a maior área; barra mínima com capítulo, página e navegação | Carregamento por página, falha individual, offline, alteração de orientação e retomada do progresso |
| Contas | Estado de sessão, perfil e ações de conectar/atualizar/desconectar | Navegador aberto, retorno OAuth, erro de autorização, sem sessão, sessão expirada e sincronização |
| Configurações | Uma coluna contínua com índice; seções abertas, controles relacionados em duas colunas quando há espaço e resumo das contas | Índice acompanha a rolagem; temas segmentados; switches acessíveis; estado salvando/salvo/falha e retry sem botão global |
| Diagnóstico | Dependências, logs técnicos e exportação controlada | Nomes/IDs de fontes e erros brutos podem aparecer aqui; ocultar tokens, cookies, URLs assinadas e dados pessoais |

## Componentes e regras

- **AnimeCard:** capa com proporção uniforme, título em até duas linhas e no máximo dois metadados úteis. Área inteira é acionável e tem foco visível. Nas prateleiras da Home, hover/foco também revela “Ver anime” sobre a capa; a sobreposição não cria uma ação separada e respeita movimento reduzido. Não mostrar a origem da opção.
- **Rating:** estrela exibida em amarelo, independentemente do tema; o valor numérico permanece texto para não depender somente da cor.
- **Spotlight:** banner legível com camada neutra suficiente para contraste, título, sinopse curta e uma ação principal. Não depender de uma imagem para transmitir nome ou botão.
- **SearchBox:** rótulo acessível persistente, limpar e cancelar explícitos; Enter executa a busca. `Ctrl+F` foca a pesquisa. Resultados novos invalidam operações antigas.
- **EpisodeList:** agrupamento por temporada apenas quando fornecida pela fonte/metadado verificável. Usar ID estável e não posição do episódio como identidade.
- **PlayerBar:** controles com rótulo e estado, foco por teclado, seek com valor anunciado, teclado documentado e volume separado.
- **Progress:** texto equivalente a percentagem/estado; barra não comunica sozinha.
- **Dialog/Toast:** diálogos só para decisão que bloqueia fluxo; feedback temporário para ações reversíveis; alertas de erro ficam até serem resolvidos ou dispensados.
- **Skeleton:** mantém dimensão da capa/cartão/linha final e evita mudanças de layout.
- **Ação Minha Lista nos detalhes:** reutilizar o ícone da navegação lateral, sem texto visível; mostrar o acento vermelho quando salvo e manter rótulo acessível, tooltip e estado pressionado sincronizados com a biblioteca persistida.
- **Continuar:** no Histórico e no carrossel “Continuar assistindo”, exibir o ícone de play da família visual da sidebar à esquerda do rótulo; o botão mantém seu nome acessível e a mesma ação de retomada.
- **Ações de arquivos offline:** usar botões de ícone compactos para reproduzir/ler, abrir a pasta do arquivo e excluir. Cada controle mantém nome acessível e tooltip; exclusão conserva confirmação.
- **Filtro de temporada:** usar menu próprio no estilo das superfícies do app, com opção atual identificada, foco visível e navegação por teclado; evitar menus nativos do sistema.
- **Configurações:** usar seções abertas em coluna única, separadas por divisores e com índice que quebra linha em telas estreitas. Cada grupo mantém rótulos e descrições próximos aos controles; campos relacionados podem usar duas colunas e empilham quando o espaço não comporta. A interface aplica a escolha imediatamente e apresenta o estado do autosave, com retry em falha. Switches compartilham o mesmo controle visual, estado acessível e foco visível. A seção Integrações mostra um resumo e encaminha a gestão de contas à tela própria. Manutenção informa cada resultado junto às ações e não altera o estado de preferências; Feedback direciona issues e dúvidas aos canais GitHub correspondentes.
- **Preview dos cards:** anime usa metadados carregados sob demanda; mangá usa título e sinopse já presentes no catálogo, sem chamadas por card nem subtítulo. O painel compacto fica ancorado ao card, escolhe o lado com espaço disponível e limita título a duas linhas e sinopse a três. Não deve criar rolagem interna nem cobrir desnecessariamente o carrossel; movimento respeita `prefers-reduced-motion`.
- **Descoberta de mangás:** usa os mesmos componentes visuais `spotlight`, `home-shelf`, `shelf-heading` e `Rail` da Home e a mesma largura da área de conteúdo. O cabeçalho contextual é a única busca. O banner usa uma obra real do ranking e abre detalhes/capítulos. Prateleiras usam ordenações e status fornecidos pelo MangaDex; gêneros filtram pelo ID da tag. Como a fonte não publica temporada de anime para mangá, “Em publicação” ocupa a prateleira de séries ativas, sem inventar calendário sazonal. As imagens das prateleiras são lazy-load e a resposta agregada usa cache para reduzir chamadas ao catálogo.
- **Mascote AnimeCaos:** manter a personagem com cabelo longo vermelho liso dividido ao meio, olhos vermelhos, chifres escuros, camiseta cropped preta de caveira e saia preta lisa. A arte aprovada usa chibi cartoon 2D, contorno preto espesso e paleta curta de vermelho, creme e carvão. A versão normal é de corpo inteiro; a mini é superdeformed, com cabeça maior e corpo simplificado. A miniatura de 256 px deriva da versão mini. `poses/` contém seis ângulos/vistas e `reactions/` contém expressões. Na interface, usar a reação de dúvida com cabelo simplificado em buscas sem resultados, a pose do coração na lista vazia, a arte da detetive com lupa em erros inesperados/recuperáveis e feedback, a mascote lendo no fim da página do catálogo de mangás e a reação de piscadela com língua à mostra no fim da Home. A arte da Home usa camiseta preta e caveira alinhada ao centro do torso. A mascote de leitura usa capa preta com a logo e páginas internas brancas. As duas reações decorativas ficam alinhadas à direita no fim do conteúdo da respectiva página, no fluxo normal e com espaço próprio, sem sobrepor cards ou ficar presas à janela. A raiz (`html`, `body` e `#root`) ocupa a janela sem rolagem própria; a rolagem vertical fica em `main`. Não colocar um retrato avulso no cabeçalho nem repetir a mascote em áreas sem contexto. As imagens contextuais carregam sob demanda; as duas reações de página carregam imediatamente e têm fundo transparente.
- **Links nos estados vazios:** mostrar GitHub e site oficial como ícones compactos com tooltip e nome acessível; não usar rótulos textuais de comunidade nesses atalhos.

## Responsividade

- **Amplo (>1050 px):** sidebar expandida com opção de recolher para uma coluna de ícones; conteúdo e carrosséis adaptam ao espaço restante.
- **Médio (761–1050 px):** sidebar mantém 188 px e reduz o espaçamento interno dos botões para preservar rótulos longos; conteúdo, cartões e banner reduzem espaçamento. Abaixo de 760 px, a navegação muda para a barra inferior.
- **Compacto (≤760 px):** navegação inferior; o botão da sidebar fica no cabeçalho; recolher reduz a barra e esconde rótulos. Em telas estreitas, a grade usa duas colunas; player e fila reservam espaço para a navegação.
- **Janela estreita/altura baixa:** telas sem largura suficiente devem empilhar imagem e texto, evitar larguras mínimas fixas, oferecer rolagem vertical e manter controles essenciais visíveis.
- Testar redimensionamento contínuo, zoom/escala, orientação e conteúdo com títulos muito longos. Nenhum texto, controle ou ação deve depender de hover.

## Acessibilidade e conteúdo

- Navegação completa por teclado, ordem de foco coerente, foco visível e retorno de foco após fechar diálogo.
- Semântica HTML, títulos hierárquicos, nomes acessíveis para controles e estados anunciados com `aria-live` quando apropriado.
- Contraste WCAG AA para texto e controles; áreas de foco não podem ser confundidas com o acento de marca.
- Não comunicar somente por cor, posição, áudio ou animação. Imagens decorativas têm `alt=""`; capas com função levam título acessível.
- Evitar jargão, mensagens de stack ou nomes de provedores no fluxo comum. Mensagens dizem o que ocorreu e sugerem uma ação concreta.
- A área avançada de diagnóstico não pode exibir credenciais, tokens, cookies ou URLs temporárias.

## Métricas qualitativas de aceite

1. Uma pessoa nova consegue pesquisar um título e iniciar reprodução sem conhecer aliases ou a origem do resultado.
2. É possível cancelar uma busca e iniciar outra sem resultados antigos reaparecerem.
3. Temporadas incertas não são apresentadas como fatos; títulos ambíguos não são unidos silenciosamente.
4. O CSS adapta o layout desde 480 px, com teclado, escala e tema claro/escuro/sistema; a checagem visual em janelas empacotadas segue pendente.
5. Todos os estados têm hierarquia visual clara, próxima ação óbvia e texto conciso.
6. A marca, tipografia, vermelho de acento e padrões de espaçamento são consistentes em toda a aplicação.
