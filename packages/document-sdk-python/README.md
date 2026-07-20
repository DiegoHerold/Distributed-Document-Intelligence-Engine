# eixo-document-sdk-python

Public Python entrypoint for Eixo.

Distribution name: `eixo-document-sdk-python`.

Public import:

```python
from eixo import DocumentEngine, ProcessingRequest
```

## Local Usage

```python
from eixo import BytesSource, DocumentEngine, ProcessingRequest

source = BytesSource(content=b"example", filename="example.bin", size=7)

async with DocumentEngine.local() as engine:
    result = await engine.process(ProcessingRequest(source=source))
```

Without a registered capability, methods raise `CapabilityNotFoundError`. Real PDF, Excel, OCR, layout and semantic capabilities are not implemented yet.

## Typing

The package includes `py.typed` and reexports typed contracts from the core packages.

## Errors

Public errors are reexported from `eixo`, including `EixoError`, `CapabilityNotFoundError`, `ExecutionTimeoutError`, `ExecutionCancelledError`, `ConfigurationError`, `ValidationError`, `JobNotFoundError` and `InvalidStateTransitionError`.

## Dependencies

The SDK remains lightweight. It does not install OCR, CUDA, databases, Redis, MinIO, Temporal or model dependencies.

