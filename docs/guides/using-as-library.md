# Usando o Eixo como Biblioteca Python

## Instalacao

O pacote publico Python desta fase e:

```text
Distribuicao: eixo-document-sdk-python
Import publico: eixo
```

Depois de instalar o wheel:

```bash
pip install eixo_document_sdk_python-0.1.0-py3-none-any.whl
```

Imports principais:

```python
from eixo import DocumentEngine, ProcessingRequest
```

## Uso local

```python
from eixo import BytesSource, DocumentEngine, ProcessingRequest

source = BytesSource(
    content=b"example",
    filename="example.bin",
    size=7,
)

async with DocumentEngine.local() as engine:
    result = await engine.process(
        ProcessingRequest(source=source)
    )
```

## Configuracao

```python
from eixo import DocumentEngine, LocalEngineConfig, LocalRuntimeConfig

engine = DocumentEngine.local(
    config=LocalEngineConfig(
        runtime=LocalRuntimeConfig(
            max_concurrent_tasks=4,
            max_thread_workers=4,
            max_process_workers=2,
            default_timeout=30,
            shutdown_timeout=10,
        ),
        auto_start=True,
    )
)
```

Opcoes publicas atuais:

- `max_concurrent_tasks`;
- `max_thread_workers`;
- `max_process_workers`;
- `default_timeout`;
- `shutdown_timeout`;
- `auto_start`.

## Fontes

```python
from eixo import DocumentSource

bytes_source = DocumentSource.from_bytes(
    b"...",
    filename="documento.pdf",
    declared_media_type="application/pdf",
)

path_source = DocumentSource.from_path("documento.pdf")
stream_source = DocumentSource.from_stream(stream, filename="documento.pdf")
```

`DocumentEngine` tambem aceita formas convenientes:

```python
await engine.inspect("documento.pdf")
await engine.inspect(b"%PDF-1.7\n")
```

Internamente, essas entradas sao convertidas para `DocumentSource`, resolvidas
pelo `SourceResolver`, identificadas por formato real e hash SHA-256, e so entao
encaminhadas para a capability compativel.

## Operacoes

```python
await engine.inspect(source)
await engine.parse(source)
await engine.process(ProcessingRequest(source=source))

job = await engine.submit(ProcessingRequest(source=source))
status = await engine.get_job_status(job.job_id)
result = await engine.get_job_result(job.job_id)
await engine.cancel_job(job.job_id)
```

## Erros publicos

| Erro | Quando ocorre | Retry |
|---|---|---|
| `CapabilityNotFoundError` | Nenhuma capability compativel foi registrada | Depende |
| `ExecutionTimeoutError` | A execucao ultrapassou o timeout | Possivel |
| `ExecutionCancelledError` | A execucao foi cancelada | Nao automatico |
| `ConfigurationError` | A configuracao e invalida | Apos correcao |
| `ValidationError` | Um contrato ou valor e invalido | Apos correcao |
| `SourceNotFoundError` | Origem local inexistente | Apos correcao |
| `SourceNotFileError` | Origem local nao e arquivo | Apos correcao |
| `SourceNotReadableError` | Origem nao pode ser lida | Depende |
| `JobNotFoundError` | Job inexistente | Nao |
| `InvalidStateTransitionError` | Operacao em estado invalido | Depende |

Exemplo:

```python
from eixo import CapabilityNotFoundError

try:
    await engine.process(request)
except CapabilityNotFoundError as error:
    print(error.code)
```

## Tipagem

O wheel inclui `py.typed`. Os contratos e resultados sao objetos tipados, nao dicionarios soltos.

## Exemplos

Veja [examples/python-library](../../examples/python-library/README.md).

## Limites atuais

Ainda nao existem capabilities reais de PDF, Excel, OCR, renderizacao, layout, templates, schemas de negocio, router, planner ou cliente remoto HTTP.
