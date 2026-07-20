# eixo-document-engine

Public facade and local composition root for Eixo.

`DocumentEngine` coordinates application use cases. It does not parse documents,
run OCR, implement routing, or execute capabilities directly. Local persistence
covers original artifacts, document lifecycle records and local job records.

## Public API

- `DocumentEngine.local(...)`
- `await engine.inspect(...)`
- `await engine.parse(...)`
- `await engine.process(...)`
- `await engine.submit(...)`
- `await engine.ingest(...)`
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
- `LocalArtifactStore`;
- `LocalDocumentRepository`;
- `PersistentJobService` backed by `SQLiteJobStore`.

By default, local jobs use `<data_directory>/jobs/jobs.sqlite3`. The path can
be overridden with `job_database_path`.

Dependencies: `eixo-document-core`, `eixo-document-application`, `eixo-plugins`, `eixo-runtime-local`.

No PDF, Excel, OCR or semantic capability is implemented in this package.
