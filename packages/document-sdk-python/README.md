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

source = DocumentSource.from_bytes(
    b"%PDF-1.7\n",
    filename="example.pdf",
    media_type="application/pdf",
)

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

## Ingestion Security

`DocumentEngine.local()` applies the same central ingestion policy used by the
REST API and CLI. The policy validates known size, streaming size, empty files,
detected format, declared MIME, basic corruption, XLSX/ZIP limits, read
timeouts, safe names and known page counts before storing the original.

```python
from eixo import DocumentEngine, IngestionLimits, IngestionSecurityPolicy

security = IngestionSecurityPolicy(
    limits=IngestionLimits(max_file_size_bytes=100 * 1024 * 1024)
)

async with DocumentEngine.local(security=security) as engine:
    ...
```

## Native PDF Provider

PDF provider contracts are available from `eixo.pdf`. The PyMuPDF-backed
provider is optional and isolated from the core packages.

```python
from eixo import DocumentEngine, DocumentSource, PDFOpenOptions, PDFProviderSettings
from eixo.providers.pdf.pymupdf import PYMUPDF_PROVIDER_ID, PyMuPDFPDFProvider

provider = PyMuPDFPDFProvider()
source = DocumentSource.from_path("document.pdf")

engine = DocumentEngine.local(
    pdf_providers=(provider,),
    pdf=PDFProviderSettings(default_provider=PYMUPDF_PROVIDER_ID),
)

probe = await engine.pdf_provider.probe(source)

async with await engine.pdf_provider.open(
    source,
    PDFOpenOptions(password=None),
) as document:
    info = await document.get_basic_info()
    page = await document.get_page(0)
    geometry = await page.get_basic_geometry()
```

For the Fase 3.2 technical inspector, use the specialized diagnostic API:

```python
from eixo import PDFInspectionOptions

inspection = await engine.inspect_pdf(
    source,
    options=PDFInspectionOptions(max_pages_to_inspect=5),
)
```

The result is a typed `PDFTechnicalInspection` with integrity, version, page
summary, metadata, security, permissions, resource signals, coverage,
provenance and processing recommendations. Passwords are never serialized; only
`password_provided` is recorded.

## Canonical Geometry

The public geometry module is available as `eixo.geometry`:

```python
from eixo.geometry import AffineMatrix, BoundingBox, Size

page_size = Size(width=595.0, height=842.0)
box = BoundingBox(72.0, 100.0, 300.0, 150.0)

normalized = box.normalize(page_size)
restored = normalized.denormalize(page_size)
transformed = box.transform(AffineMatrix.rotation(90.0))
```

Canonical geometry uses top-left origin, X to the right, Y downward, absolute
units in points and positive clockwise rotation.

## PDF Internal Structure

Fase 3.4 exposes a diagnostic internal PDF map:

```python
artifact = await engine.map_pdf_internal_structure(source)

fonts = artifact.resource_catalog.fonts
streams = artifact.pages[0].content_streams
relations = artifact.object_graph.relations
```

The artifact preserves object references, content stream sequence, resource
catalogs, provider limitations and provenance. It does not extract full text,
image bytes, vectors or visual scene elements.

## PDF Typography And Native Text

Phases 3.5 and 3.6 expose typography and native text artifacts:

```python
typography = await engine.resolve_pdf_typography(source)
native_text = await engine.extract_pdf_native_text(source)

fonts = typography.font_catalog.fonts
glyphs = native_text.pages[0].glyphs
statistics = native_text.statistics
```

Fonts, styles and text occurrences stay separate. Glyphs without Unicode and
invisible text are preserved with explicit warnings or visibility state when
the provider exposes enough information.

Install the backend only when needed:

```bash
pip install "eixo-document-sdk-python[pdf-pymupdf]"
```

## Typing

The package includes `py.typed` and reexports typed contracts from the core packages,
including artifact references and document lifecycle models.

## Errors

Public errors are reexported from `eixo`, including `EixoError`,
`CapabilityNotFoundError`, `ExecutionTimeoutError`, `ExecutionCancelledError`,
`ConfigurationError`, `ValidationError`, `SourceNotFoundError`,
`SourceNotFileError`, `SourceNotReadableError`, `FileTooLargeError`,
`EmptyFileError`, `UnsupportedFormatError`, `InvalidMimeError`,
`MimeMismatchError`, `CorruptedFileError`, `InvalidContainerError`,
`UnsafeFilenameError`, `PathTraversalError`, `ArchiveSecurityError`,
`ZipBombError`, `PageLimitExceededError`, `ReadTimeoutError`,
`JobNotFoundError`, `JobResultUnavailableError`, `InvalidJobTransitionError`,
`JobConcurrencyError`, `JobPersistenceError` and
`InvalidStateTransitionError`.

## Dependencies

The SDK remains lightweight. It does not install OCR, CUDA, databases, Redis, MinIO, Temporal or model dependencies.
PyMuPDF is optional and is not imported by the core, engine, API or CLI.
