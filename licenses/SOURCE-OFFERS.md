# Fontes e instruções de origem das dependências de mídia

Este arquivo define o material que deve acompanhar uma release que distribua
MPV, FFmpeg ou FFprobe. Não substituir os registros versionados por links
genéricos para a versão mais recente.

## Firefox e GeckoDriver

- Firefox 157.0.1 x64 é distribuído com o app para executar embeds com JavaScript.
  Windows usa o MSI oficial, SHA-512
  `ac630cbb2d0d726c827464b38df1bb030161cb97449820ac40e0f443bb05cbba5eb942149d561b0b6dfdae142c7b7c29cf3d09a8c1b55f713c391e4ff386a7dd`.
  Linux usa o tar.xz oficial, SHA-512
  `ebec5e5c91a7c954a0f276928748bb4249e2b44bccdcfe6c7d7b4ed9c64ca6891a56cc8a016546bfbf1ca537dfe6084dba8f2746037c62fae0acc13a542421f3`.
  O manifesto oficial fica em <https://archive.mozilla.org/pub/firefox/releases/157.0.1/SHA512SUMS>.
- GeckoDriver 0.37.1 é distribuído com o app para controlar a instância Firefox.
  Os downloads vêm de <https://github.com/mozilla/geckodriver/releases/tag/v0.37.1>.
  Windows x64 tem SHA-256
  `dfed9315abe8d2fbc1b6161a2ee8002452e79cf05ee92fdc653a4e26bc35edd8`; Linux x64 tem
  SHA-256 `e815130ea95983e162ae91843b48d3a3ce991735635fce83a647afde21e09f7e`.
  Os hashes são conferidos contra os digests dos ativos na API oficial de releases GitHub.
- Os scripts `deploy/go/download-browser-runtime.ps1` e
  `deploy/go/download-browser-runtime-linux.sh` validam os hashes antes de extrair
  os executáveis. Os arquivos de licença MPL 2.0 estão em
  `licenses/media/firefox/` e `licenses/media/geckodriver/`; o Firefox também
  expõe o inventário de licenças de bibliotecas e componentes em `about:license`.
- Fontes correspondentes: <https://hg.mozilla.org/mozilla-central/> (Firefox,
  release 157.0.1) e <https://github.com/mozilla/geckodriver/tree/v0.37.1>.

## Microsoft Edge WebView2 no Windows

- WebView2 Fixed Version 155.0.4283.62 x64 é redistribuído dentro de
  `bin/webview2` a partir do CAB oficial
  <https://msedge.sf.dl.delivery.mp.microsoft.com/filestreamingservice/files/232cf50b-3980-4531-afbb-779f446d7de1/Microsoft.WebView2.FixedVersionRuntime.155.0.4283.62.x64.cab>.
  A página oficial lista versões fixas e arquiteturas em
  <https://developer.microsoft.com/en-us/microsoft-edge/webview2/>.
- O pipeline confirma o ProductVersion e Authenticode de `msedgewebview2.exe`
  como Microsoft antes e depois de copiar o runtime. O manifesto por release
  registra SHA-256 e tamanho de todos os arquivos extraídos.
- A Microsoft documenta o uso de Fixed Version com `WebviewBrowserPath` no
  Wails e requer a cópia completa dos binários. A versão fixa não recebe
  atualizações automáticas; o projeto precisa avançar a versão e repetir a
  validação em cada ciclo de release. A distribuição deve respeitar os termos
  Microsoft incluídos no runtime e a política de suporte do fornecedor.

## MPV para Windows

- Projeto e código-fonte: <https://github.com/mpv-player/mpv>.
- Builds Windows são redistribuições de terceiros; a página do projeto lista
  explicitamente essa condição e as fontes dos builds:
  <https://mpv.io/installation/>.
- O pacote Windows do pipeline é `mpvio.install` 0.41.0. A verificação do
  pacote identifica `mpv-0.41.0-x86_64.7z` em SourceForge e o SHA-256
  `EF86FDE0959D789D77A3AD7C3C2DCA51C6999695363F493A6154F2C518634C0F`.
  `VERIFICATION.txt`, `LICENSE.txt` e `LICENSE.mpv-install.txt` do pacote são
  copiados para `licenses/media/mpv/` em cada release.
- O pipeline registra o pacote de origem, saída de `mpv --version`, hash do
  executável e arquivos auxiliares copiados. A versão indicada no número do
  pacote, sozinha, não identifica necessariamente o commit compilado.
- A release só é publicável quando o commit-fonte correspondente ao binário e
  a receita/configuração do build estiverem preservados em
  `licenses/media/` ou como ativos associados à release. Não inferir um commit
  somente pelo número `0.41.0`.
- A distribuição padrão do mpv é GPL-2.0-or-later; o aviso de copyright e os
  textos GPL/LGPL correspondentes estão em `licenses/`.

## FFmpeg e FFprobe

- Projeto e fonte FFmpeg 9.0.2: <https://git.ffmpeg.org/ffmpeg.git>, tag
  `n9.0.2`.
- Pacote Windows essentials usado pelo pipeline: Chocolatey `ffmpeg` 9.0.2,
  cuja verificação identifica a origem Gyan e o SHA-256 do arquivo original.
  O workflow copia `LICENSE.txt` e `VERIFICATION.txt` do pacote instalado para
  `licenses/media/`.
- No pacote Chocolatey 9.0.2 verificado nesta revisão, o SHA-256 do arquivo
  original `ffmpeg-release-essentials.7z` é
  `4705843CCAAF54257C16AD90F3E952ECE33C17DF964ECF7BFDBB0F49C7171077`.
- O build observado declara `--enable-gpl --enable-version3`; `ffmpeg -L`
  confirma GPLv3-or-later. A cópia da licença GPLv3 está em `licenses/`.
- Para cada release, preservar a configuração completa de `ffmpeg -version`,
  hashes de FFmpeg/FFprobe e o SHA-256 do pacote original. Se o pacote usar
  patches diferentes do tag upstream, preservar também esses patches/fontes.

## Compilador do instalador

Inno Setup é ferramenta de build e não é incluído no AnimeCaos. O pipeline usa
uma versão fixada do compilador; seus termos e distribuição pertencem ao
projeto Inno Setup.

## Critério de publicação

O pacote de release precisa conter o aviso geral, textos de licença aplicáveis,
relatórios de dependências Go/npm, inventário de executáveis/hashes e dados
suficientes para obter o fonte correspondente às builds GPL. Qualquer lacuna
nesse inventário bloqueia a publicação automática.
