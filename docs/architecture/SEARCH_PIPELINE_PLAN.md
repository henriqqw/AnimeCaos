# Plano para uma busca rápida em lote

## Objetivo

Entregar, em uma única atualização visual, todos os resultados reproduzíveis da página consultada. Um card só entra no lote quando ao menos uma fonte passa pelo preflight do episódio 1. A busca deve continuar responsiva, cancelar trabalho obsoleto e nunca misturar remakes, filmes, temporadas ou especiais diferentes.

“Todos os resultados” significa todos os candidatos elegíveis encontrados na página atual dos provedores, dentro do orçamento de tempo e concorrência. O catálogo remoto pode ter outras páginas; elas continuam acessíveis por **Carregar mais**.

## Estado atual observado

`providers.Catalog.SearchExpanded` pesquisa a consulta e aliases AniList em paralelo, com até seis jobs simultâneos. A busca reconhece temporadas explícitas e consulta também o título base; cards encontrados pelo título base ficam provisórios até o preflight confirmar E1 da temporada pedida. Uma consulta terminada em ano, como `Hunter x Hunter 2011`, também consulta o título base, mas o filtro final conserva o ano e não mistura a adaptação de 1999. A descoberta tem limite de 15 s, o preflight 12 s e a operação completa 35 s. As verificações usam concorrência global 6, no máximo 2 trabalhos por provedor e timeout de 12 s por fonte. As filas são isoladas por provedor para uma fonte lenta não ocupar workers que poderiam validar as demais. Quando o prazo do preflight vence, o backend devolve em um único lote todos os cards já aprovados e omite os candidatos ainda sem confirmação; o frontend troca a grade uma vez. A resolução de identidade agrupa até oito consultas AniList em um único pedido GraphQL e mantém cache de título positivo por 30 min (24 h de validade máxima) e negativo por 2 min (30 min de validade máxima). Páginas de catálogo dos provedores ficam em cache por 30 s após resultado positivo e 10 s após resultado vazio; erros não entram no cache.

Na validação live de 18/10/2026, a consulta `Tensei Shitara Ken Deshita 2nd Season` retornou um único card após agrupar quatro provedores. O E1 da temporada 2 foi validado; a maior resolução observada foi 1080p. O MPV decodificou AV1/AAC em 1920×1080, avançou a posição e concluiu seek. As quatro fontes forneceram um E1 identificado como temporada 2, embora apenas AnimeFire tenha sido a fonte escolhida pelo resolvedor do MPV.

Na execução live de `hunter` em 18/10/2026, o método Search levou 15,147 s e retornou nove cards com E1 aprovado, entre eles Hunter x Hunter (1999), Hunter x Hunter (2011), City Hunter, Witch Hunter Robin e títulos relacionados. A qualidade ficou não identificada. O orçamento foi atingido e informado no aviso, mas os cards verificados foram preservados mesmo com candidatos ainda pendentes. Essa é uma amostra pontual e ainda supera o alvo inicial de 8 s para busca fria.

Na consulta live ampla `Tensei Shitara`, sete grupos passaram pelo E1. As três entradas de Dai Nana Ouji foram consolidadas em um card com três provedores, depois de confirmar a identidade AniList; outras obras da franquia e o filme continuaram em cards separados. A etapa de metadados passou a agrupar consultas GraphQL: uma execução anterior levou 12,44 s no pacote e a rodada atual levou 8,29 s no pacote, com 6,371 s dentro da chamada Search. Essa é uma amostra pontual, não uma medição p95. A consulta sazonal e o MPV foram repetidos após a mudança; T2 E1 continuou agrupando quatro provedores e tocando em 1080p.

Na validação live mais recente de `Hunter x Hunter 2011`, a consulta literal passou a encontrar o título agrupado e validou E1 pela Otakulogia. O MPV confirmou H.264/AAC, 1280×720, avanço e seek; a maior resolução aprovada no preflight foi 1080p. Uma amostra separada encontrou a versão 1999 pela Sushi. A busca levou 14,43 s e informou que algumas fontes excederam o orçamento, mas preservou os cards já aprovados. Os testes por provedor registram os casos de AnimesOnlineCC E1/E2 em [Testes](../TESTING.md).

## Arquitetura proposta

### 1. Controlador de consulta no frontend

- Aplicar debounce de 250 ms à digitação e manter busca imediata ao pressionar Enter.
- Associar cada consulta a um `operationId` crescente. Ao iniciar uma nova consulta, cancelar a anterior; ignorar eventos e respostas de IDs antigos.
- Manter um único estado de progresso, por exemplo `Buscando fontes · 4 de 7` e depois `Validando episódios · 9 de 18`.
- Não inserir cards provisórios. O spinner ocupa o lugar da lista até o backend publicar o lote elegível.

### 2. Coordenador de busca no backend

Dividir o trabalho em três etapas com prazo global e cancelamento comuns:

1. **Descoberta:** consultar os provedores em paralelo para a página pedida. Consultar aliases multilíngues com orçamento limitado, sem abrir Selenium nesta fase.
2. **Identidade e ranking:** normalizar caixa, acentos e pontuação; pontuar título exato, título principal, sequência contígua de palavras, alias único e erro de digitação, nessa ordem. Relação textual só inclui o candidato; não determina identidade.
3. **Preflight:** validar o E1 das fontes equivalentes em um pool limitado. Manter o card em memória até existir ao menos uma fonte válida; descartar o grupo se todas falharem ou o prazo expirar.

Proposta inicial de limites: seis verificações globais, duas por provedor e no máximo 8 s por fonte, com prazo total de 12 s para a página. Esses números devem ser confirmados por medições p50/p95 em uma amostra de buscas; o limite global deve impedir que um provedor lento segure a tela indefinidamente.

### 3. Identidade e deduplicação seguras

- Usar AniList ID ou outro ID canônico confirmado para agrupar versões publicadas por fontes diferentes.
- Preferir título principal do provedor; aceitar alias apenas quando for único e não contradisser uma adaptação com ano/formato explícito.
- Manter filmes, remakes, OVAs e séries como identidades separadas, mesmo que compartilhem palavras no título.
- Quando duas fontes exibirem o mesmo título, mas não houver identidade canônica única, não fundir os episódios. A próxima evolução deve buscar sinais independentes — ano, formato, número de episódios e títulos de episódio — antes de consolidar. Título igual, por si só, não prova que os players apontam para a mesma obra.
- Associar episódios somente por temporada/número explícitos ou por título único; nunca pela posição no array.

### 4. Preflight de mídia

- Usar HTTP e parser de manifesto como caminho rápido; reconhecer HLS pela resposta, mesmo quando a extensão engana.
- Tentar Selenium/Firefox somente quando o HTML não expuser o player. Limitar o navegador ao contexto e ao prazo da fonte; falha de challenge conta como indisponibilidade.
- Confirmar resposta de mídia e variante HLS. Para arquivo direto, usar FFprobe quando instalado; ausência de metadados não deve ser apresentada como resolução confirmada.
- Não abrir um processo MPV para cada card. MPV continua reservado à reprodução escolhida; testes E2E por provedor cobrem codecs, avanço e seek.
- Para provar disponibilidade, parar de procurar fontes assim que uma fonte válida for encontrada. A qualidade pode ser refinada por verificações restantes dentro do mesmo orçamento, sem atrasar a entrada do card no lote.

### 5. Publicação atômica do lote

Substituir a publicação de cada card por evento agregado:

- `search-progress`: etapa e contadores, sem dados de cards.
- `search-results`: `operationId`, lista final de cards aprovados, paginação e avisos. Emitir uma vez quando os candidatos terminarem ou o prazo global for atingido.
- Cada card inclui disponibilidade E1 e maior resolução confirmada no orçamento. Se o preflight passar sem identificar resolução, mostrar **Qualidade não identificada**.
- Um resultado que não passou no preflight nunca aparece. Quando o prazo vencer, publicar apenas os aprovados e avisar que fontes lentas podem ter deixado resultados de fora.
- Ordenar o lote por relevância textual e, em empate, por qualidade confirmada; manter a ordem estável entre atualizações.

O frontend substitui a lista de uma vez para a primeira página e anexa uma página completa ao carregar mais. A busca seguinte invalida o lote anterior antes de qualquer atualização tardia.

### 6. Cache e controle de carga

- Manter o cache atual de disponibilidade positiva por 2 min e negativa por 20 s; cache nunca contém URL assinada.
- Consultas AniList de título são agrupadas em um único GraphQL por até oito buscas e armazenadas no SQLite por prazo curto; esse cache contém somente metadados de identidade, não URLs de reprodução.
- Cache curto de resultados por consulta normalizada, provedor e página foi adicionado: 30 s para páginas com itens, 10 s para resultados vazios e sem cache de erros. A disponibilidade continua sendo validada separadamente e não cacheia URLs de stream.
- Coalescer consultas idênticas em andamento e cancelar consumidores quando nenhum ainda aguardar o resultado.
- Aplicar limite por host e cooldown curto após timeout/429 para reduzir chamadas repetidas à mesma fonte.
- Métricas locais por etapa: duração, candidatos encontrados, descartados por identidade, falhas por motivo, cache hit e resultados aprovados. Não registrar cookies ou URLs assinadas.

## Alvos de desempenho

Medir antes de ajustar e reportar p50/p95 em buscas quentes e frias. Alvos iniciais para a página consultada:

| Medida | Alvo inicial |
|---|---:|
| Resultado com cache de disponibilidade | p95 até 1,5 s |
| Busca fria com provedores responsivos | p95 até 8 s |
| Prazo total da página | até 12 s |
| Atualizações de cards por lote | 1 resposta final por página |
| Cards sem E1 aprovado | 0 |
| Mistura de adaptações ou episódios por posição | 0 |

Os alvos são hipóteses para o primeiro ciclo de otimização; a coleta de métricas dirá se precisam mudar.

## Plano de implementação

1. Instrumentar tempos atuais de descoberta, identidade e preflight; registrar p50/p95 sem conteúdo sensível.
2. `search-item` foi removido; a tela consome somente o resultado final e troca a lista em lote.
3. Foram adicionados limites de 15 s para descoberta, 12 s para preflight e 35 s para a operação, mantendo 6 verificações globais, 2 por provedor e 12 s por fonte. Filas separadas por provedor evitam que workers bloqueados pelo limite de uma fonte impeçam o início das outras.
4. O cancelamento por `operationId` continua ativo; o frontend ignora respostas antigas e mostra um único estado da busca.
5. Fixtures cobrem temporada solicitada, identidade provisória até preflight, variantes agrupadas, cache por temporada, publicação em lote, cancelamento e respostas antigas.
6. Consultas de identidade AniList foram agrupadas em GraphQL e receberam cache positivo/negativo; testes cobrem associação de respostas e reaproveitamento do cache.
7. Uma busca live ampla `Tensei Shitara` passou de 12,44 s para 8,33 s no tempo do comando em duas execuções frias; reuniu os três cards Dai Nana em um grupo. A busca sazonal ainda passou pelo preflight em quatro fontes e MPV. Ainda falta repetir medições p50/p95 em uma amostra maior e ampliar as amostras MPV por provedor.
8. O prazo do preflight preserva e publica em lote os cards que já passaram; candidatos incompletos continuam ocultos. O live `hunter` após a correção retornou nove cards em 15,147 s. A validação de falhas e do atraso controlado está coberta em `availability_test.go`.

## Critérios de aceite

- `hunter` inclui Hunter x Hunter 1999 e 2011, City Hunter e outros títulos relacionados que existam nos provedores e passem pelo E1; filmes só aparecem quando a fonte publicar um episódio resolvível e o preflight aprovar.
- Uma consulta com sufixo de temporada encontra provedores que indexam pelo título base, valida E1 da temporada pedida e agrupa as fontes somente depois desse preflight.
- Nenhum card é publicado antes do lote final nem permanece se todas as fontes falharem.
- A mesma obra em fontes diferentes ocupa um card com variantes quando a identidade canônica é única; remakes e títulos ambíguos continuam separados.
- Uma nova consulta cancela a antiga e nenhuma resposta atrasada altera os resultados visíveis.
- Os alvos de tempo são verificados em testes com atrasos controlados e em amostras live. O MPV confirma codecs, avanço e seek para cada adaptador certificado.
