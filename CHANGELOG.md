# Changelog

## Preparação para publicação

- Builds instaladas Windows e AppImage Linux verificam releases ao abrir. A versão nova é baixada e validada por SHA-256 durante a splash e aplicada antes de liberar a interface; falhas de rede ou pacote deixam o app atual iniciar. `wails dev` e Flatpak não são atualizados por esse fluxo. Na migração da release v2.0.0 para Windows, o atualizador Python legado encontra o ZIP 3.x e pede confirmação; depois dessa atualização, a linha Go/Wails aplica as próximas versões durante a inicialização. Instalações Flatpak antigas devem migrar manualmente para o AppImage, pois o atualizador legado não sabe aplicar esse formato.
- Corrigido o CI que executava Go tests antes de criar `frontend/dist`; agora os runners instalam e compilam o frontend antes dos testes Go que incorporam seus assets.
- O workflow de release permite publicação Windows sem Authenticode quando os secrets de certificado não estão configurados, e registra essa condição nas notas e num asset. Quando os secrets existem, continua assinando/verificando os executáveis; `SHA256SUMS` recebe assinatura Sigstore em ambos os casos.
- Em 20/10/2026, foram recompilados localmente o ZIP e instalador Windows x64 e o AppImage Ubuntu 24.04 x86_64 da versão 3.0.0. Go, TypeScript, Vitest, runtimes de navegador/mídia, inicialização portátil Windows e smoke de update AppImage passaram. Os hashes estão em `release/SHA256SUMS`; os pacotes ainda não foram publicados e continuam pendentes de assinatura Windows, testes em máquinas limpas e resolução do fluxo MAL.
- Wails `dev` e o pacote instalado usam identificadores de instância separados. Abrir a build instalada não redireciona mais para uma janela `AnimeCaos-dev.exe` presa a um servidor Vite parado.
- Tokens OAuth AniList/MAL e Client Secret MAL passaram a usar Credential Manager no Windows e Secret Service no Linux. Instalações antigas migram credenciais do SQLite para o cofre e apagam a cópia ativa com secure delete/checkpoint/VACUUM; indisponibilidade do cofre aparece como erro, sem fallback em texto.
- Pacotes agora usam `3.0.0` como versão padrão; adicionados avisos de terceiros, textos de licença, inventário SHA-256 e coleta de proveniência/licenças dos pacotes MPV/FFmpeg.
- Criado CI Windows/Ubuntu e pipeline tag-based para portátil, instalador Inno Setup e AppImage; verifica Authenticode, checksums, assinatura Sigstore, reprodução MPV sintética com seek, update e preservação de dados.
- Adicionados smoke tests do Windows para migração de histórico legado e desinstalação sem remoção do banco, além de smoke do AppImage para startup e update.
- O pacote de produção agora falha se MPV/FFmpeg/FFprobe, Firefox ou GeckoDriver estiverem ausentes. Scripts baixam Firefox 157.0.1 e GeckoDriver 0.37.1 dos fornecedores oficiais com validação de SHA-512/SHA-256; o runtime completo vai no ZIP, instalador e AppImage, e o teste de release abre fixture com iframe criado por JavaScript usando esses binários empacotados. As DLLs do MPV também passam ao stage Windows.
- O AppImage local passou a preservar os binários upstream do Firefox e GeckoDriver após a coleta de dependências: o linuxdeploy alterava RPATH e corrompia a execução do GeckoDriver estático. A imagem final foi validada com fixture Selenium, reprodução/seek MPV, startup, update e preservação do banco em Ubuntu 24.04/WSL.
- WebView2 agora usa Fixed Version 155.0.4283.62, baixado do endpoint oficial e validado por assinatura Microsoft; o app carrega o runtime da própria instalação/ZIP, inclusive no modo portátil, sem depender de runtime no sistema ou download durante a primeira execução. A versão deve ser atualizada em cada ciclo de release.
- O smoke test Windows confirma que o processo WebView2 veio do bundle. A validação offline em VM limpa, a execução dos workflows remotos e o certificado de assinatura Windows continuam pendentes; nenhum artefato foi publicado por esta alteração.

## Em desenvolvimento — interface, janela e documentação

- A splash de produção usa somente o loop local `frontend/public/avatar_loop.webm` para a mascote; não carrega PNG de poster nem fallback estático. A página antecipa o download do vídeo, espera o primeiro quadro decodificado e sincroniza o fade-in de 560 ms com a wordmark. Se houver erro, tenta recarregar uma vez e oferece nova tentativa sem revelar a logo sozinha. O fundo preto acompanha o vídeo opaco.
- A página local `frontend/splash-preview.html` usa Three.js para separar, diretamente do PNG original, a camada base e duas mechas laterais sem alterar o rosto, a pose ou o enquadramento. Uma malha suave balança as pontas continuamente; amplitude e velocidade podem ser ajustadas, o ciclo de fade/progresso reinicia a cada 8 s e movimento reduzido mantém o balanço em menor amplitude. Essa deformação vale só para a página de prévia; a splash de produção toca o arquivo WebM local.
- Na inicialização, a janela é trazida para frente e fica acima das demais até a splash terminar; um limite de segurança de 30 segundos evita mantê-la no topo caso a interface falhe. Abrir uma segunda instância do mesmo canal também traz a janela para frente e reapresenta a splash. O comando Reiniciar na bandeja recarrega a UI sem reiniciar o processo durante `wails dev`, preservando o servidor Vite; no pacote continua relançando o aplicativo.
- O menu da bandeja do Windows oferece “Reiniciar”: no pacote instalado, encerra e relança o app após liberar o mutex; em `wails dev`, recarrega a UI dentro do processo atual para preservar o servidor Vite.
- O listener do menu da bandeja permanece ativo depois de `Reiniciar`, permitindo repetir a ação durante várias sessões de `wails dev` sem perder o item após o primeiro clique.
- A splash mantém fade-in e fade-out sincronizados entre vídeo e wordmark, barra fluida de 10 px com percentual e layout adaptável à largura e altura da janela. O progresso contabiliza vídeo, wordmark, `Initial()` e tempo; a tela fica visível por pelo menos 4 s e aguarda vídeo e inicialização antes de sair.
- A mascote de Mangás usa a arte chibi de leitura e a da Home usa a reação de piscadela; ambas têm fundo transparente e carregam imediatamente.
- As mascotes ficam no fim do conteúdo das páginas de Home e Mangás, alinhadas à direita e com espaço próprio no fluxo. Não ficam fixas à janela e não cobrem os cards durante a rolagem.
- O espaço final foi reduzido nas duas páginas para aproximar as mascotes das bordas inferior e direita, mantendo uma margem segura para não cortar a arte.
- A raiz do documento ocupa a janela sem rolagem própria; a rolagem vertical do app fica em `main`.
- A grade de gêneros aparece logo abaixo do banner e antes de “Continue lendo”, com tiles monocromáticos e relevo sutil; as linhas se equilibram para preencher a largura sem deixar um card isolado esticado. A sinopse dos cards da Home aparece com os dados locais enquanto a consulta complementar carrega.
- A grade de categorias mostra duas fileiras por padrão; “+ Ver mais” revela as restantes e “− Ver menos” recolhe a lista.
- Configurações agora tem uma seção “Found a bug?” com a mascote detetive: bugs e melhorias abrem GitHub Issues e dúvidas vão para Q&A em Discussions. Os links sociais continuam sozinhos no rodapé da sidebar.
- A seção “Found a bug?” agrupa texto e ações à esquerda e posiciona a mascote à direita, inclusive no layout responsivo.
- A mascote de feedback foi ampliada para ficar legível sem competir com as ações; o tamanho diminui em telas compactas.
- O catálogo de mangás ganhou a mascote lendo no canto inferior direito, com cabelo simplificado e tamanho responsivo.
- A mascote do catálogo agora é renderizada fora da área rolável para ficar fixa na janela durante a rolagem.
- A arte fixa da Home foi atualizada para a reação de piscadela, com cabelo simplificado e caveira alinhada ao centro do torso.
- Estados vazios agora oferecem acesso ao repositório GitHub e ao site oficial por ícones compactos, com tooltip e rótulos acessíveis.
- As artes da mascote em busca sem resultados e erros inesperados agora usam as versões de cabelo simplificado: a reação de dúvida tem mechas agrupadas e arredondadas, e erros recuperáveis reutilizam a detetive com lupa.
- A mascote aparece apenas em estados contextuais: busca sem resultados, lista vazia e erros inesperados/recuperáveis; a reação da busca e a arte com lupa usam as referências escolhidas.
- A mascote dos estados vazios foi ampliada para até 180 px, mantendo a proporção e a centralização.
- Na tela Downloads, “Abrir pasta” e “Atualizar biblioteca” agora aparecem como botões somente com ícones; nomes acessíveis e tooltips preservam a identificação das ações.
- Campos MyAnimeList Client ID/Client Secret removidos da tela do usuário; o Client ID é definido internamente, o backend mantém compatibilidade com segredo legado no cofre, e o fluxo MAL sem segredo segue pendente de cliente público para desktop ou intermediário seguro.
- Rich Presence do Discord agora usa um switch visual acessível estilo Apple; a configuração técnica do Developer Portal não aparece mais em Configurações.
- O executável Windows de distribuição agora é compilado pela CLI Wails na versão do projeto; assim, o ícone da marca, o manifesto e os metadados de versão são incorporados aos recursos PE do `.exe`, usados pela janela, barra de tarefas e atalho do instalador.
- Integrações AniList e MyAnimeList agora aparecem com os favicons oficiais e ações de conectar/desconectar dentro de Configurações e da tela Contas; falhas de OAuth ficam visíveis junto ao serviço.
- Discord agora tem vínculo de perfil via OAuth PKCE, cartão com símbolo oficial, ações de atualizar/desconectar e controle visual de Rich Presence; o painel diferencia presença pública do registro de episódios no AniList/MAL.
- A presença Discord acompanha título, temporada/episódio, pausa, tempo e seek conforme o estado do MPV; o Developer Portal precisa registrar o callback `http://127.0.0.1:9744/` e a arte `logo`. Autorização e presença contra conta/cliente reais seguem pendentes.
- O Client Secret opcional do MAL pode ser salvo/removido em campo de senha local sem ser devolvido ao frontend; a troca de token envia autenticação HTTP Basic conforme a documentação oficial.
- Sincronização automática só marca progresso depois do EOF natural ou de 80% da duração conhecida, evitando enviar como assistido quando o usuário fecha o episódio cedo. Antes de gravar, consulta a lista remota para não regredir progresso nem reabrir obra concluída; testes com servidores locais validam as duas APIs.
- A área de Mangás agora funciona como fluxo completo de catálogo, capítulos e leitor: busca sob demanda, retomada visual do progresso, filtro de idioma, ordenação/seleção/download, navegação entre capítulos, modos contínuo/paginado, direção RTL/LTR, retry quando o MangaDex@Home falha e crédito do grupo de tradução quando disponível. URLs temporárias continuam fora do histórico salvo.
- O campo global de pesquisa agora acompanha o contexto de mangás no catálogo, nos capítulos e no leitor: identifica a busca como “Buscar mangás...” e envia a consulta ao catálogo MangaDex; nas demais telas, permanece como busca de animes.
- O resolvedor de páginas do MangaDex aceita capítulos em que só a qualidade `data-saver` esteja listada e valida base HTTP(S), hash e páginas antes de criar a sessão do leitor.
- Corrigida a restauração de janelas posicionadas fora da tela, incluindo o sentinel `-32000,-32000` gravado ao minimizar no Windows. No Windows, fechar pelo X oculta o app na bandeja, cujo menu permite abrir, minimizar, ocultar e sair.

- A marca enviada substituiu os ícones anteriores. O lettering foi recortado com transparência e agora aparece na sidebar expandida e no carregamento; os ícones PNG/ICO de janela e pacote usam a versão quadrada.
- Configurações agora usa uma coluna com seções abertas e índice que acompanha a rolagem. Preferências são aplicadas imediatamente e salvas por fila serializada com debounce; falhas preservam as escolhas e oferecem retry. O resumo de integrações abre a tela Contas, switches são consistentes e acessíveis, e ações de manutenção exibem feedback próprio sem barra fixa global.
- A entrada de Mangás ganhou hierarquia de catálogo: busca em destaque sincronizada com o cabeçalho, retomada em grade sem rolagem horizontal, progresso por página quando conhecido, resultados com status/idiomas/sinopse e estados vazios com caminho de retorno.
- Descoberta de mangás agora usa banner de destaque, trilhos no padrão da Home, gêneros filtráveis e ranking/atividade de publicação do MangaDex. As prateleiras são carregadas em paralelo, cacheadas por 15 minutos e usam imagens sob demanda. “Em alta” reflete capítulos enviados recentemente; “Em publicação” substitui temporada porque o catálogo não fornece um calendário sazonal confiável para mangás.
- A tela de Mangás agora reutiliza o `spotlight`, a largura de conteúdo, os cabeçalhos, os cartões de pôster para retomada e os carrosséis da Home. A busca duplicada saiu do banner e permanece no cabeçalho contextual; o destaque gira no mesmo intervalo da Home e aceita indicadores e teclas de direção.
- As capas das prateleiras da Home agora revelam “Ver anime” ao passar o mouse ou navegar por teclado, seguindo o CTA visual dos pôsteres de mangá e preservando a ação existente do card.
- As capas das prateleiras de mangá agora abrem uma prévia com título e sinopse em hover/foco, usando os dados do catálogo sem consultas extras por card; os títulos das seções ficaram sem subtítulos explicativos.
- A mascote-base ganhou cabelo longo vermelho mais liso, saia preta sem detalhes vermelhos e uma versão mini superdeformed, com cabeça maior e corpo simplificado. O pacote de artes inclui miniatura de 256 px, seis vistas de pose/ângulo, uma pose adicional de piscada e dez reações; a integração nos cards de categorias continua pendente.
- Em janelas de 761 a 1050 px, a sidebar mantém 188 px e compacta o espaçamento dos itens para preservar rótulos como “Configurações”; antes, a regra de 145 px cortava os nomes das telas.
- Cards de busca agora identificam adaptações com ano e contagem de episódios (por exemplo, Hunter x Hunter 1999/62 e 2011/148). Os valores vêm dos metadados canônicos já consultados em lote e só são associados após uma correspondência de identidade sem ambiguidade.
- O painel de prévia usa o AniList ID da obra quando confirmado, evitando exibir a contagem de episódios de outra adaptação com título parecido.
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
