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

`DocumentEngine.local()` creates one `LocalRuntime`, one `CapabilityRegistry`, application use cases and a persistent local job service backed by SQLite.

Custom dependencies can be injected:

```python
engine = DocumentEngine.local(
    registry=registry,
    runtime=runtime,
    pdf_providers=(pdf_provider,),
    pdf=pdf_settings,
    data_directory=".eixo/local",
    job_database_path=".eixo/local/jobs/jobs.sqlite3",
    security=security_policy,
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

The current job service is local-only and persistent. By default, jobs are
stored under `<data_directory>/jobs/jobs.sqlite3`. The service keeps the public
flow stable while preserving completed job status and results across a simple
restart of the local engine.

Interrupted non-terminal jobs are recovered explicitly:

- `created`, `queued` and `running` become `failed` with `job.interrupted`;
- `cancel_requested` becomes `cancelled`.

Production persistence, distributed workers and event streams remain outside
the current local engine.

## Ingestion Security

`DocumentEngine.local()` accepts `security=IngestionSecurityPolicy(...)`.

The policy is applied before content is stored, before capabilities run and
before jobs persist successful results. See
[ingestion-security.md](ingestion-security.md).

## PDF Providers

`DocumentEngine.local()` accepts `pdf_providers=(...)` and keeps a
`PDFProviderRegistry` for native PDF providers. The registry stores provider
contracts only; `DocumentEngine` does not import PyMuPDF or any concrete PDF
backend.

The active provider can be resolved through `engine.pdf_provider` when a default
provider is configured or a single compatible provider is registered. See
[pdf-provider-contracts.md](pdf-provider-contracts.md).

`inspect_pdf(source, options=PDFInspectionOptions(...))` runs the technical PDF
inspector over the registered provider registry and returns
`PDFTechnicalInspection`. This is a specialized diagnostic API for native PDF
work; the generic `inspect()` and `parse()` flows remain capability-backed.

`map_pdf_internal_structure(source, options=PDFInternalMappingOptions(...))`
returns `PDFInternalStructureArtifact`, preserving the PDF object graph, content
stream sequence, resource catalog, limitations and provenance.

`resolve_pdf_typography(source, options=PDFTypographyOptions(...))` returns
`PDFTypographyArtifact`, preserving the font catalog, encodings, text styles and
provider support matrix.

`extract_pdf_native_text(source, options=PDFNativeTextExtractionOptions(...))`
returns `PDFNativeTextArtifact`, preserving page text layers, glyphs,
characters, words, spans, baselines, lines, blocks, relations and statistics.

`extract_pdf_native_images(source, options=PDFImageExtractionOptions(...))`
returns `PDFNativeImageArtifact`, preserving image resources, binary
references, masks, visual occurrences, page image layers, catalog queries and
statistics without embedding large bytes in JSON.

`extract_pdf_native_vectors(source, options=PDFNativeVectorOptions(...))`
returns `PDFNativeVectorArtifact`, preserving vector commands, subpaths, fill
and stroke styles, effective graphics states, clipping paths, page vector
layers, paint order and statistics.

## Current limitation

No real PDF, Excel, OCR, rendering, layout, template or semantic capability exists yet. Without registered capabilities, public methods preserve and propagate `CapabilityNotFoundError`.
