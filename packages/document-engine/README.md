# eixo-document-engine

Public facade and local composition root for Eixo.

`DocumentEngine` coordinates application use cases. It does not parse documents, run OCR, own persistence, implement routing, or execute capabilities directly.

## Public API

- `DocumentEngine.local(...)`
- `await engine.inspect(...)`
- `await engine.parse(...)`
- `await engine.process(...)`
- `await engine.submit(...)`
- `await engine.get_job_status(...)`
- `await engine.get_job_result(...)`
- `await engine.cancel_job(...)`
- `await engine.start()`
- `await engine.shutdown()`

## Local Composition

`DocumentEngine.local()` creates:

- one `LocalRuntime`;
- one `CapabilityRegistry`;
- application use cases;
- capability-backed application services;
- an in-memory job service.

Dependencies: `eixo-document-core`, `eixo-document-application`, `eixo-plugins`, `eixo-runtime-local`.

No PDF, Excel, OCR or semantic capability is implemented in this package.

