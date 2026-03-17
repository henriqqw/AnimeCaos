<div align="center">
  <img src="public/icon.png" alt="AnimeCaos Logo" width="128"/>

# AnimeCaos

**App de streaming desktop minimalista, sem anúnciosm, rápido e autônomo para animes.**

Centralize sua experiência de assistir anime em uma única aplicação, sem anúncios intrusivos e com busca inteligente entre múltiplas fontes.

🌐 Website: https://animecaos.vercel.app
🐦 Twitter: https://x.com/getanimecaos
📦 Repositório: https://github.com/henriqqw/animecaos  
🚀 Releases: https://github.com/henriqqw/animecaos/releases

![Version](https://img.shields.io/badge/version-v0.1.0-red.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

</div>

---

# 🖼 Preview

<div align="center">
  <img src="public/screenshot2.webp" alt="AnimeCaos - Tela do App" width="780"/>
  <br/>
  <em>Tela principal do app</em>
</div>

<br/>

<div align="center">
  <img src="public/screenshot4.webp" alt="AnimeCaos - Busca" width="780"/>
  <br/>
  <em>Busca com capas dinamicas</em>
</div>

<br/>

<div align="center">
  <img src="public/screenshot3.webp" alt="AnimeCaos - Detalhes" width="780"/>
  <br/>
  <em>Detalhes do anime e lista de episodios</em>
</div>

<br/>

<div align="center">
  <img src="public/screenshot.webp" alt="AnimeCaos - Player" width="680"/>
  <br/>
  <em>Player integrado</em>
</div>

---

# 📺 Sobre o Projeto

O **AnimeCaos** é uma aplicação desktop open source criada para **centralizar a experiência de assistir animes**.

Quem acompanha anime frequentemente precisa:

- navegar por vários sites diferentes  
- lidar com anúncios intrusivos  
- usar players inconsistentes  
- procurar episódios manualmente  

O AnimeCaos resolve esse problema funcionando como um **agregador inteligente de fontes públicas**, reunindo busca, reprodução e gerenciamento de episódios em uma única interface desktop.

A aplicação foi construída como um **experimento prático de automação web, scraping e agregação de dados**, explorando a integração de diversas bibliotecas Python utilizadas em projetos reais.

---

# ✨ Funcionalidades

### 🎬 Hub de Streaming Inteligente
Busca unificada em múltiplas fontes brasileiras simultaneamente.

### 🖼 Integração AniList
Busca automática de:

- capas oficiais
- sinopses
- metadados

utilizando a API **GraphQL do AniList**.

### ⭐ Watchlist & Histórico
Sistema local para:

- salvar animes favoritos
- acompanhar episódios assistidos
- continuar de onde parou

### ⏭ Auto-Play Next
Detecta o fim natural do episódio e avança automaticamente para o próximo.

### ⬇ Download Offline
Gerenciador de downloads integrado usando **yt-dlp**, com logs de progresso.

### 💨 Executável Standalone
Scripts de build permitem gerar um executável completo que já inclui dependências necessárias.

---

# 🧠 Tecnologias Utilizadas

O projeto foi desenvolvido em **Python** e integra várias bibliotecas populares do ecossistema.

| Tecnologia | Função |
|---|---|
| **PySide6** | Interface gráfica desktop |
| **Selenium** | Automação de navegação para páginas dinâmicas |
| **Requests + BeautifulSoup** | Coleta e parsing de HTML |
| **FuzzyWuzzy + Levenshtein** | Busca aproximada (fuzzy search) |
| **yt-dlp** | Extração e resolução de streams de vídeo |
| **mpv** | Player de vídeo externo |
| **PyInstaller** | Empacotamento do executável |

---

# 🔎 O que o projeto explora

Este projeto também funciona como um **laboratório prático para experimentar**:

- automação de navegação web  
- scraping de conteúdo dinâmico  
- agregação de múltiplas fontes  
- fuzzy matching para busca aproximada  
- integração entre bibliotecas Python  
- distribuição de aplicações desktop  

---

# 🛠 Pré-requisitos

Para rodar a partir do código fonte:

- **Python 3.10+**
- **Mozilla Firefox**
- **mpv**
- **yt-dlp**

Firefox é utilizado pelos scrapers Selenium para lidar com páginas protegidas por **Cloudflare**.

---

# 📦 Instalação (Source)

```bash
git clone https://github.com/henriqqw/anicaos.git
cd anicaos

python -m venv venv
