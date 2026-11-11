# Fixtures AnimesFHD

Amostras da API pública fornecidas pelo contribuidor em 11/11/2026. Os seis JSON
foram copiados sem modificar o conteúdo, removendo somente o BOM UTF-8 quando
presente. Não contêm credenciais nem destinos temporários de redirecionamento;
as fontes de mídia usam os resolvedores públicos `/api/v/...`.

| Arquivo | Operação |
|---|---|
| `busca-frieren.json` | Busca de Frieren, uma obra com áudios legendado/dublado |
| `populares.json` | Lista popular, cinco resultados com próxima página |
| `serie-1709160706373932.json` | Série com seis episódios e versão explícita |
| `episodio-22882.json` | Fonte nativa `s6`, HLS no parâmetro `playlist` |
| `serie-filme-2110072639862535.json` | Filme com um episódio; `seo.format=movie` |
| `episodio-filme-1049086484300956.json` | Fonte nativa `s4` com HLS e legenda externa |

As respostas sintéticas em `animesfhd_test.go` exercitam casos que estas amostras
não incluem. As fixtures não atestam disponibilidade atual nem reprodução.
