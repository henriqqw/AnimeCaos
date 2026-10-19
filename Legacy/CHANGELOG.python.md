# Changelog

Todas as mudanças relevantes do projeto são documentadas aqui.

## [2.1.0] — 2026-08-06

### Adicionado
- **Dimensionamento da interface (acessibilidade)**: slider de 100%–200%
  em Configurações, aplicado via `QT_SCALE_FACTOR` — escala fontes, ícones
  e cards de uma vez, sem depender de reescrever cada tela.
- **Nova tela de Configurações**, com botão dedicado na sidebar: aparência
  (zoom), player, downloads (pasta, simultâneos, auto-fechar) e status de
  dependências (mpv/yt-dlp/geckodriver) com dica de instalação por
  plataforma.
- **Player externo**: além do mpv (padrão), agora é possível tocar no
  player padrão do sistema ou num player personalizado. Fora do mpv,
  autoplay e sincronização de progresso com a AniList ficam indisponíveis
  — a tela de Configurações avisa isso ao trocar de modo.
- **Downloads em fila real**: downloads simultâneos (1–5, configurável),
  download em lote (seleção múltipla na tela do anime) e downloads em
  segundo plano — o overlay pode ser ocultado sem cancelar o que está
  baixando, e fecha sozinho ao terminar (configurável).
- **Subpastas por anime** em `Downloads/AnimeCaos/`, agrupando os
  episódios baixados. Downloads feitos antes desta versão são migrados
  automaticamente na primeira vez que a tela de Downloads é aberta.
- A janela principal agora lembra a última posição/tamanho ao reabrir.
- Aviso proativo (na home e em Configurações) quando o mpv ou o yt-dlp não
  são encontrados, com instrução de instalação específica da plataforma —
  em vez de só falhar ao tentar reproduzir.
- **AppImage para Linux**, publicado automaticamente via GitHub Actions a
  cada tag de release, com atualização automática (delta via zsync).

### Melhorado
- **Qualidade dos banners da home**: as imagens da AniList passaram a
  pedir `extraLarge` (caindo em `large` quando ausente), e o desenho do
  banner passou a considerar o `devicePixelRatio` da tela — antes o fundo
  era escalado para o tamanho lógico do widget, ficando borrado em telas
  HiDPI (e pior ainda com o zoom da interface ligado). Quando não há
  banner de verdade e o card cai no cover, um leve desfoque + escurecimento
  faz o upscale ler como escolha estética em vez de defeito.

### Corrigido
- **Ícone errado na barra de tarefas/título no Linux (Wayland)**: o app
  nunca chamava `setDesktopFileName()`, então o compositor não conseguia
  casar a janela com o `.desktop` e mostrava o ícone genérico do Wayland.
- **Erro seco de "mpv não encontrado" no Linux**: a detecção de binários
  só cobria caminhos comuns do Windows; agora também procura em
  `/usr/bin`, `/usr/local/bin`, Flatpak e Snap, e a mensagem de erro inclui
  o comando de instalação certo pra plataforma do usuário.
- Resolução do ícone/base path dependia do diretório de trabalho atual
  (`os.path.abspath(".")`), o que podia falhar quando o app era iniciado
  por um lançador `.desktop` com um cwd diferente.

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
