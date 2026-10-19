# Instruções de trabalho do AnimeCaos

Este arquivo orienta futuras sessões de desenvolvimento neste repositório.

## Antes de alterar o projeto

- Leia `docs/README.md` e a documentação da área que será modificada.
- Confira a implementação atual antes de confiar em descrições, screenshots ou notas antigas. O código é a referência para o comportamento vigente.
- Não transforme uma hipótese em fato. Quando não houver evidência no código, nos testes ou numa validação registrada, descreva como pendente ou não verificado.
- Mantenha credenciais, tokens, cookies e URLs temporárias fora do código e da documentação. IDs públicos de clientes não são segredos, mas devem ter configuração e contexto documentados.
- O código Python em `Legacy/` é histórico e não deve entrar no runtime, nos scripts Go de distribuição ou em novos caminhos de execução.

## Ao concluir uma mudança

Atualize a documentação junto com o código. No mínimo:

1. Registre o comportamento e as regras afetadas em `docs/architecture/` ou `docs/PRODUCT_FLOWS.md`.
2. Atualize `docs/CODE_MAP.md` se arquivos, telas, métodos ou scripts forem adicionados, removidos ou mudarem de responsabilidade.
3. Atualize `docs/TESTING.md` e `docs/GO_MIGRATION_MATRIX.md` quando cobertura ou paridade mudar.
4. Atualize `CHANGELOG.md` para mudanças perceptíveis ou decisões relevantes.
5. Registre riscos confirmados em `docs/CODE_REVIEW.md`; remova ou reclassifique itens que deixaram de ser verdade.

Escreva em português claro e direto, com o vocabulário normal de documentação de engenharia. Evite texto promocional, conclusões genéricas e frases que pareçam preenchimento. Use tabelas quando ajudarem a localizar informação; prefira explicar o motivo e o fluxo em prosa curta.

## Validação

- Interface: `cd frontend; npm exec -- tsc --noEmit; npm test -- --run`.
- Go: `go test ./...` e, quando CGO estiver disponível, `go test -race ./...`.
- Não execute build, empacotamento ou instalador sem solicitação explícita. `go test`, checagem de tipos e testes de interface não são builds do produto.
- Documente exatamente os comandos executados e seus resultados; não copie resultados antigos como se fossem atuais.

## Fonte de verdade e manutenção

- Índice da documentação: `docs/README.md`.
- Visão da arquitetura e mapa de arquivos: `docs/architecture/OVERVIEW.md` e `docs/CODE_MAP.md`.
- Interfaces Wails: código Go exportado em `internal/app/service.go`, `main.go` e tipos em `internal/domain/models.go`; a lista do frontend fica em `docs/architecture/FRONTEND.md`.
- Endpoints externos: código dos adaptadores e `docs/architecture/NETWORK_AND_PROVIDERS.md`.
- Este arquivo não substitui uma revisão do código. Atualize instruções e documentos se a estrutura mudar.
