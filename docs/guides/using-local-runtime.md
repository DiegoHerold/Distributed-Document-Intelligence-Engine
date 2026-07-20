# Usando o LocalRuntime

## Uso direto

```python
from eixo.plugins import ExecutionContext, ExecutionTask
from eixo.runtime.local import LocalRuntime
from eixo.core import CorrelationId

async def handler(value, context):
    return value

async with LocalRuntime() as runtime:
    result = await runtime.execute(
        ExecutionTask(
            task_id="task_example",
            name="example",
            handler=handler,
            input="hello",
        ),
        context=ExecutionContext(correlation_id=CorrelationId.new()),
    )
```

## Uso pelo engine

```python
from eixo.engine import DocumentEngine

async with DocumentEngine.local(max_concurrent_tasks=4, default_timeout=30) as engine:
    ...
```

## Thread

Use `ExecutionMode.THREAD` para chamadas sincronas bloqueantes leves.

## Processo

Use `ExecutionMode.PROCESS` para trabalho CPU-bound. A funcao e os argumentos precisam ser serializaveis e importaveis em Windows e Linux.

## Progresso

Handlers podem reportar progresso por `context.progress`:

```python
await context.progress.report(current=5, total=10, message="metade")
```

## Cancelamento

Handlers longos devem verificar `context.cancellation_token.raise_if_cancelled()`.

Threads e processos Python nao podem ser interrompidos a forca de forma segura depois de iniciados; o runtime cancela a espera e preserva status/erro estruturado.

## Fora do escopo

O LocalRuntime nao processa PDF, Excel, OCR, templates, schemas de negocio, filas distribuidas ou Temporal.

