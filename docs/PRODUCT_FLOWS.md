# Fluxos e regras de produto

Estas regras descrevem o comportamento implementado. Para a hierarquia visual e estados por tela, consulte [Frontend](architecture/FRONTEND.md) e [System design](SYSTEM_DESIGN.md).

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
- Ao assistir, o backend sincroniza o progresso com a conta conectada se o título tiver ID reconhecido pelo tracker. Sem ID correspondente, sincronização não é válida.
- Tokens são locais e a interface recebe estado de perfil, não o segredo/token.

## Mangás

- Catálogo MangaDex escolhe texto em pt-BR quando disponível e tem fallback por idiomas em `manga.Service`.
- A tela pede capítulos por idioma, exibe o progresso salvo e reabre na página persistida.
- Download individual/em lote é registrado na mesma fila de atividade. Página remota tenta URL original e alternativa data-saver.
- Leitura offline usa o caminho do CBZ e não exige pedir lista de páginas à API.

## Interface e acessibilidade observadas

- Pesquisa no cabeçalho é compartilhada; `Ctrl+K` leva o foco ao campo.
- Sidebar desktop pode ser recolhida; em largura compacta a navegação fica no rodapé e o controle vai para o cabeçalho.
- Prévia de anime é montada fora do carrossel para não ser cortada por overflow; no layout compacto fica oculta, pois depende de hover.
- Capas podem falhar sem bloquear cards; mantém-se placeholder.
- Tema aceita `system`, `light`, `dark`; escala de UI é validada entre 1 e 1,5.
- O botão da hero continua iniciando a pesquisa pelo anime destacado; texto/ícone apresentados são “Assistir” com play.
