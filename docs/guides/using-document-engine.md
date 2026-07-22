# Usando o DocumentEngine

## Import publico

```python
from eixo import DocumentEngine, ProcessingRequest
```

## Criacao local

```python
engine = DocumentEngine.local()
```

Ou com configuracao:

```python
from eixo import DocumentEngine, LocalRuntimeConfig
from eixo.engine import LocalEngineConfig

engine = DocumentEngine.local(
    config=LocalEngineConfig(
        runtime=LocalRuntimeConfig(
            max_concurrent_tasks=4,
            default_timeout=30,
        )
    )
)
```

## Ciclo de vida recomendado

```python
async with DocumentEngine.local() as engine:
    result = await engine.process(
        ProcessingRequest(source=source)
    )
```

## Metodos publicos

- `inspect(request_or_source)`
- `parse(request_or_source)`
- `process(request_or_source)`
- `submit(request_or_source)`
- `get_job_status(job_id)`
- `get_job_result(job_id)`
- `cancel_job(job_id)`
- `start()`
- `shutdown()`

Os metodos aceitam o request canonico ou uma `DocumentSource` quando aplicavel.

## Registro de capabilities

Capabilities podem ser registradas antes do start:

```python
engine = DocumentEngine.local(registry=registry)
```

Ou:

```python
engine.register_capability(capability)
```

Depois que o engine inicia, as dependencias principais ficam protegidas contra mudanca silenciosa.

## Erros

O engine preserva erros de dominio. Por exemplo, formatos desconhecidos levantam
`UnsupportedFormatError`; se a capability PDF estiver registrada mas o backend
opcional nao estiver disponivel, a execucao levanta `PDFProviderUnavailableError`.

## Limites atuais

Existe integracao publica inicial do parser nativo de PDF para `inspect()`,
`parse()` e jobs locais. Excel, OCR, renderizacao, templates, schemas de negocio,
router e planner ainda ficam fora do escopo atual.
