# Avisos de dependências de terceiros

AnimeCaos distribui executáveis e bibliotecas de terceiros. Os termos abaixo
complementam a licença indicada nos próprios projetos; não alteram os direitos
dos autores. As licenças e relatórios incluídos no pacote ficam em
`licenses/`.

## Componentes de runtime

| Componente | Origem e versão do pacote | Licença aplicável | Material incluído |
|---|---|---|---|
| Firefox | Mozilla Firefox 157.0.1 x64; arquivos completos copiados para o pacote | MPL-2.0 e licenças de componentes listadas pelo Firefox | `licenses/media/firefox/MPL-2.0.txt`; inventário adicional no navegador em `about:license`; fonte e hashes em `licenses/SOURCE-OFFERS.md` |
| GeckoDriver | Mozilla geckodriver 0.37.1 x64 | MPL-2.0 | `licenses/media/geckodriver/MPL-2.0.txt`; fonte e hashes em `licenses/SOURCE-OFFERS.md` |
| mpv | Projeto mpv; versão e hash do binário registrados por release | GPL-2.0-or-later por padrão, salvo prova de build LGPL | `licenses/mpv-Copyright-v0.41.0.txt`, `licenses/mpv-LICENSE.GPL-v0.41.0.txt`, `licenses/mpv-LICENSE.LGPL-v0.41.0.txt` |
| FFmpeg / FFprobe | FFmpeg 9.0.2 essentials no Windows; build e configuração registrados por release | GPL-3.0-or-later para o build Windows com `--enable-gpl --enable-version3` | `licenses/ffmpeg-COPYING.GPLv3-n9.0.2.txt`, `licenses/ffmpeg-COPYING.LGPLv2.1-n9.0.2.txt` |
| WebView2 | Microsoft Edge WebView2 Fixed Version 155.0.4283.62 x64, arquivos completos junto ao app Windows | Termos de distribuição Microsoft | O app carrega `bin/webview2`; versão, origem oficial, assinatura e ciclo de atualização em `licenses/SOURCE-OFFERS.md` |

O app, suas dependências Go e as dependências npm de produção têm avisos
adicionais gerados no pipeline de release em `licenses/dependency-reports/`.
As builds de mídia são componentes separados do código AnimeCaos. A licença
aplicável ao conjunto não é declarada aqui como aconselhamento jurídico.

## Código-fonte correspondente

Cada release deve guardar a versão, configuração de build e SHA-256 dos
executáveis de mídia em `licenses/media/`. Os fontes e as instruções para obter
o fonte correspondente estão descritos em
[`licenses/SOURCE-OFFERS.md`](licenses/SOURCE-OFFERS.md). Se o pipeline não
conseguir registrar esses dados, a publicação deve falhar.

## Relatórios

- Dependências Go: `licenses/dependency-reports/go/` e
  `go-dependencies.csv`.
- Dependências npm de produção: `licenses/dependency-reports/frontend/`.
- Licenças e configuração de MPV/FFmpeg: `licenses/` e
  `licenses/media/`.
- Manifesto de hashes dos arquivos de cada pacote: `release-manifest.json`;
  checksums externos do pacote: `SHA256SUMS`.
