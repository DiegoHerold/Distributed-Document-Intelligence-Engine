# Documentacao do Eixo

Este diretorio organiza o contexto, a arquitetura, as decisoes, o roadmap e os documentos historicos do Eixo.

## Ordem recomendada de leitura

1. [Contexto mestre](context/master-context.md)
2. [Arquitetura](architecture/overview.md)
3. [Kernel v0](architecture/kernel-v0.md)
4. [Roadmap](roadmap/README.md)
5. [Indice oficial de fases](roadmap/phases/README.md)
6. [Decisoes arquiteturais](decisions/README.md)
7. [Guia para agentes](../AGENTS.md)
8. [Uso como biblioteca Python](guides/using-as-library.md)
9. [Uso da API REST](guides/using-the-api.md)
10. [Uso da CLI](guides/cli.md)
11. [Testes de paridade](testing/parity-tests.md)
12. [Arquivo historico](archive/README.md), quando for necessario auditar a origem das decisoes

## Estrutura

```text
docs/
├── README.md
├── context/
├── architecture/
│   └── diagrams/
├── decisions/
├── specifications/
├── roadmap/
│   └── phases/
├── guides/
├── testing/
├── research/
└── archive/
```

## Fontes consolidadas

- `context/master-context.md` consolida a visao principal do antigo contexto mestre.
- `roadmap/README.md` e `roadmap/phases/README.md` consolidam o roadmap de implementacao mais recente.
- `architecture/overview.md` e `architecture/diagrams/processing-flow.mmd` consolidam a arquitetura e o fluxo operacional.
- `decisions/` registra as primeiras ADRs derivadas das decisoes ja estabelecidas.

## Contradicoes registradas

- O documento `# Fases revisadas - Motor de Inteli.txt` chama "Bloco 0" de contratos, corpus e criterios de qualidade.
- O documento `# Roadmap de implementacao do Eixo.txt`, mais recente, chama "Bloco 0" de organizacao e governanca do projeto.
- Para esta organizacao, o roadmap mais recente prevalece: contratos e corpus ficam como trabalho tecnico do Bloco 1, especialmente a partir das fases 1.2 e 1.3.
