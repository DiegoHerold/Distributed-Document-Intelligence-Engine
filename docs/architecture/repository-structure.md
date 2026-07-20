# Estrutura do Repositorio

O monorepo usa Python 3.12+ e namespace agrupado `eixo.*`.

```text
apps/
├── api/
└── cli/

packages/
├── document-core/
├── document-model/
├── document-application/
├── document-engine/
├── document-sdk-python/
├── artifacts/
├── plugins/
└── runtime-local/

adapters/
contracts/
examples/
tests/
├── unit/
├── integration/
├── contract/
└── architecture/
```

## Responsabilidades

- `document-core`: tipos fundamentais e contratos publicos.
- `document-model`: namespace reservado para o modelo canonico.
- `plugins`: contratos de capabilities, providers e registry.
- `artifacts`: referencias de artefatos e futura camada de armazenamento.
- `document-application`: casos de uso independentes de transporte.
- `document-engine`: composicao inicial do motor.
- `document-sdk-python`: fachada publica Python.
- `runtime-local`: namespace reservado para o runtime local.
- `apps/api`: adaptador HTTP futuro; nao contem logica do motor.
- `apps/cli`: adaptador de terminal futuro; nao contem logica do motor.

## Direcao de dependencias

```text
apps/api, apps/cli, eixo.sdk
  -> eixo.application
  -> eixo.engine / eixo.plugins / eixo.core

eixo.engine
  -> eixo.plugins
  -> eixo.core

eixo.model, eixo.artifacts
  -> eixo.core
```

Camadas centrais nao importam FastAPI, Typer, Click, Temporal, Redis, MinIO, SQLAlchemy, boto3 ou adapters concretos.

