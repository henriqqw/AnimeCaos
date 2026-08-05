# Changelog

Todas as mudanças relevantes do projeto são documentadas aqui.

## [2.0.0] — 2026-08-05

### Adicionado
- **Minha Lista**: nova página de watchlist pessoal, com ícone dedicado na
  sidebar. Adicionar/remover animes direto pela home, pela busca ou pela
  página de detalhes, com o mesmo comportamento de "listas" das streamings
  profissionais. Estado persistido em disco via `WatchlistService` e
  refletido em tempo real em todos os cards do app.
- **Preview ao passar o mouse (estilo Crunchyroll)**: hover em qualquer
  capa (home ou busca) expande um card com nota, "1 Temporada", número de
  episódios e sinopse (dados reais da AniList — nenhum campo fictício),
  fundo transparente sobre a própria capa do anime, e botões de Assistir e
  Adicionar/Remover da Lista.
- **Manga**: `MangaCard`, `MangaHomeView`, `MangaDetailView` e
  `MangaReaderView` para navegar, buscar e ler mangás, incluindo leitura
  offline de capítulos já baixados (CBZ) e banner da editora Zinnes na
  home de manga.
- **AniList**: integração completa (login, sincronização de progresso,
  nota/episódios/sinopse nos cards) e **Discord Rich Presence** mostrando o
  que está sendo assistido.
- **Home redesenhada**: banner de destaque (spotlight) com o anime da
  temporada, seções "Em Alta" e "Temporada Atual" com scroll horizontal
  (arraste, roda do mouse e setas), splash de carregamento que busca tudo
  de verdade antes de abrir a home.
- **Downloads**: cancelamento de download com limpeza automática dos
  arquivos temporários; botão de limpar busca.
- Cache de descoberta (trending/temporada) com TTL de 4h e fallback offline
  usando o cache expirado quando a AniList está fora do ar.
- Pool de drivers do Firefox e cache de URLs de player em disco (4h de
  TTL) para acelerar buscas repetidas.
- Suíte de testes ampliada de forma consistente a cada mudança — mais de
  60 novos testes desde a v0.1.3 (168 no total).

### Melhorado
- **Qualidade de vídeo do AnimeFire**: sempre escolhe a melhor resolução
  disponível por episódio (1080p > 720p > 360p), com fallback automático
  para o que existir — antes ficava preso em 360p mesmo quando 720p/1080p
  estavam disponíveis.
- **Rate limit da AniList**: um limitador compartilhado entre todos os
  serviços que conversam com `graphql.anilist.co` garante que nenhuma
  chamada (login, sincronização, cards) estoure o limite por IP e derrube
  outra chamada não relacionada. A busca de sinopse dos cards de
  descoberta deixou de ser feita para ~50 animes de uma vez ao abrir a
  home e passou a ser sob demanda, só ao passar o mouse.
- **Títulos longos nos cards**: paravam de quebrar no meio do caractere;
  agora o texto é calculado com precisão (via `QFontMetrics`) e termina
  em reticências quando necessário, tanto no card normal quanto no painel
  de preview.
- Reorganização da GUI em `views/`, `widgets/`, `overlays/` e `workers/`,
  separando responsabilidades que antes viviam em poucos arquivos enormes.
- Tradução PT-BR com fallback: mantém o texto em inglês se o Google
  Translate falhar, em vez de quebrar a exibição.
- Remoção dos scrapers `animeplayer`, `hinatasoul` e `animesvision`
  (fora do ar/instáveis), com correção de contenção de lock nas buscas.

### Corrigido
- **Listagem de episódios incorreta em animes com muitos episódios** (ex.
  One Piece, 1172 episódios): o repositório escolhia a lista mais curta
  entre as fontes disponíveis em vez da mais longa, cortando episódios.
- **Painel de preview "grudado" na tela**: ao trocar de página, dar play
  ou rolar a tela com o mouse sobre uma capa, o painel expandido podia
  ficar flutuando por cima do conteúdo errado — corrigido fechando (e
  bloqueando reabertura por um instante) sempre que a página muda, a grade
  é reconstruída ou há scroll.
- **Scroll travado ao passar o mouse sobre uma capa em hover**: a rolagem
  (roda do mouse) parava de funcionar assim que o painel de preview
  aparecia sobre o card.
- **Flicker no hover**: o painel de preview piscava/sumia e voltava toda
  vez que o mouse se movia sobre a capa.
- Ícone de deletar episódio no Downloads aparecia como um quadrado vazio
  — trocado por um ícone de lixeira visível. Ícone da sidebar de Downloads
  trocado de pasta para um ícone de download.
- Banner de aviso quando a AniList está fora do ar, com mensagens
  específicas por tipo de erro (offline, rate limit, autenticação,
  servidor, IP bloqueado).
- Vazamento de memória/crash por conflito de `QPainter` em `AnimatedButton`
  ao recriar o efeito de opacidade repetidamente.
- Checksum SHA-256 incorreto do geckodriver v0.36.0 no build Flatpak.

---

## [0.1.3] e anteriores

Ver histórico completo em `git log` a partir da tag `v0.1.0`.
