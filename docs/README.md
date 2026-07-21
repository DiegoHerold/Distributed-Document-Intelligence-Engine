# Documentacao do Eixo

Este diretorio organiza o contexto, a arquitetura, as decisoes, o roadmap e os documentos historicos do Eixo.

## Ordem recomendada de leitura

1. [Contexto mestre](context/master-context.md)
2. [Arquitetura](architecture/overview.md)
3. [Kernel v0](architecture/kernel-v0.md)
4. [Ingestao e identidade de conteudo](architecture/ingestion-and-content-identity.md)
5. [Storage local e ciclo de vida documental](architecture/local-storage-and-document-lifecycle.md)
6. [Jobs locais persistentes](architecture/persistent-local-jobs.md)
7. [Seguranca de ingestao](architecture/ingestion-security.md)
8. [Limites de ingestao](specifications/ingestion-limits.md)
9. [Erros de seguranca](specifications/security-errors.md)
10. [Contratos e provider nativo de PDF](architecture/pdf-provider-contracts.md)
11. [PDF Technical Inspector](architecture/pdf-technical-inspector.md)
12. [Geometria canonica](architecture/canonical-geometry.md)
13. [Bloco 3 - Decomposicao nativa e cena visual de PDF](roadmap/block-3-native-pdf-scene.md)
14. [Roadmap](roadmap/README.md)
15. [Indice oficial de fases](roadmap/phases/README.md)
16. [Decisoes arquiteturais](decisions/README.md)
17. [Guia para agentes](../AGENTS.md)
18. [Uso como biblioteca Python](guides/using-as-library.md)
19. [Uso da API REST](guides/using-the-api.md)
20. [Uso da CLI](guides/cli.md)
21. [Manuseio seguro de arquivos](guides/safe-file-handling.md)
22. [Testes de paridade](testing/parity-tests.md)
23. [Arquivo historico](archive/README.md), quando for necessario auditar a origem das decisoes

## Estrutura

```text
docs/
|-- README.md
|-- context/
|-- architecture/
|   |-- diagrams/
|   |-- canonical-geometry.md
|   |-- ingestion-security.md
|   |-- pdf-technical-inspector.md
|   |-- pdf-provider-contracts.md
|   `-- persistent-local-jobs.md
|-- decisions/
|-- specifications/
|-- roadmap/
|   |-- block-3-native-pdf-scene.md
|   `-- phases/
|-- guides/
|-- testing/
|-- research/
`-- archive/
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
