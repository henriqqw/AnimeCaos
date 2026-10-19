# Ampliação do catálogo de fontes

Este capítulo descreve como integrar um provedor público ao catálogo Go sem misturar títulos ou episódios e sem expor no app opções que não possam ser reproduzidas.

## Contrato do provedor

Um adaptador em `internal/providers` implementa `domain.AnimeProvider`:

- `Name()` devolve um identificador estável, usado para selecionar a variante do provedor.
- `Search(ctx, query, page)` consulta uma página e devolve registros com IDs próprios da fonte.
- `Details(ctx, anime)` devolve temporadas e episódios, preservando IDs e URLs de origem.
- `Resolve(ctx, episode)` converte um episódio em uma ou mais streams, incluindo cabeçalhos de origem necessários quando aplicável.

IDs locais são identificados por `provider:id`. Um título semelhante é candidato à busca, mas não basta para unir adaptações. A identidade canônica só é compartilhada quando o catálogo confirma metadados não ambíguos. Temporada e número de episódio devem vir de marcadores explícitos; a posição da lista nunca serve como identidade.

## Registro e fluxo

1. Implemente o adaptador junto de fixtures pequenas para busca, detalhes e resolução, cobrindo markup alternativo, erros HTTP, timeout e cancelamento relevantes.
2. Registre-o na composição `internal/app.New` ao construir `providers.Catalog`. O nome deve ser único e aparecer no diagnóstico/mapa de fontes se esse contrato mudar.
3. Faça `Search` e `Details` retornar metadados suficientes para que `providers.Catalog` agrupe somente variantes da mesma obra e associe os mesmos episódios com segurança.
4. Faça `Resolve` devolver streams sem cachear URLs assinadas. HTTP estático é o caminho rápido; use Chromium ou Selenium/Firefox somente quando a página realmente criar o player por JavaScript.
5. Limite a extração ao contêiner do player. Não transforme anúncios, iframes externos ou páginas de verificação em candidatos. Desafios de segurança que persistem são falha fechada; a integração não automatiza sua evasão.
6. Passe os candidatos por `media.Validate`/`media.Best`, gateway e MPV. O preflight da busca só aprova um card depois de confirmar o episódio amostrado.

O app usa AnimeFire, AnimesOnlineCC, SushiAnimes e Otakulogia na composição atual. O construtor e a interface do catálogo ficam em `internal/app/service.go` e `internal/domain/models.go`.

## Critérios de teste

- Os testes unitários usam `httptest` e fixtures locais; não dependem da disponibilidade de sites externos.
- Um teste live de catálogo pode confirmar que o adaptador encontra título, detalhes e um candidato de mídia, mas não prova que MPV decodifica o conteúdo.
- `TestLiveProviderPlayerMPVE2E` é a validação de reprodução: busca, detalhes, resolução, gateway, codecs/faixas, dimensões, avanço da posição e seek.
- Registre a data, a amostra de episódio, a fonte e os metadados observados em `docs/TESTING.md`. Um resultado live é evidência daquela amostra, não garantia de catálogo completo.
- Atualize `docs/architecture/NETWORK_AND_PROVIDERS.md`, `docs/CODE_MAP.md`, `docs/GO_MIGRATION_MATRIX.md` e `CHANGELOG.md` junto com a implementação.

Os comandos e resultados live atuais estão em [Testes](../TESTING.md); regras do pipeline de identidade e preflight estão em [Rede e provedores](NETWORK_AND_PROVIDERS.md) e [Pipeline de busca](SEARCH_PIPELINE_PLAN.md).
