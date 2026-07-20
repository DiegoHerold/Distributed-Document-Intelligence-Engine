# DocumentEngine

`DocumentEngine` is the public facade of the Eixo motor.

It exists to provide a stable, simple interface for consumers while preserving the internal architecture:

```text
Consumer
  -> DocumentEngine
  -> Application Use Case
  -> Capability Registry
  -> ExecutionRuntime
  -> Capability
  -> Typed Result
```

## Responsibilities

- Compose local dependencies through `DocumentEngine.local()`.
- Expose public methods for inspect, parse, process and submit.
- Manage lifecycle for the runtime and local dependencies.
- Preserve typed public contracts.
- Support dependency injection for tests, API, CLI and future remote mode.

## Non-responsibilities

`DocumentEngine` is not:

- a parser;
- a runtime;
- a capability registry;
- a repository;
- a processing router;
- a provider implementation.

It does not import FastAPI, CLI frameworks, databases, Redis, MinIO, Temporal, PDF libraries, Excel libraries or OCR providers.

## Local Factory

```python
from eixo import DocumentEngine

engine = DocumentEngine.local()
```

`DocumentEngine.local()` creates one `LocalRuntime`, one `CapabilityRegistry`, application use cases and an in-memory job service.

Custom dependencies can be injected:

```python
engine = DocumentEngine.local(
    registry=registry,
    runtime=runtime,
)
```

## Lifecycle

Recommended usage:

```python
async with DocumentEngine.local() as engine:
    result = await engine.process(request)
```

Manual usage:

```python
engine = DocumentEngine.local()
await engine.start()
try:
    result = await engine.process(request)
finally:
    await engine.shutdown()
```

Public operations auto-start the engine when `auto_start=True`, which is the default for local mode.

Internal states:

- `created`;
- `starting`;
- `running`;
- `stopping`;
- `stopped`;
- `failed`.

After shutdown, operations are rejected with a domain state error.

## Jobs

`submit()` returns a `JobResult` immediately. Job status, result and cancellation are exposed by:

- `get_job_status(job_id)`;
- `get_job_result(job_id)`;
- `cancel_job(job_id)`.

The current job service is in-memory and local-only.

## Current limitation

No real PDF, Excel, OCR, rendering, layout, template or semantic capability exists yet. Without registered capabilities, public methods preserve and propagate `CapabilityNotFoundError`.

