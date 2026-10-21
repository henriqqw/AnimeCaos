# Fluxos e regras de produto

Estas regras descrevem o comportamento implementado. Para a hierarquia visual e estados por tela, consulte [Frontend](architecture/FRONTEND.md) e [System design](SYSTEM_DESIGN.md).

## Janela e bandeja do Windows

- Ao iniciar, o app restaura a posição salva somente se a barra de título continuar visível em pelo menos um monitor conectado. Posições inválidas ou gravadas pelo Windows ao minimizar (`-32000,-32000`) são descartadas e a janela é centralizada.
- O botão X oculta a janela e mantém o processo ativo na bandeja. A ação `Sair` do menu encerra o processo e remove o ícone.
- Se o Windows não conseguir inicializar o ícone da bandeja, o botão X encerra o app para evitar deixá-lo invisível.
- O menu da bandeja oferece `Abrir AnimeCaos`, `Minimizar`, `Ocultar para bandeja`, `Reiniciar` e `Sair`. Ao abrir, a janela é mostrada e desminimizada. Em `wails dev`, `Reiniciar` recarrega a interface dentro do processo atual para reapresentar a splash sem encerrar o servidor Vite; o listener permanece ativo para aceitar reinícios consecutivos. Na build instalada, fecha o processo e o helper reabre o executável após liberar o mutex. Uma segunda instância do mesmo canal reativa a janela já existente; `wails dev` e a build instalada usam mutexes distintos para que um servidor Vite parado não capture a abertura da versão de produção.
- Na inicialização, a janela é trazida para frente e fica acima das demais enquanto a splash está visível; o frontend remove essa prioridade quando a animação termina. Um limite de segurança de 30 segundos evita manter a janela sempre no topo se a interface não conseguir concluir a splash. Abrir uma segunda instância do mesmo canal também traz a janela para frente e recarrega a interface para reapresentar a splash.
- Minimizar pelo controle nativo da janela continua minimizando para a barra de tarefas; a ação do menu da bandeja tem o mesmo comportamento. `Ocultar para bandeja` remove a janela da barra de tarefas sem encerrar o app.
- O menu de bandeja está implementado para Windows. Em Linux e macOS o app mantém o comportamento nativo de fechamento até existir um adaptador de bandeja específico para essas plataformas.

## Splash de inicialização

- A primeira tela combina a mascote à esquerda e a wordmark AnimeCaos à direita, sobre fundo preto. Usa somente o vídeo local da mascote, pré-carregado pelo documento de entrada; sem poster ou fallback PNG. Vídeo e logo iniciam juntos o fade de 560 ms quando o primeiro quadro do vídeo está decodificado e a wordmark carregou. Se o vídeo falhar, o app tenta uma nova carga e apresenta uma ação de retry, mantendo a logo oculta até o vídeo estar pronto. A logo e a mascote desaparecem em 600 ms. O rótulo “INICIANDO” permanece estático. A barra espessa mostra o percentual à direita e considera vídeo, wordmark, resposta de `Initial()` e tempo mínimo, avançando até 100% durante a saída. Não há escala, desfoque, faixas, zoom, respiração ou parallax. As transições continuam ativas mesmo quando o sistema pede movimento reduzido. O layout ajusta proporções e espaçamentos em janelas estreitas ou baixas.
- A abertura dura pelo menos 4 segundos no total: 3,4 s antes do início do fade-out e 600 ms de fade. A interface abaixo permanece sem interação até que esse tempo, o carregamento do vídeo/logo e a inicialização estejam concluídos.
- A janela nativa começa com o mesmo fundo da splash para evitar um flash de cor diferente.

## Atualização automática

- Builds instaladas no Windows e AppImage Linux verificam `/releases/latest` durante a splash. A consulta termina em até 8 s; sem rede ou release válida, a inicialização continua normalmente.
- Quando encontra uma versão mais nova, baixa o ZIP Windows ou AppImage correspondente, valida seu SHA-256 usando `SHA256SUMS` e aplica o pacote antes de liberar a interface. A barra da splash mostra o progresso do download. O helper substitui os arquivos e abre a nova versão; falha de verificação ou instalação libera a versão atual.
- Flatpak continua gerenciado pelo sistema. `wails dev` não busca nem instala releases. O fluxo manual de Configurações continua disponível.
- A release Windows `v2.0.0` antecede a aplicação Go/Wails, mas o atualizador Python legado consulta a mesma API e seleciona o ZIP Windows. Na primeira release 3.x, ele pede confirmação e copia o ZIP para a pasta existente; depois disso, o atualizador Go/Wails instala automaticamente as próximas versões 3.x. O atualizador legado não valida SHA-256; o atualizador Go/Wails valida o pacote antes da instalação. A edição Flatpak antiga não consegue instalar AppImage e precisa migrar manualmente.
- Ao retomar um vídeo baixado pelo histórico no Windows, caminhos longos e aliases 8.3 são reconhecidos pelo arquivo real (`os.SameFile`), para preservar o ponto de reprodução após a deduplicação do histórico local.

## Descobrir, pesquisar e abrir um anime

1. A home combina descoberta do AniList com histórico local. Cards de catálogo consultam resumo detalhado sob demanda.
2. Selecionar um destaque ou anime da home leva à pesquisa pelo título, conservando a referência canônica quando disponível.
3. O catálogo pesquisa aliases relevantes nas fontes registradas. Para consultas que terminam em uma temporada explícita, também tenta o título base. O preflight deve validar E1 daquela temporada antes de associar a variante ao resultado; um título base que só tenha E1 de outra temporada continua oculto.
4. A identidade canônica prefere títulos principais do AniList. Sinônimos só ajudam quando nenhum título principal corresponde e o sinônimo é único; um sinônimo ambíguo nunca transforma outro anime em resultado. Correspondências fuzzy fortes podem ser exibidas, mas não fundem identidades.
5. A busca mantém os candidatos fora da tela até concluir o preflight ou atingir o prazo de 12 s. Então devolve em um lote os cards que já passaram; candidatos que ainda não foram validados continuam ocultos. O frontend troca a grade de uma vez; consultas antigas são canceladas e suas respostas não substituem a busca atual.
6. O selo do poster informa `Até 1080p` ou `Qualidade não identificada`, com base no episódio 1. Ele aparece apenas na busca; home, histórico e biblioteca não exibem essa informação.

## Temporadas, idiomas e episódios

- Temporadas só são mostradas como fato quando a fonte/metadado fornece essa informação explicitamente.
- O identificador do episódio vem do provedor. O número humano é metadado separado; nunca substituir o ID por índice da lista.
- Um catálogo pode mostrar a mesma obra com cobertura de temporadas diferente. O app prefere o conjunto com mais temporadas explicitamente nomeadas; não combina listas de IDs diferentes.
- Áudio preferido vem da configuração; se não existir correspondência, o resolvedor usa uma alternativa disponível.
- Na validação do card, apenas o episódio 1 com número explícito é amostrado. Uma consulta com temporada explícita exige E1 daquela temporada; a cache de disponibilidade separa temporadas. Sem temporada na consulta, a temporada 1 explícita tem precedência; uma temporada ausente só é aceita quando há um único E1 não agrupado. Posição na lista nunca preenche identidade ausente.
- A busca verifica no máximo seis fontes simultaneamente e duas por provedor, com filas isoladas por provedor, prazo de 12 s para o lote e timeout de 12 s por fonte. Um prazo vencido mantém os cards já aprovados; fontes pendentes não são contadas nem entram no cache. Cancelar a busca cancela o preflight. Cache em memória guarda só o resumo: 2 min para resultado positivo e 20 s para negativo.
- A disponibilidade do primeiro episódio não garante episódios posteriores. Ao iniciar a reprodução, streams são obtidos novamente e validados; o áudio preferido vem primeiro e, dentro dele, altura e bitrate ordenam as fontes. HLS usa a variante acessível mais alta; arquivos diretos usam FFprobe para confirmar codecs e dimensões quando instalado. `ANIMECAOS_FFPROBE_PATH` configura o executável. Se FFprobe identifica um arquivo sem faixa de áudio, a fonte é descartada antes do MPV.
- Antes de avançar a posição no MPV, um erro ou timeout de início permite tentar a próxima candidata. Depois de haver avanço, a fonte não muda silenciosamente. A URL de mídia e seus cabeçalhos ficam apenas na resolução/gateway em memória, nunca no resumo de disponibilidade.
- A resolução entre variantes usa temporada/número explícitos; sem esse par, usa apenas título normalizado único, mesmo que os grupos de temporada sejam diferentes. Títulos repetidos e posição na lista não são usados para adivinhar.
- O scraping estático segue como caminho rápido. Quando uma página de player só é criada por JavaScript, o AnimesOnlineCC usa Firefox/GeckoDriver via Selenium se configurado e mantém Chromium como fallback. O navegador usa proxy local temporário para bloquear hosts conhecidos de anúncios/rastreadores e não clica em links nem resolve desafios de segurança. A extração prioriza contêineres de vídeo, filtra iframes de anúncios e rejeita intersticiais; uma verificação que continua ativa mantém a fonte indisponível. FFprobe descarta arquivos diretos sem áudio quando consegue inspecioná-los.
- O cliente HTTP, a validação de mídia e o gateway recusam redirecionamentos para hosts conhecidos de anúncios/rastreadores; o MPV não recebe a URL de destino desse redirecionamento. A lista é baseada em host e não altera URLs de CDNs comuns.
- O scraper AnimesOnlineCC decodifica entidades HTML e escapes comuns do `iframe.src`, resolve URLs relativas e rejeita esquemas diferentes de HTTP(S), seguindo o contrato do scraper Python legado.

## Reprodução e histórico

- O MPV é controlado por JSON IPC; o modo padrão do app é MPV, com opções `custom` e `system` previstas em configuração.
- O estado de player carrega identificador de sessão. Eventos de uma sessão antiga não podem substituir a seleção mais recente.
- Ao tocar mídia online, o app resolve stream com áudio/configuração atual. Mídia local abre sem depender do catálogo remoto.
- Histórico guarda anime, episódio, posição e timestamp. O evento de player atualiza a retomada durante a execução.
- Reprodução de arquivo associado a um download concluído usa a identidade original do anime/episódio. Registros offline antigos ligados ao mesmo arquivo são consolidados no histórico canônico, preservando a posição mais recente; Continuar retoma pelo arquivo local quando esse for o progresso salvo.
- Autoplay requer término natural (`EOF`) e opção habilitada. Parar/fechar o player não equivale a EOF.
- Fechar o player encerra a sessão e limpa os controles antigos da interface. Eventos atrasados de uma sessão encerrada não podem restaurar esses controles.
- Na importação antiga, índice sem ID atual recebe `needsResolve`; a UI permite procurar opções e não associa episódio por posição.

## Downloads

- Uma seleção de episódios cria trabalhos individuais, com duplicata identificada pela chave persistente da tarefa/arquivo.
- Simultaneidade aceita 1–5. Tarefas publicam progresso e estado por evento; a UI pode continuar em segundo plano.
- Cancelamento sinaliza o contexto e não libera o slot de concorrência antes de o worker terminar.
- Arquivo é baixado para temporário; só é publicado no caminho definitivo depois de verificação e finalização. Cancelamento/falha não deve aparecer como arquivo concluído.
- A biblioteca local lê arquivos já existentes e metadados, permitindo reprodução offline; excluir arquivo também remove metadado associado.
- Capítulos de mangá baixam como CBZ; erro em página impede publicação do capítulo incompleto.

## Minha Lista e contas

- Minha Lista usa a chave `provider:id`; ligar/desligar é persistido no bucket `watchlist`.
- AniList/MAL são opcionais. A reprodução continua mesmo quando a sincronização falha; erro de integração é relatado separadamente.
- A tela Contas conecta/desconecta AniList, MyAnimeList e Discord pelo navegador do sistema; os cartões apresentam ícones, estado e perfil conectado. Configurações mantém apenas um resumo de conexão e o atalho “Gerenciar contas”. O Discord solicita apenas `identify`; ele não sincroniza episódios assistidos. As credenciais OAuth do aplicativo MAL são internas ao AnimeCaos e não são solicitadas ao usuário. O Client ID vem da configuração da aplicação; um Client Secret legado no cofre local pode ser usado pelo backend, sem aparecer na interface.
- Após o MPV encerrar um episódio, a sincronização avança a lista se houve EOF natural ou se o vídeo chegou a pelo menos 80% da duração conhecida. Fechar antes disso não marca o episódio como assistido. A integração consulta primeiro o progresso remoto, não diminui a contagem nem reabre uma obra concluída. Apenas IDs AniList/MAL canônicos e correspondentes são aceitos; sem ID, o serviço externo não é alterado.
- A sincronização usa `SaveMediaListEntry` no AniList e `PATCH /anime/{id}/my_list_status` no MyAnimeList. A reprodução não espera a resposta dessas chamadas; erros aparecem como erro de integração.
- Tokens são locais e a interface recebe estado de perfil, não o segredo/token.
- A opção Discord Rich Presence publica AnimeCaos, título, temporada/episódio e tempo no perfil enquanto o Discord Desktop está aberto. Pausa congela o contador e parar limpa a atividade; a opção é independente do login de conta. O nome, ícone e asset `logo` precisam estar configurados no Developer Portal.

## Mangás

  - A página de catálogo começa com um banner de destaque da lista mais acompanhada. A seção “Categorias” fica logo abaixo do banner e antes de “Continue lendo”; mostra duas fileiras por padrão e revela as demais por “+ Ver mais”. Depois vêm as prateleiras “Top mangás”, atividade recente e séries em publicação. O banner e os cartões abrem a página da obra; não iniciam a leitura até que uma pessoa escolha capítulo.
  - “Top mangás” segue `followedCount`, “Em alta” segue o capítulo enviado mais recentemente e “Em publicação” vem do status `ongoing` do MangaDex. O catálogo não declara temporada para mangás; a interface não reaproveita a temporada de anime como se fosse calendário de publicação de uma obra.
  - Categorias são gêneros provenientes das tags oficiais do MangaDex. Selecionar uma aplica o filtro por ID, apresenta as obras retornadas e permite voltar à descoberta.
  - A estante “Continue lendo” usa carrossel horizontal ordenado pelo progresso mais recente. Cada item mostra obra, capítulo, página e, quando há contagem de páginas, uma barra de progresso; a ação retoma o ponto salvo. Durante uma busca, os resultados ficam antes da estante para manter a resposta perto do campo.
  - A busca não dispara consulta vazia. Os campos da página e do cabeçalho contextual mantêm a mesma consulta; enviar um título mostra carregamento, falha com nova tentativa, resultados com capa, status, idiomas e sinopse curta. Resultado vazio identifica a consulta e oferece retorno ao catálogo.
- Ao abrir uma obra, a tela apresenta capa, sinopse, status, idioma e capítulos, incluindo crédito do grupo de tradução quando fornecido pela API. É possível alternar idioma, ordenar capítulos, selecionar um conjunto para baixar e abrir um capítulo individual.
- O leitor abre páginas em sequência contínua por padrão e também oferece modo de página única, seletor de página, atalhos por teclado, direção RTL/LTR e botões de página/capítulo anterior e seguinte. O modo e a direção ficam salvos localmente.
- O progresso é salvo por obra, capítulo e página. Retomar uma leitura busca novamente as páginas no MangaDex; URLs temporárias não são persistidas.
- Falha ao buscar páginas sai do estado de carregamento, explica o problema e oferece nova tentativa para obter uma atribuição MangaDex@Home atualizada. Falha de uma imagem também mostra ação de recuperação.
- Catálogo MangaDex escolhe texto em pt-BR quando disponível e tem fallback por idiomas em `manga.Service`.
- A resposta de descoberta e os resultados por categoria usam cache local de 15 minutos (até seis horas como fallback). Se uma origem de catálogo falhar após parte das prateleiras carregar, a tela preserva as demais e exibe um aviso.
- O aplicativo mantém os créditos ao MangaDex e ao grupo de tradução quando fornecido. A política do MangaDex exige atender pedidos de remoção dos grupos e proíbe monetizar o cliente por anúncios/serviços pagos.
- Download individual/em lote é registrado na mesma fila de atividade. Cada imagem tenta qualidade original e alternativa data-saver; capítulos incompletos não são publicados. Leitura offline usa páginas do CBZ sem pedir lista de páginas à API.

## Interface e acessibilidade observadas

- Pesquisa no cabeçalho é compartilhada; `Ctrl+K` leva o foco ao campo.
- Sidebar desktop pode ser recolhida; em largura compacta a navegação fica no rodapé e o controle vai para o cabeçalho.
- Prévia de anime é montada fora do carrossel para não ser cortada por overflow; no layout compacto fica oculta, pois depende de hover.
- Capas podem falhar sem bloquear cards; mantém-se placeholder.
- Tema aceita `system`, `light`, `dark`; escala de UI é validada entre 1 e 1,5.
- Configurações apresenta Aparência, Reprodução, Downloads, Integrações, Manutenção e Feedback em seções abertas numa coluna. Um índice navegável acompanha a seção visível; controles relacionados usam duas colunas quando cabe e empilham em larguras menores. Tema, escala, player, autoplay, downloads e Discord Rich Presence atualizam o estado da interface imediatamente. O ícone de navegação da tela é uma engrenagem.
- Uma fila central com debounce de 350 ms serializa `SaveSettings` e mantém apenas o snapshot mais recente pendente. Se uma gravação falhar, a escolha visual é preservada e há ação para tentar novamente. Limpeza de cache e operações de atualização têm feedback próprio e não passam pelo autosave.
- Aparência oferece opções segmentadas Sistema/Claro/Escuro; autoplay, fechamento do painel e Rich Presence usam switches com semântica `role="switch"`, foco visível e movimento reduzido respeitado. O caminho customizado só aparece para player personalizado; o atraso do fechamento só aparece se a opção estiver ativa.
- O botão da hero continua iniciando a pesquisa pelo anime destacado; texto/ícone apresentados são “Assistir” com play.
- A seção “Found a bug?” em Configurações encaminha bugs e melhorias para o GitHub Issues e dúvidas para a categoria Q&A do Discussions. O painel mantém a mascote detetive à direita do texto e das ações.
- Downloads usa somente ícones para “Abrir pasta” e “Atualizar biblioteca”; cada botão preserva `aria-label` e tooltip.
- A base da sidebar exibe atalhos iconográficos para GitHub, site, Instagram e Twitter/X no desktop. Os estados vazios mantêm ícones para GitHub e site, sem chamada textual “Projeto e comunidade”. Os atalhos abrem no navegador do sistema.
