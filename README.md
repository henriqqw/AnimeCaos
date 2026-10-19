# AnimeCaos

Aplicativo desktop para descobrir, organizar e assistir anime e ler mangás. A aplicação atual usa Go, Wails 2, React e TypeScript. O código Python anterior foi preservado em [`Legacy/`](Legacy/README.python.md) como referência durante a conclusão da matriz de paridade.

## Estrutura

- `internal/`: domínio, catálogo, player, downloads, integrações e persistência em Go.
- `frontend/`: interface React/TypeScript e estilos responsivos.
- `cmd/`: CLI e empacotador Go.
- `deploy/go/`: recursos de distribuição do aplicativo Go.
- `docs/`: documentação de arquitetura, produto, telas, contratos, dados, rede, testes, revisão e distribuição. Comece pelo [índice da documentação](docs/README.md).
- `Legacy/`: aplicativo Python, testes e scripts antigos, preservados sem fazer parte da execução Go.

## Desenvolvimento

Requisitos: Go, Node.js/npm e dependências nativas do Wails 2/WebView2 ou GTK/WebKitGTK. MPV e FFmpeg são usados para reprodução e downloads de vídeo.

```powershell
cd frontend
npm ci
cd ..
wails dev
```

Para executar os testes de comportamento sem iniciar uma compilação do app:

```powershell
go test ./...
cd frontend
npm test -- --run
```

O build/empacotamento não faz parte desta etapa; consulte [`docs/DISTRIBUTION.md`](docs/DISTRIBUTION.md) antes de preparar uma distribuição.

## Documentação

- [Índice e guia de leitura](docs/README.md)
- [Visão geral da arquitetura](docs/architecture/OVERVIEW.md)
- [Mapa do código e das telas](docs/CODE_MAP.md)
- [Fluxos e regras de produto](docs/PRODUCT_FLOWS.md)
- [Backend](docs/architecture/BACKEND.md)
- [Frontend e interface Wails](docs/architecture/FRONTEND.md)
- [Dados e migrações](docs/architecture/DATA_AND_MIGRATIONS.md)
- [Rede e provedores](docs/architecture/NETWORK_AND_PROVIDERS.md)
- [Integrações](docs/architecture/INTEGRATIONS.md)
- [Desenvolvimento e operação](docs/OPERATIONS.md)
- [Testes e validação](docs/TESTING.md)
- [Revisão técnica](docs/CODE_REVIEW.md)
- [System design visual e UX](docs/SYSTEM_DESIGN.md)
- [Matriz de migração Go](docs/GO_MIGRATION_MATRIX.md)
- [Distribuição](docs/DISTRIBUTION.md)
