# Changelog

## Em desenvolvimento — revisão de interface e documentação

- A resolução da SushiAnimes aceita os atributos `data-id` e `data-embed` e usa o extrator de player filtrado quando a opção AJAX não está disponível. O fallback Blogger da AnimesOnlineCC tenta Selenium quando o RPC não publica renditions; o navegador também pode iniciar silenciadamente um vídeo HTML5 dentro do player.
- Consultas que terminam em ano, como `Hunter x Hunter 2011`, pesquisam também o título base, mas só mantêm resultados que correspondam ao ano consultado; isso recupera o título na Otakulogia sem misturar a versão de 1999.
- Testes live recentes confirmaram busca → resolução → gateway → MPV para SushiAnimes, AnimesOnlineCC e Otakulogia. AnimesOnlineCC Hunter E1 recebeu `payload=null` do RPC Blogger e continua sem mídia extraível; Hunter E2 e Naruto E1 tocaram. No app, Hunter 2011 E1 passou pelo fallback Otakulogia. Detalhes e limites em `docs/TESTING.md`.
- A busca passa a consultar quatro fontes registradas; fontes sem fluxo reproduzível confirmado foram retiradas do catálogo.
- O encerramento de árvore do GeckoDriver no Windows limita `taskkill` a 2 s e mantém a tentativa de terminar o processo do driver se o comando falhar. Um teste Selenium opt-in usa servidor HTTP local para validar a rejeição de um desafio persistente.
- A sessão Firefox usa `pageLoadStrategy=eager` para iniciar o polling após o DOM inicial e um diretório temporário exclusivo para cache em disco, removido no encerramento. Erros de timeout registram o último estado observado e continuam identificáveis com `errors.Is`; `$env:ANIMECAOS_BROWSER_HEADLESS='0'` abre a janela para auditoria visual, mantendo a rejeição rápida de catálogo ausente/incompleto e de páginas de verificação.
- Arquivos disponíveis offline agora usam ícones compactos para reproduzir/ler, abrir a pasta do item e excluir; o backend valida o caminho antes de revelar a pasta.
- As ações “Continuar” do Histórico e do carrossel “Continuar assistindo” agora mostram o ícone de play à esquerda, mantendo o rótulo acessível e a retomada existente.
- Reprodução de arquivo baixado agora compartilha o histórico canônico do anime; entradas locais duplicadas são consolidadas e continuam retomando pelo arquivo offline.
- Abrir pasta reutiliza a janela do Explorer quando já existe e a traz para frente; caso contrário, abre o diretório e aguarda a janela aparecer.
- O scraping de players agora usa contêineres de vídeo em vez de varrer iframes da página toda; navegadores Selenium/Chromium bloqueiam hosts conhecidos de anúncio/rastreamento por proxy local e não abrem pop-ups automáticos. Clientes HTTP, validação e gateway MPV também interrompem redirects para esses hosts; intersticiais reconhecidos ficam indisponíveis, sem seguir o link.
- Spinner da busca volta a girar mesmo em sistemas com movimento reduzido; skeletons recebem shimmer suave, discreto e escalonado durante o carregamento.
- Estados genéricos “Carregando…” agora mostram três pontos pulsantes em vermelho, incluindo o carregamento de episódios.
- Skeleton inicial da busca agora exibe 10 cards para completar melhor a grade durante o carregamento.
- Busca só publica animes cujo episódio de amostra passou pelo preflight de mídia; cards chegam em um lote final, sem URLs de stream no resumo. Consultas com temporada explícita validam E1 daquela temporada.
- Corrigida a busca vazia quando o preflight atingia o prazo: cards já aprovados são preservados no lote final; candidatos pendentes seguem ocultos. Filas separadas por provedor evitam starvation, e o orçamento do preflight caiu de 20 s para 12 s.
- Busca prioriza títulos principais sobre sinônimos ambíguos do AniList e agrupa fontes apenas quando a identidade canônica coincide.
- Canonicalização agora prioriza o título principal do provedor sobre aliases genéricos: a busca `hunter` volta a mostrar separadamente Hunter x Hunter (1999) e (2011), com o E1 da Otakulogia aprovado no preflight.
- A busca também aceita títulos relacionados quando a consulta aparece como sequência completa de palavras no título principal. `hunter` pode encontrar `City Hunter`; o preflight continua obrigatório e cada identidade permanece separada. A lista final é exibida em lote com limites de descoberta/preflight e cancelamento.
- Busca com temporada, como `Tensei Shitara Ken Deshita 2nd Season`, também consulta o título base. Variantes só recebem a identidade AniList da temporada depois de uma fonte confirmar o E1 sazonal; a disponibilidade e o cache distinguem T2 E1 de E1.
- Consultas AniList auxiliares para identidade são agrupadas em uma chamada GraphQL e cacheadas por título. Na amostra live `Tensei Shitara`, sete grupos reproduzíveis levaram 8,29 s no pacote; as três fontes de Dai Nana Ouji foram consolidadas em um card.
- Páginas de busca dos provedores têm cache curto (30 s com itens, 10 s vazias); o preflight de mídia segue sendo uma etapa separada para limitar cards sem stream funcional.
- Preflight usa concorrência 6/2 por provedor, timeout por fonte e cache efêmero; a seleção de playback compara áudio, resolução e bitrate e tenta outra candidata apenas antes de avançar no MPV.
- MPV agora reporta dimensões; FFprobe mede arquivos diretos quando instalado. Selenium WebDriver com GeckoDriver/Firefox é opcional para players dinâmicos, preservando Chromium como fallback.
- Selenium agora lê playlist/config do JWPlayer e pode ser aberto visivelmente por `ANIMECAOS_BROWSER_HEADLESS=0`. Firefox 157.0.1 e GeckoDriver 0.36.0 foram configurados neste ambiente; a validação também rejeita arquivos que FFprobe confirma não terem áudio.
- `ANIMECAOS_FFPROBE_PATH` configura FFprobe fora do `PATH`, e a busca também detecta `bin/ffprobe.exe` no workspace.
- O `AnimeCaos-dev` foi reiniciado com `wails dev` e está aberto para validação manual.
- Um teste atual do embed Anidrive retornou apenas um clipe VP9 de 6,876 s, 320×100 e sem áudio. FFprobe o recusou antes do MPV; Anidrive segue sem E2E reproduzível confirmado para esse episódio.

- Corrigido o recorte das prévias de anime: o painel agora fica acima dos carrosséis e acompanha rolagem/redimensionamento.
- Sidebar recolhível com animação curta, controle visível no desktop e no cabeçalho compacto.
- Ação do destaque da home agora usa ícone de play e texto “Assistir”; a busca de opções permanece parte do fluxo.
- Reprodução agora valida variantes HLS e tenta a mesma temporada/episódio em outra fonte quando o vídeo primário retorna erro.
- Fallback de episódio resolve fontes alternativas em paralelo, conserva preferência determinística, remove URLs repetidas e decodifica escapes comuns do player HTML do AnimesOnlineCC antes da validação de mídia.
- Scraper do AnimesOnlineCC agora usa Chrome/Chromium/Edge headless como fallback quando o player só aparece após JavaScript; o `src` renderizado passa pela resolução e validação habituais.
- Validação live em 10 títulos encontrou mídia amostrada nos 10 casos AnimesOnlineCC; Demon Slayer também passou pelo fallback agregado após 404 no AnimeFire. AnimeFire forneceu mídia acessível em apenas um dos dez títulos amostrados.
- Sessões de MPV encerradas limpam os controles antigos; o fallback entre catálogos aceita um título de episódio exato e único quando as fontes organizam as temporadas de formas diferentes.
- Validação manual no app Windows de desenvolvimento: busca, seleção de temporada e reprodução no MPV aprovadas em 20 títulos. Também foram registrados erros HTTP 404 em cinco outros títulos; os resultados estão em `docs/TESTING.md`.
- Checagem live anterior consultou dez combinações de título e fonte para cinco séries, mas só confirmava a obtenção de URL. O teste agora valida a resposta de mídia antes de contar um episódio como acessível; resultados atuais estão em `docs/TESTING.md`.
- Teste live de catálogo agora lê playlists HLS ou valida arquivos diretos em amostras do início, meio e fim da série; o teste anterior contava apenas o retorno de uma URL.
- Revalidação de Hunter x Hunter e One Piece separou URL de catálogo e mídia acessível: episódios antigos amostrados responderam 404, enquanto o episódio recente de One Piece teve HLS válido; Hunter x Hunter 2011 abriu o episódio 2 pelo fallback secundário.
- Mensagem de HLS 404 agora explica que o servidor não encontrou o arquivo do episódio; o teste cobre essa distinção.
- Ícones-fonte do Wails foram alinhados à logo AnimeCaos e incluídos nas exceções de versionamento. O executável ainda precisa ser reconstruído para confirmar o ícone da janela/taskbar.
- Organizada a documentação em capítulos de arquitetura, backend, frontend, dados, rede, integrações, fluxos de produto, operações e testes; criado `AGENTS.md` para orientar atualização contínua.
- Documentada a arquitetura de expansão do catálogo, o estado real dos provedores e os critérios para integrar novas fontes públicas sem contornar controles de acesso.
- `media.Validate` e o gateway agora preservam o User-Agent específico da fonte. Selenium/Chrome visível extraiu a mídia do JWPlayer Anidrive e o MPV avançou 2 s com H.264/AAC; o teste de AnimeOnlineCC também chegou ao EOF com H.264/AAC.
- AnimeOnline.io/Anidrive ainda não tem adaptador de catálogo no app.
- Validação automatizada registrada em `docs/TESTING.md`: `go test ./...`, checagem TypeScript e 18 testes de frontend passaram. Build e empacotamento continuam sem execução.

## Próxima versão Go

- Busca agora mostra indicador de progresso e skeletons de cards com acento vermelho discreto; carregar mais preserva os resultados já visíveis.
- Histórico de animes paginado em grupos de 24, com controles responsivos para avançar e voltar.
- Seletor de temporada da tela de detalhes substituído por um menu próprio acessível.
- Ação de Minha Lista nos detalhes usa o ícone da sidebar e fica vermelha quando salva.
- Preview dos cards compactado, ancorado ao card e com sinopse limitada, sem rolagem interna.
- Migração da aplicação desktop para Go, Wails 2, React e TypeScript.
- Catálogo multilíngue, resolução de variantes entre AnimeFire, AnimesOnlineCC, SushiAnimes e Otakulogia, e seleção de áudio por player.
- Temas claro, escuro e sistema; splash com identidade AnimeCaos; layout responsivo e skeletons.
- Fontes, testes, scripts e documentos do aplicativo Python preservados em `Legacy/`.
- Revisão técnica e especificação visual/UX atualizadas em `docs/`.

O histórico detalhado da versão Python está em `Legacy/CHANGELOG.python.md`.
