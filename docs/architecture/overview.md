# Arquitetura

O Eixo usa uma arquitetura modular em camadas. O objetivo e manter o nucleo reutilizavel e independente de infraestrutura, enquanto API, biblioteca, CLI e workers compartilham a mesma logica.

## Camadas

```text
Camada de consumo
  Python SDK, TypeScript SDK, REST API, CLI e webhooks

Control Plane
  jobs, tenants, templates, schemas, politicas, providers, revisoes e administracao

Document Intelligence Kernel
  modelo documental, inspector, router, planner, pipeline, validacao, confianca e evidencias

Capabilities
  parsers, rendering, OCR, layout, tabelas, classificacao, semantica, reconciliacao e templates

Execution Plane
  LocalRuntime, TemporalRuntime, workers, cache, artifact storage e observabilidade
```

## Fluxo operacional

O fluxo completo esta descrito em Mermaid:

- [processing-flow.mmd](diagrams/processing-flow.mmd)
- [kernel-v0.md](kernel-v0.md)
- [document-engine.md](document-engine.md)
- [runtimes-and-workers.md](runtimes-and-workers.md)

## Regras essenciais

- A API adapta casos de uso; ela nao implementa extracao.
- A biblioteca chama os mesmos casos de uso da API.
- A CLI chama a mesma camada de aplicacao quando existir.
- Workers executam capabilities ja definidas pelo motor.
- Capabilities devem produzir artefatos versionados.
- Resultados devem manter evidencias e historico de processamento.

## Execucao inicial recomendada

A primeira implementacao fisica deve priorizar um monorepo simples, uma biblioteca principal, uma API, CLI de diagnostico, storage local e runtime local.

PostgreSQL, MinIO, Redis, Temporal e workers distribuidos devem entrar quando os contratos e o nucleo estiverem suficientemente estaveis.
