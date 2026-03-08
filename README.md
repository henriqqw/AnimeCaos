<div align="center">
  <img src="icon.png" alt="animecaos logo" width="128" />
  <h1>animecaos</h1>
  <p><em>Agregador de streaming desktop premium, minimalista e autônomo.</em></p>

  [![Version](https://img.shields.io/badge/version-v0.1.0-red.svg)](https://github.com/henriqqw/anicaos/releases)
  [![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
  [![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
</div>

---

O **animecaos** é uma plataforma desktop moderna focada em centralizar a experiência de assistir animes no Windows/Linux, removendo anúncios intrusivos e oferecendo uma interface limpa, rápida e imersiva. Construído com **PySide6**, ele integra metadados oficiais e ferramentas de reprodução consagradas (`mpv`) e download (`yt-dlp`).

## ✨ Funcionalidades Principais

*   **🎬 Hub de Streaming Inteligente**: Pesquisa unificada em múltiplas fontes brasileiras simultaneamente.
*   **🖼️ Integração AniList (GraphQL)**: Busca automática de capas originais e sinopses (com tradução PT-BR interna) de todos os títulos.
*   **⭐ Favoritos & Histórico**: Painel de Watchlist para salvar seus títulos preferidos e histórico local para continuar de onde parou.
*   **⏭️ Auto-Play Next**: Detector de fim de vídeo que avança automaticamente para o próximo episódio se o player for encerrado no fim natural.
*   **⬇️ Download Offline**: Gerenciador de downloads integrado em segundo plano com logs de progresso em tempo real.
*   **💨 Standalone Build**: Scripts prontos para gerar um executável Windows completo que já embuti todas as dependências binárias necessárias.

## 🛠 Pré-requisitos

- **Python 3.10+**
- **Mozilla Firefox** (Necessário para os scrapers Selenium bypassarem Cloudflare)
- **mpv** e **yt-dlp** instalados globalmente (caso não esteja usando o executável compilado)

## 📦 Instalação (Source)

```bash
git clone https://github.com/henriqqw/anicaos.git
cd anicaos
python -m venv venv

# Windows
.\venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
python main.py
```

## 🏗 Distribuição (Build Oficial)

Para criar uma versão instalável `Setup_Animecaos.exe` para outros usuários:

1.  Coloque o executável do `mpv.exe` dentro da pasta `bin/`.
2.  Rode o script de build:
    ```bash
    python build_release.py
    ```
    *Este script baixará automaticamente o yt-dlp e o geckodriver, e empacotará tudo usando PyInstaller.*
3.  (Opcional) Compile o instalador profissional usando o arquivo `setup.iss` no **Inno Setup**.

## 📂 Estrutura do Projeto

- `animecaos/core/`: Domínio, carregamento de plugins e resolução de caminhos (`sys._MEIPASS`).
- `animecaos/services/`: Serviços de API (AniList, Tradução, Watchlist, Histórico).
- `animecaos/plugins/`: Web Scrapers baseados em Selenium e Requests.
- `animecaos/ui/gui/`: Interface gráfica rica baseada em PySide6 e Workers assíncronos.
- `animecaos/player/`: Wrapper de comunicação bidirecional com o `mpv`.

---

> [!NOTE]
> Este projeto é apenas um agregador de links públicos. O conteúdo reproduzido é de total responsabilidade de seus respectivos proprietários originais e servidores externos.

<div align="center">
  Feito com ☕ por caosdev
</div>
