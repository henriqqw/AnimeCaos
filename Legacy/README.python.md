# Código legado Python

Esta pasta preserva a aplicação Python anterior enquanto a auditoria de paridade segue aberta. Ela não faz parte do runtime nem do empacotamento Go.

O arquivo preserva 83 módulos Python do aplicativo e 56 arquivos `test_*.py` em `tests/` (além de `conftest.py`).

- `animecaos/`: módulos do aplicativo anterior.
- `tests/`: suíte Python anterior.
- `venv/`: ambiente Python local antigo, grande, ignorado pelo Git e preso aos caminhos absolutos de onde foi criado. Não é necessário para a versão Go; recrie um ambiente se voltar a rodar o legado.
- `main.py`, configurações de PyInstaller e arquivos de dependências ficam na raiz do arquivo.
- `deploy/`: scripts, manifests, instaladores e recursos de distribuição Python.
- `.github/workflows/`: workflow de release Python arquivado.
- `public/` e `assets/`: capturas, ícones e logos antigos que não são usados pela interface Go. `public/icon.png` preserva o mesmo arquivo de marca usado pelo pacote Go.
- `README.python.md`: guia do arquivo legado.
- `CHANGELOG.python.md`: histórico da aplicação Python anterior.

Os caminhos de dados do usuário não foram movidos. O importador Go ainda consulta os diretórios antigos de configuração e preserva backups durante a migração para SQLite.

Não execute os scripts arquivados para desenvolver ou distribuir a versão Go. A auditoria dos módulos e testes Python continua registrada em `../docs/GO_MIGRATION_MATRIX.md`.
