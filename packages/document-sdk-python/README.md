# eixo-document-sdk-python

Public Python entrypoint for Eixo.

Distribution name: `eixo-document-sdk-python`.

Public import:

```python
from eixo import DocumentEngine, ProcessingRequest
```

## Local Usage

```python
from eixo import DocumentEngine, DocumentSource, ProcessingRequest

source = DocumentSource.from_bytes(b"example", filename="example.bin")

async with DocumentEngine.local() as engine:
    result = await engine.process(ProcessingRequest(source=source))
```

`DocumentEngine` also accepts convenient path and bytes inputs, such as
`await engine.inspect("document.pdf")`, and converts them to typed
`DocumentSource` contracts internally.

Use `await engine.ingest(source)` to store the original locally and create a
`DocumentRecord` with status `stored` before any parsing capability exists.

Jobs submitted through `await engine.submit(...)` are persisted by the local
engine in SQLite. Completed local job status and small structured results can
be read by a later `DocumentEngine.local()` instance that uses the same data
directory.

Without a registered capability, methods raise `CapabilityNotFoundError`. Real PDF, Excel, OCR, layout and semantic capabilities are not implemented yet.

## Typing

The package includes `py.typed` and reexports typed contracts from the core packages,
including artifact references and document lifecycle models.

## Errors

Public errors are reexported from `eixo`, including `EixoError`, `CapabilityNotFoundError`, `ExecutionTimeoutError`, `ExecutionCancelledError`, `ConfigurationError`, `ValidationError`, `SourceNotFoundError`, `SourceNotFileError`, `SourceNotReadableError`, `JobNotFoundError`, `JobResultUnavailableError`, `InvalidJobTransitionError`, `JobConcurrencyError`, `JobPersistenceError` and `InvalidStateTransitionError`.

## Dependencies

The SDK remains lightweight. It does not install OCR, CUDA, databases, Redis, MinIO, Temporal or model dependencies.
