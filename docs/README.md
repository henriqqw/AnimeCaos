# Documentação do AnimeCaos

Este diretório descreve o aplicativo Go/Wails que está na raiz do repositório. Os documentos se apoiam no código existente e nos testes; itens sem comprovação ficam identificados como pendentes.

## Por onde começar

| Se você quer entender… | Leia… |
|---|---|
| Como as peças se conectam | [Visão geral da arquitetura](architecture/OVERVIEW.md) |
| A responsabilidade de cada arquivo, tela ou script | [Mapa do código](CODE_MAP.md) |
| Métodos Wails e telas React | [Frontend e interface Wails](architecture/FRONTEND.md) |
| Contratos de chamadas do app e eventos | [API da aplicação](architecture/APP_API.md) |
| Serviços Go e regras que atravessam módulos | [Backend](architecture/BACKEND.md) e [regras de produto](PRODUCT_FLOWS.md) |
| Busca rápida, publicação em lote e orçamento de preflight | [Plano do pipeline de busca](architecture/SEARCH_PIPELINE_PLAN.md) |
| Fontes de anime, scraping e rede | [Rede e provedores](architecture/NETWORK_AND_PROVIDERS.md) |
| Como ampliar o catálogo e integrar novas fontes | [Expansão do catálogo](architecture/CATALOG_EXPANSION.md) |
| SQLite, cache e migração de instalações antigas | [Dados e migrações](architecture/DATA_AND_MIGRATIONS.md) |
| AniList, MyAnimeList, MangaDex, Discord e atualizador | [Integrações externas](architecture/INTEGRATIONS.md) |
| Testar uma alteração ou entender o que ainda falta | [Testes](TESTING.md) e [matriz de migração](GO_MIGRATION_MATRIX.md) |
| Executar ou distribuir localmente | [Desenvolvimento e operação](OPERATIONS.md) e [distribuição](DISTRIBUTION.md) |
| Identidade visual, componentes e comportamento responsivo | [System design](SYSTEM_DESIGN.md) |
| Problemas conhecidos e revisão técnica | [Code review](CODE_REVIEW.md) |

## Estado descrito

O estado documentado foi conferido em **18/10/2026**. Uma rodada live de busca e reprodução MPV para dez títulos teve nove reproduções com áudio/vídeo e seek. A busca `hunter` aceita títulos relacionados e, naquela consulta, publicou dez cards cujo E1 passou no preflight; a qualidade não foi identificada. A consulta sazonal `Tensei Shitara Ken Deshita 2nd Season` retorna um card agrupado em quatro fontes, com T2 E1 validado até 1080p; o MPV decodificou AV1/AAC em 1920×1080 e avançou após seek. Na busca ampla `Tensei Shitara`, sete grupos reproduzíveis incluíram um único card Dai Nana Ouji com três fontes; o batching de identidade reduziu o tempo do pacote de 12,44 s para 8,29 s em execuções frias isoladas. A busca publica resultados em lote, com prazos globais e caches curtos de catálogo e identidade AniList, mantendo o preflight por temporada; os detalhes estão em [Pipeline de busca](architecture/SEARCH_PIPELINE_PLAN.md). A auditoria live de anúncios nas quatro fontes restantes validou uma amostra da Otakulogia e, em consulta separada, Naruto Shippuden E1 da SushiAnimes. No Hunter x Hunter E1, AnimeFire retornou HLS 404, AnimesOnlineCC não obteve rendition Blogger e a Sushi oscilou entre validar mídia e não retornar o título na repetição. O navegador de scraping bloqueia hosts conhecidos de anúncios/rastreadores e não segue redirecionamentos conhecidos para esses hosts. A revalidação Selenium/Firefox do embed Anidrive identificou um clipe sem áudio, que FFprobe rejeita. Os resultados e limites estão em [Testes](TESTING.md); as rodadas não certificaram reprodução integral de episódios nem um executável empacotado.

Na rodada por provedor mais recente, o MPV confirmou SushiAnimes (Hunter x Hunter 1999 E1), AnimesOnlineCC (Naruto Shippuden E1 e Hunter x Hunter 2011 E2) e Otakulogia (Hunter x Hunter 2011 E1), com H.264/AAC, dimensões, avanço e seek. A página AnimesOnlineCC de Hunter E1 ainda não fornece rendition; a busca agregada aprovou E1 pela Otakulogia. Uma consulta literal `Hunter x Hunter 2011` passou a usar expansão segura do ano e retornou a edição certa sem misturar a de 1999. AnimeFire segue fora da validação positiva desta rodada por instabilidade/404 do servidor remoto.

Quando uma alteração mudar o comportamento, atualize o capítulo correspondente e o [mapa do código](CODE_MAP.md) no mesmo conjunto de mudanças. Leia as [instruções do projeto](../AGENTS.md) antes de começar.
