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
13. [PDF Object Model](architecture/pdf-object-model.md)
14. [Catalogo de recursos PDF](specifications/pdf-resource-catalog.md)
15. [Ordem de pintura PDF](specifications/pdf-paint-order.md)
16. [Tipografia PDF](architecture/pdf-typography.md)
17. [Modelo textual nativo PDF](architecture/pdf-native-text-model.md)
18. [Catalogo de fontes PDF](specifications/pdf-font-catalog.md)
19. [Modelo de glifos PDF](specifications/pdf-glyph-model.md)
20. [Ordem textual PDF](specifications/pdf-text-order.md)
21. [Capacidades do provider PDF](providers/pdf-provider-capabilities.md)
22. [Capacidades textuais do provider PDF](providers/pdf-text-capabilities.md)
23. [Bloco 3 - Decomposicao nativa e cena visual de PDF](roadmap/block-3-native-pdf-scene.md)
24. [Roadmap](roadmap/README.md)
25. [Indice oficial de fases](roadmap/phases/README.md)
26. [Decisoes arquiteturais](decisions/README.md)
27. [Guia para agentes](../AGENTS.md)
28. [Uso como biblioteca Python](guides/using-as-library.md)
29. [Uso da API REST](guides/using-the-api.md)
30. [Uso da CLI](guides/cli.md)
31. [Manuseio seguro de arquivos](guides/safe-file-handling.md)
32. [Testes de paridade](testing/parity-tests.md)
33. [Arquivo historico](archive/README.md), quando for necessario auditar a origem das decisoes

## Estrutura

```text
docs/
|-- README.md
|-- context/
|-- architecture/
|   |-- diagrams/
|   |-- canonical-geometry.md
|   |-- ingestion-security.md
|   |-- pdf-native-text-model.md
|   |-- pdf-typography.md
|   |-- pdf-technical-inspector.md
|   |-- pdf-provider-contracts.md
|   `-- persistent-local-jobs.md
|-- decisions/
|-- specifications/
|-- providers/
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
