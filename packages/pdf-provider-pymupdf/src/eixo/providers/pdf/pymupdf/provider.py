from __future__ import annotations

import asyncio
import importlib
import importlib.util
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import BinaryIO, Protocol

from eixo.application import LocalSourceResolver, ResolvedDocumentSource
from eixo.core import (
    ClosedPDFDocumentError,
    ContractVersion,
    CorruptedPDFError,
    DocumentSource,
    EixoWarning,
    InvalidPDFPasswordError,
    PDFPageOutOfRangeError,
    PDFPasswordRequiredError,
    PDFProviderExecutionError,
    PDFProviderUnavailableError,
    PDFResourceLimitExceededError,
    ProviderId,
    ProviderVersion,
)
from eixo.pdf import (
    PDFBasicInfo,
    PDFContentStream,
    PDFContentStreamReference,
    PDFDocumentHandle,
    PDFEncryptionState,
    PDFFontResourceDescriptor,
    PDFImageResourceDescriptor,
    PDFIndirectObject,
    PDFInternalMappingOptions,
    PDFInternalPageMap,
    PDFInternalStructureArtifact,
    PDFInspectionState,
    PDFMappingStatus,
    PDFObjectGraph,
    PDFObjectReference,
    PDFObjectRelation,
    PDFObjectRelationType,
    PDFOpenOptions,
    PDFPageGeometry,
    PDFPageHandle,
    PDFPageReference,
    PDFPageTechnicalHints,
    PDFProbeOptions,
    PDFProbeResult,
    PDFProbeStatus,
    PDFProviderCapabilityMatrixEntry,
    PDFProviderCapabilities,
    PDFProviderDescriptor,
    PDFProviderProvenance,
    PDFProviderSupportStatus,
    PDFResourceCatalog,
    PDFResourceReference,
    PDFResourceScope,
    PDFResourceType,
    PDFUnknownResource,
    PDFXObjectResource,
    PDFProviderRegistry,
    PDFSupportLevel,
    ProviderLimitation,
    canonical_pdf_page_geometry,
    resource_id,
)

logger = logging.getLogger(__name__)

PYMUPDF_PROVIDER_ID = ProviderId("prov_pdf_pymupdf")
PYMUPDF_PROVIDER_VERSION = ProviderVersion("0.1.0")


class _Backend(Protocol):
    def open(self, *args: object, **kwargs: object) -> object:
        ...


@dataclass(slots=True)
class PyMuPDFPDFProvider:
    source_resolver: LocalSourceResolver | None = None
    provider_version: ProviderVersion = PYMUPDF_PROVIDER_VERSION
    _backend: _Backend | ModuleType | None = field(default=None, repr=False)

    @property
    def descriptor(self) -> PDFProviderDescriptor:
        backend = self._backend
        backend_version = _backend_version(backend) if backend is not None else None
        limitations: tuple[ProviderLimitation, ...] = ()
        if backend is None and _find_backend() is None:
            limitations = (
                ProviderLimitation(
                    code="backend_not_installed",
                    message=(
                        "PyMuPDF is not installed. Install the optional "
                        "`eixo-pdf-provider-pymupdf[backend]` extra."
                    ),
                    scope="provider",
                ),
            )
        return PDFProviderDescriptor(
            provider_id=PYMUPDF_PROVIDER_ID,
            name="PyMuPDF PDF Provider",
            provider_version=self.provider_version,
            backend_name="PyMuPDF",
            backend_version=backend_version,
            capabilities=self.capabilities,
            limitations=limitations,
        )

    @property
    def capabilities(self) -> PDFProviderCapabilities:
        return PDFProviderCapabilities(
            supports_encrypted_documents=PDFSupportLevel.PARTIAL,
            supports_password_authentication=PDFSupportLevel.SUPPORTED,
            supports_incremental_page_access=PDFSupportLevel.SUPPORTED,
            supports_basic_info=PDFSupportLevel.SUPPORTED,
            supports_page_geometry=PDFSupportLevel.SUPPORTED,
            supports_metadata_inspection=PDFSupportLevel.PARTIAL,
            supports_security_inspection=PDFSupportLevel.PARTIAL,
            supports_permission_inspection=PDFSupportLevel.UNSUPPORTED,
            supports_resource_inspection=PDFSupportLevel.PARTIAL,
            supports_text_presence_inspection=PDFSupportLevel.PARTIAL,
            supports_image_presence_inspection=PDFSupportLevel.PARTIAL,
            supports_vector_presence_inspection=PDFSupportLevel.PARTIAL,
            supports_link_inspection=PDFSupportLevel.PARTIAL,
            supports_annotation_inspection=PDFSupportLevel.PARTIAL,
            supports_form_inspection=PDFSupportLevel.PARTIAL,
            supports_layer_inspection=PDFSupportLevel.UNSUPPORTED,
            supports_text_extraction=PDFSupportLevel.UNSUPPORTED,
            supports_glyph_extraction=PDFSupportLevel.UNSUPPORTED,
            supports_word_extraction=PDFSupportLevel.UNSUPPORTED,
            supports_native_blocks=PDFSupportLevel.UNSUPPORTED,
            supports_image_extraction=PDFSupportLevel.UNSUPPORTED,
            supports_image_occurrences=PDFSupportLevel.UNSUPPORTED,
            supports_vector_extraction=PDFSupportLevel.UNSUPPORTED,
            supports_clipping=PDFSupportLevel.UNSUPPORTED,
            supports_annotations=PDFSupportLevel.UNSUPPORTED,
            supports_forms=PDFSupportLevel.UNSUPPORTED,
            supports_layers=PDFSupportLevel.UNSUPPORTED,
            supports_content_streams=PDFSupportLevel.PARTIAL,
            supports_object_references=PDFSupportLevel.PARTIAL,
            supports_embedded_fonts=PDFSupportLevel.PARTIAL,
            supports_rendering=PDFSupportLevel.UNSUPPORTED,
        )

    async def probe(
        self,
        source: DocumentSource,
        options: PDFProbeOptions | None = None,
    ) -> PDFProbeResult:
        opts = options or PDFProbeOptions()
        started = time.perf_counter()
        _log("pdf.provider.probe.started")
        try:
            async with _resolver(self).resolve(source) as resolved:
                sample = await _read_sample(resolved, opts.timeout_seconds)
                detected_version = _detect_pdf_version(sample)
                if detected_version is None:
                    return self._probe_result(
                        supported=False,
                        status=PDFProbeStatus.NOT_PDF,
                        confidence=0.0,
                        detected_version=None,
                        encryption_state=PDFEncryptionState.UNKNOWN,
                        requires_password=None,
                        options=opts,
                        source=resolved,
                    )
                _validate_limits(resolved.content_length, opts.max_file_size_bytes)
                backend = self._load_backend()
                document = await _open_backend_document(backend, resolved, opts)
                try:
                    state = _encryption_state(document, password=opts.password)
                    if state == PDFEncryptionState.PASSWORD_REQUIRED:
                        status = PDFProbeStatus.ENCRYPTED
                        supported = True
                    elif state == PDFEncryptionState.INVALID_PASSWORD:
                        status = PDFProbeStatus.ENCRYPTED
                        supported = False
                    else:
                        _validate_page_limit(_page_count(document), opts.max_pages)
                        status = PDFProbeStatus.VALID
                        supported = True
                    return self._probe_result(
                        supported=supported,
                        status=status,
                        confidence=1.0,
                        detected_version=detected_version,
                        encryption_state=state,
                        requires_password=state
                        in {
                            PDFEncryptionState.PASSWORD_REQUIRED,
                            PDFEncryptionState.INVALID_PASSWORD,
                        },
                        options=opts,
                        source=resolved,
                    )
                finally:
                    await _close_document(document)
        except PDFProviderUnavailableError:
            raise
        except PDFResourceLimitExceededError:
            raise
        except Exception as exc:
            raise _map_backend_error(exc, operation="probe")
        finally:
            _log(
                "pdf.provider.probe.completed",
                duration_ms=f"{(time.perf_counter() - started) * 1000:.3f}",
            )

    async def open(
        self,
        source: DocumentSource,
        options: PDFOpenOptions | None = None,
    ) -> PDFDocumentHandle:
        opts = options or PDFOpenOptions()
        started = time.perf_counter()
        _log("pdf.provider.open.started")
        resolved: ResolvedDocumentSource | None = None
        document: object | None = None
        try:
            resolved = await _resolver(self).open(source)
            _validate_limits(resolved.content_length, opts.max_file_size_bytes)
            backend = self._load_backend()
            document = await _open_backend_document(backend, resolved, opts.to_probe_options())
            state = _encryption_state(document, password=opts.password)
            if state == PDFEncryptionState.PASSWORD_REQUIRED:
                raise PDFPasswordRequiredError("PDF password is required")
            if state == PDFEncryptionState.INVALID_PASSWORD:
                raise InvalidPDFPasswordError("PDF password is invalid")
            page_count = _page_count(document)
            _validate_page_limit(page_count, opts.max_pages)
            handle = PyMuPDFPDFDocumentHandle(
                document=document,
                resolved=resolved,
                descriptor=self.descriptor,
                options=opts,
                page_count=page_count,
                detected_version=_detect_pdf_version(await _read_sample(resolved, None)),
                encryption_state=state,
            )
            _log(
                "pdf.provider.open.completed",
                duration_ms=f"{(time.perf_counter() - started) * 1000:.3f}",
                page_count=str(page_count),
            )
            return handle
        except Exception as exc:
            if document is not None:
                await _close_document(document)
            if resolved is not None:
                resolved.close()
            _log("pdf.provider.open.failed", error_type=exc.__class__.__name__)
            if isinstance(
                exc,
                (
                    PDFPasswordRequiredError,
                    InvalidPDFPasswordError,
                    PDFProviderUnavailableError,
                    PDFResourceLimitExceededError,
                ),
            ):
                raise
            raise _map_backend_error(exc, operation="open")

    def _load_backend(self) -> _Backend | ModuleType:
        if self._backend is not None:
            return self._backend
        try:
            return importlib.import_module("fitz")
        except ModuleNotFoundError as exc:
            raise PDFProviderUnavailableError(
                "PyMuPDF PDF provider is not available",
                public_context={
                    "provider_id": str(PYMUPDF_PROVIDER_ID),
                    "install": "Install eixo-pdf-provider-pymupdf[backend].",
                },
                cause=exc,
            ) from exc

    def _probe_result(
        self,
        *,
        supported: bool,
        status: PDFProbeStatus,
        confidence: float,
        detected_version: str | None,
        encryption_state: PDFEncryptionState,
        requires_password: bool | None,
        options: PDFProbeOptions,
        source: ResolvedDocumentSource,
    ) -> PDFProbeResult:
        return PDFProbeResult(
            supported=supported,
            status=status,
            confidence=confidence,
            detected_media_type="application/pdf" if detected_version is not None else None,
            detected_version=detected_version,
            encryption_state=encryption_state,
            requires_password=requires_password,
            provider_id=self.descriptor.provider_id,
            provider_version=self.descriptor.provider_version,
            backend_name=self.descriptor.backend_name,
            backend_version=self.descriptor.backend_version,
            limitations=self.descriptor.limitations,
            provenance=_provenance(
                self.descriptor,
                operation="probe",
                source=source,
                options=options.safe_options(),
            ),
        )


@dataclass(slots=True)
class PyMuPDFPDFDocumentHandle:
    document: object = field(repr=False)
    resolved: ResolvedDocumentSource = field(repr=False)
    descriptor: PDFProviderDescriptor
    options: PDFOpenOptions
    page_count: int
    detected_version: str | None
    encryption_state: PDFEncryptionState
    _closed: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    @property
    def provider_id(self) -> str:
        return str(self.descriptor.provider_id)

    @property
    def source(self) -> DocumentSource:
        return self.resolved.source

    @property
    def closed(self) -> bool:
        return self._closed

    async def __aenter__(self) -> PDFDocumentHandle:
        self._ensure_open()
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.close()

    async def get_basic_info(self) -> PDFBasicInfo:
        self._ensure_open()
        async with self._lock:
            metadata = _safe_metadata(getattr(self.document, "metadata", {}) or {})
            return PDFBasicInfo(
                page_count=self.page_count,
                declared_version=self.detected_version,
                interpreted_version=_interpreted_version(self.document, self.detected_version),
                encryption_state=self.encryption_state,
                requires_password=False,
                metadata=metadata,
                size_bytes=self.resolved.content_length,
                provider_id=self.descriptor.provider_id,
                provider_version=self.descriptor.provider_version,
                backend_name=self.descriptor.backend_name,
                backend_version=self.descriptor.backend_version,
                limitations=self.descriptor.limitations,
                provenance=_provenance(
                    self.descriptor,
                    operation="get_basic_info",
                    source=self.resolved,
                    options=self.options.safe_options(),
                ),
            )

    async def get_page_count(self) -> int:
        self._ensure_open()
        return self.page_count

    async def get_page(self, index: int) -> PDFPageHandle:
        self._ensure_open()
        if index < 0 or index >= self.page_count:
            raise PDFPageOutOfRangeError(
                "PDF page index is out of range",
                public_context={"page_index": index, "page_count": self.page_count},
            )
        _log("pdf.provider.page.accessed", page_index=str(index))
        return PyMuPDFPDFPageHandle(document_handle=self, index=index)

    async def close(self) -> None:
        if self._closed:
            return
        async with self._lock:
            if self._closed:
                return
            await _close_document(self.document)
            self.resolved.close()
            self._closed = True
            _log("pdf.provider.document.closed")

    def _ensure_open(self) -> None:
        if self._closed:
            raise ClosedPDFDocumentError("PDF document handle is closed")

    async def get_internal_structure(
        self,
        options: PDFInternalMappingOptions | None = None,
    ) -> PDFInternalStructureArtifact:
        self._ensure_open()
        opts = options or PDFInternalMappingOptions()
        async with self._lock:
            return await asyncio.to_thread(_internal_structure_from_document, self, opts)


@dataclass(slots=True)
class PyMuPDFPDFPageHandle:
    document_handle: PyMuPDFPDFDocumentHandle
    index: int

    @property
    def page_number(self) -> int:
        return self.index + 1

    @property
    def stable_id(self) -> str:
        return f"pdf-page-{self.index}"

    async def get_basic_geometry(self) -> PDFPageGeometry:
        self.document_handle._ensure_open()
        async with self.document_handle._lock:
            page = await asyncio.to_thread(
                self.document_handle.document.load_page,
                self.index,
            )
            rect = _box(getattr(page, "rect", None))
            media_box = _box(getattr(page, "mediabox", None))
            crop_box = _box(getattr(page, "cropbox", None))
            rotation = int(getattr(page, "rotation", 0) or 0)
            user_unit = _user_unit(page, self.document_handle.document)
            canonical_geometry = (
                canonical_pdf_page_geometry(
                    media_box=media_box,
                    crop_box=crop_box,
                    rotation_degrees=rotation,
                    user_unit=user_unit,
                )
                if media_box is not None
                else None
            )
            width = (
                canonical_geometry.width
                if canonical_geometry is not None
                else rect[2] - rect[0]
                if rect is not None
                else 0.0
            )
            height = (
                canonical_geometry.height
                if canonical_geometry is not None
                else rect[3] - rect[1]
                if rect is not None
                else 0.0
            )
            return PDFPageGeometry(
                page_index=self.index,
                page_number=self.page_number,
                width=width,
                height=height,
                rotation=rotation,
                media_box=media_box,
                crop_box=crop_box,
                canonical_geometry=canonical_geometry,
                provenance=_provenance(
                    self.document_handle.descriptor,
                    operation="get_basic_geometry",
                    source=self.document_handle.resolved,
                    options=self.document_handle.options.safe_options(),
                    page_index=self.index,
                ),
            )

    async def get_technical_hints(self) -> PDFPageTechnicalHints:
        self.document_handle._ensure_open()
        async with self.document_handle._lock:
            page = await asyncio.to_thread(
                self.document_handle.document.load_page,
                self.index,
            )
            return await asyncio.to_thread(_technical_hints_from_page, page)


def create_pymupdf_pdf_provider() -> PyMuPDFPDFProvider:
    return PyMuPDFPDFProvider()


def register_pymupdf_pdf_provider(registry: PDFProviderRegistry) -> PyMuPDFPDFProvider:
    provider = create_pymupdf_pdf_provider()
    registry.register(provider)
    return provider


def _resolver(provider: PyMuPDFPDFProvider) -> LocalSourceResolver:
    return provider.source_resolver or LocalSourceResolver()


def _find_backend() -> object | None:
    return importlib.util.find_spec("fitz")


async def _read_sample(
    resolved: ResolvedDocumentSource,
    timeout_seconds: float | None,
    size: int = 64,
) -> bytes:
    resolved.rewind()
    try:
        if timeout_seconds is None:
            return resolved.stream.read(size)
        return await asyncio.wait_for(
            asyncio.to_thread(resolved.stream.read, size),
            timeout=timeout_seconds,
        )
    finally:
        resolved.rewind()


def _detect_pdf_version(sample: bytes) -> str | None:
    if not sample.startswith(b"%PDF-") or len(sample) < 8:
        return None
    version = sample[5:8].decode("ascii", errors="ignore")
    return version if version and version[0].isdigit() else None


def _validate_limits(size: int | None, max_size: int | None) -> None:
    if max_size is not None and size is not None and size > max_size:
        raise PDFResourceLimitExceededError(
            "PDF exceeds the configured size limit",
            public_context={"limit_bytes": max_size, "observed_bytes": size},
        )


def _validate_page_limit(page_count: int, max_pages: int | None) -> None:
    if max_pages is not None and page_count > max_pages:
        raise PDFResourceLimitExceededError(
            "PDF exceeds the configured page limit",
            public_context={"limit_pages": max_pages, "observed_pages": page_count},
        )


async def _open_backend_document(
    backend: _Backend | ModuleType,
    resolved: ResolvedDocumentSource,
    options: PDFProbeOptions,
) -> object:
    if resolved.local_path is not None:
        return await asyncio.to_thread(backend.open, str(Path(resolved.local_path)))
    data = await _read_all(
        resolved.stream,
        max_size=options.max_file_size_bytes,
        timeout_seconds=options.timeout_seconds,
    )
    resolved.rewind()
    return await asyncio.to_thread(backend.open, stream=data, filetype="pdf")


async def _read_all(
    stream: BinaryIO,
    *,
    max_size: int | None,
    timeout_seconds: float | None,
) -> bytes:
    chunks: list[bytes] = []
    size = 0
    stream.seek(0)
    while True:
        if timeout_seconds is None:
            chunk = stream.read(1024 * 1024)
        else:
            chunk = await asyncio.wait_for(
                asyncio.to_thread(stream.read, 1024 * 1024),
                timeout=timeout_seconds,
            )
        if not chunk:
            break
        size += len(chunk)
        if max_size is not None and size > max_size:
            raise PDFResourceLimitExceededError(
                "PDF exceeds the configured size limit during read",
                public_context={"limit_bytes": max_size, "observed_bytes": size},
            )
        chunks.append(chunk)
    stream.seek(0)
    return b"".join(chunks)


def _encryption_state(document: object, *, password: str | None) -> PDFEncryptionState:
    needs_password = bool(getattr(document, "needs_pass", False))
    if not needs_password:
        return PDFEncryptionState.NOT_ENCRYPTED
    if not password:
        return PDFEncryptionState.PASSWORD_REQUIRED
    authenticated = getattr(document, "authenticate", lambda value: 0)(password)
    return (
        PDFEncryptionState.ENCRYPTED_UNLOCKED
        if int(authenticated or 0) > 0
        else PDFEncryptionState.INVALID_PASSWORD
    )


def _page_count(document: object) -> int:
    value = getattr(document, "page_count", None)
    if value is not None:
        return int(value)
    return int(len(document))  # type: ignore[arg-type]


async def _close_document(document: object) -> None:
    close = getattr(document, "close", None)
    if close is not None:
        await asyncio.to_thread(close)


def _map_backend_error(exc: Exception, *, operation: str) -> Exception:
    name = exc.__class__.__name__.lower()
    if "filedata" in name or "syntax" in name or "corrupt" in name:
        return CorruptedPDFError("PDF content is corrupted", cause=exc)
    if isinstance(exc, PDFProviderExecutionError):
        return exc
    return PDFProviderExecutionError(
        "PDF provider operation failed",
        details={"operation": operation, "backend_error": exc.__class__.__name__},
        cause=exc,
    )


def _safe_metadata(metadata: dict[str, object]) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in metadata.items():
        if key.lower() in {"password", "encryption"}:
            continue
        if value is not None:
            safe[str(key)] = str(value)
    return safe


def _interpreted_version(document: object, fallback: str | None) -> str | None:
    metadata = getattr(document, "metadata", {}) or {}
    value = metadata.get("format") if isinstance(metadata, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip().removeprefix("PDF ").strip() or fallback
    return fallback


def _box(value: object | None) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    try:
        return (
            float(getattr(value, "x0")),
            float(getattr(value, "y0")),
            float(getattr(value, "x1")),
            float(getattr(value, "y1")),
        )
    except (TypeError, ValueError, AttributeError):
        try:
            x0, y0, x1, y1 = value  # type: ignore[misc]
            return (float(x0), float(y0), float(x1), float(y1))
        except (TypeError, ValueError):
            return None


def _user_unit(page: object, document: object) -> float:
    for owner in (page, document):
        value = getattr(owner, "user_unit", None)
        if value is not None:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                return 1.0
            return parsed if parsed > 0.0 else 1.0
    return 1.0


def _technical_hints_from_page(page: object) -> PDFPageTechnicalHints:
    text_count = _text_count(page)
    image_count = _collection_count(page, "get_images", full=True)
    vector_count = _collection_count(page, "get_drawings")
    link_count = _collection_count(page, "get_links")
    annotation_count = _collection_count(page, "annots")
    form_count = _collection_count(page, "widgets")
    return PDFPageTechnicalHints(
        has_text=_state_from_optional_count(text_count),
        has_images=_state_from_optional_count(image_count),
        has_vectors=_state_from_optional_count(vector_count),
        has_links=_state_from_optional_count(link_count),
        has_annotations=_state_from_optional_count(annotation_count),
        has_forms=_state_from_optional_count(form_count),
        approximate_text_count=text_count if text_count != _UNSUPPORTED_COUNT else None,
        approximate_image_count=image_count if image_count != _UNSUPPORTED_COUNT else None,
        approximate_vector_count=vector_count if vector_count != _UNSUPPORTED_COUNT else None,
        approximate_link_count=link_count if link_count != _UNSUPPORTED_COUNT else None,
        approximate_annotation_count=annotation_count
        if annotation_count != _UNSUPPORTED_COUNT
        else None,
        approximate_form_count=form_count if form_count != _UNSUPPORTED_COUNT else None,
    )


def _internal_structure_from_document(
    handle: PyMuPDFPDFDocumentHandle,
    options: PDFInternalMappingOptions,
) -> PDFInternalStructureArtifact:
    descriptor = handle.descriptor
    pages: list[PDFInternalPageMap] = []
    fonts: dict[str, PDFFontResourceDescriptor] = {}
    images: dict[str, PDFImageResourceDescriptor] = {}
    masks: dict[str, PDFImageResourceDescriptor] = {}
    xobjects: dict[str, PDFXObjectResource] = {}
    unknown: dict[str, PDFUnknownResource] = {}
    objects: list[PDFIndirectObject] = []
    relations: list[PDFObjectRelation] = []
    content_stream_count = 0
    if options.include_indirect_objects:
        objects.extend(_indirect_objects(handle, options))
    object_ids = {item.object_id for item in objects}
    for page_index in range(handle.page_count):
        page = handle.document.load_page(page_index)
        page_reference = PDFPageReference(
            page_index=page_index,
            page_number=page_index + 1,
            object_reference=_page_object_reference(page),
            provider_reference=f"page:{page_index}",
        )
        streams = _content_streams(handle, page, page_reference, options)
        content_stream_count += len(streams)
        resources = _page_resources(
            handle,
            page,
            page_reference,
            fonts=fonts,
            images=images,
            masks=masks,
            xobjects=xobjects,
            unknown=unknown,
            options=options,
        )
        for stream in streams:
            for resource in resources:
                relations.append(
                    PDFObjectRelation(
                        source_id=stream.stream_reference.stream_id,
                        target_id=resource.resource_id,
                        relation_type=PDFObjectRelationType.USES_RESOURCE,
                    )
                )
        if page_reference.object_reference is not None:
            object_ids.add(page_reference.object_reference.stable_id)
        pages.append(
            PDFInternalPageMap(
                page_reference=page_reference,
                own_resources=resources,
                content_streams=streams,
                operation_references=tuple(
                    operation.operation_reference
                    for stream in streams
                    for operation in stream.operations
                ),
                provenance=_provenance(
                    descriptor,
                    operation="map_internal_structure.page",
                    source=handle.resolved,
                    options=options.safe_options(),
                    page_index=page_index,
                ),
            )
        )
    for relation in relations:
        if relation.source_id.startswith("pdfobj") and relation.source_id not in object_ids:
            objects.append(
                PDFIndirectObject(
                    reference=PDFObjectReference(provider_reference=relation.source_id),
                    object_id=relation.source_id,
                    status=PDFMappingStatus.UNRESOLVED,
                )
            )
    return PDFInternalStructureArtifact(
        artifact_version=ContractVersion("1.0.0"),
        provider=descriptor,
        object_graph=PDFObjectGraph(objects=tuple(objects), relations=tuple(relations)),
        resource_catalog=PDFResourceCatalog(
            fonts=tuple(fonts.values()),
            images=tuple(images.values()),
            masks=tuple(masks.values()),
            xobjects=tuple(xobjects.values()),
            unknown_resources=tuple(unknown.values()),
        ),
        pages=tuple(pages),
        capability_matrix=_structure_capability_matrix(content_stream_count),
        warnings=(
            EixoWarning(
                code="pdf.structure.operations_unavailable",
                message="PyMuPDF mapping does not expose raw content stream operations.",
            ),
        ),
        limitations=descriptor.limitations
        + (
            ProviderLimitation(
                code="content_operations_unavailable",
                message="Content stream operators are not decoded in this phase.",
                scope="content_stream",
            ),
            ProviderLimitation(
                code="paint_order_provider_approximation",
                message="Paint order is limited to content stream/resource order hints.",
                scope="page",
            ),
        ),
        provenance=_provenance(
            descriptor,
            operation="map_internal_structure",
            source=handle.resolved,
            options=options.safe_options(),
        ),
    )


def _indirect_objects(
    handle: PyMuPDFPDFDocumentHandle,
    options: PDFInternalMappingOptions,
) -> tuple[PDFIndirectObject, ...]:
    xref_length = _call_int(handle.document, "xref_length")
    if xref_length is None:
        return ()
    limit = min(xref_length, (options.max_objects or xref_length) + 1)
    objects: list[PDFIndirectObject] = []
    for xref in range(1, limit):
        reference = PDFObjectReference(object_number=xref, generation_number=0, xref=xref)
        summary = _object_summary(handle.document, xref, options.max_raw_summary_size)
        objects.append(
            PDFIndirectObject(
                reference=reference,
                object_id=reference.stable_id,
                object_type=summary.get("Type"),
                subtype=summary.get("Subtype"),
                dictionary_summary=summary,
                has_stream=_has_stream(handle.document, xref),
                status=PDFMappingStatus.RESOLVED,
                provenance=_provenance(
                    handle.descriptor,
                    operation="map_internal_structure.object",
                    source=handle.resolved,
                    options=options.safe_options(),
                ),
            )
        )
    return tuple(objects)


def _content_streams(
    handle: PyMuPDFPDFDocumentHandle,
    page: object,
    page_reference: PDFPageReference,
    options: PDFInternalMappingOptions,
) -> tuple[PDFContentStream, ...]:
    if not options.include_content_streams:
        return ()
    contents = _call(page, "get_contents")
    if contents is None:
        return ()
    if isinstance(contents, int):
        values = (contents,)
    else:
        try:
            values = tuple(int(value) for value in contents)
        except TypeError:
            values = ()
    streams: list[PDFContentStream] = []
    for stream_index, xref in enumerate(values):
        object_reference = PDFObjectReference(
            object_number=xref,
            generation_number=0,
            xref=xref,
        )
        stream_reference = PDFContentStreamReference(
            stream_id=f"pdfstream:{xref}:0",
            page_reference=page_reference,
            object_reference=object_reference,
            stream_index=stream_index,
        )
        streams.append(
            PDFContentStream(
                stream_reference=stream_reference,
                byte_length=_stream_length(handle.document, xref),
                filter_chain=_filter_chain(handle.document, xref),
                decoded_available=PDFMappingStatus.PARTIALLY_RECOVERED,
                operations_available=PDFMappingStatus.UNSUPPORTED_BY_PROVIDER,
                operation_count=0,
                provenance=_provenance(
                    handle.descriptor,
                    operation="map_internal_structure.content_stream",
                    source=handle.resolved,
                    options=options.safe_options(),
                    page_index=page_reference.page_index,
                ),
            )
        )
    return tuple(streams)


def _page_resources(
    handle: PyMuPDFPDFDocumentHandle,
    page: object,
    page_reference: PDFPageReference,
    *,
    fonts: dict[str, PDFFontResourceDescriptor],
    images: dict[str, PDFImageResourceDescriptor],
    masks: dict[str, PDFImageResourceDescriptor],
    xobjects: dict[str, PDFXObjectResource],
    unknown: dict[str, PDFUnknownResource],
    options: PDFInternalMappingOptions,
) -> tuple[PDFResourceReference, ...]:
    if not options.include_resources:
        return ()
    resources: list[PDFResourceReference] = []
    for font in _safe_sequence_call(page, "get_fonts", full=True):
        reference = _font_resource(handle, font, page_reference)
        fonts.setdefault(reference.reference.resource_id, reference)
        resources.append(reference.reference)
    for image in _safe_sequence_call(page, "get_images", full=True):
        reference = _image_resource(handle, image, page_reference)
        images.setdefault(reference.reference.resource_id, reference)
        resources.append(reference.reference)
        mask_reference = reference.soft_mask_reference or reference.mask_reference
        if mask_reference is not None:
            masks.setdefault(
                mask_reference.resource_id,
                _mask_resource(handle, reference, mask_reference, page_reference),
            )
            resources.append(mask_reference)
    for xobject in _safe_sequence_call(page, "get_xobjects"):
        reference = _xobject_resource(handle, xobject, page_reference)
        xobjects.setdefault(reference.reference.resource_id, reference)
        resources.append(reference.reference)
    for item in _safe_sequence_call(page, "get_unknown_resources"):
        reference = _unknown_resource(handle, item, page_reference)
        unknown.setdefault(reference.reference.resource_id, reference)
        resources.append(reference.reference)
    return tuple(resources)


def _font_resource(
    handle: PyMuPDFPDFDocumentHandle,
    item: object,
    page_reference: PDFPageReference,
) -> PDFFontResourceDescriptor:
    values = _tuple(item)
    xref = _int_at(values, 0)
    font_type = _str_at(values, 2)
    base_font = _str_at(values, 3)
    resource_name = _str_at(values, 4) or base_font
    object_reference = _object_reference_from_xref(xref)
    reference = PDFResourceReference(
        resource_id=resource_id(
            PDFResourceType.FONT,
            PDFResourceScope.PAGE,
            resource_name=resource_name,
            object_reference=object_reference,
            page_index=page_reference.page_index,
        ),
        resource_type=PDFResourceType.FONT,
        scope=PDFResourceScope.PAGE,
        resource_name=resource_name,
        page_reference=page_reference,
        object_reference=object_reference,
    )
    return PDFFontResourceDescriptor(
        reference=reference,
        status=PDFMappingStatus.RESOLVED,
        object_reference=object_reference,
        pages_using_resource=(page_reference,),
        font_subtype=font_type,
        base_font=base_font,
        dictionary_summary=_resource_summary("font", values),
        provenance=_provenance(
            handle.descriptor,
            operation="map_internal_structure.font",
            source=handle.resolved,
            options={},
            page_index=page_reference.page_index,
        ),
    )


def _image_resource(
    handle: PyMuPDFPDFDocumentHandle,
    item: object,
    page_reference: PDFPageReference,
) -> PDFImageResourceDescriptor:
    values = _tuple(item)
    xref = _int_at(values, 0)
    smask = _int_at(values, 1)
    width = _int_at(values, 2)
    height = _int_at(values, 3)
    bpc = _int_at(values, 4)
    color_space = _str_at(values, 5)
    resource_name = _str_at(values, 7) or f"image-{xref or page_reference.page_index}"
    object_reference = _object_reference_from_xref(xref)
    reference = PDFResourceReference(
        resource_id=resource_id(
            PDFResourceType.IMAGE,
            PDFResourceScope.PAGE,
            resource_name=resource_name,
            object_reference=object_reference,
            page_index=page_reference.page_index,
        ),
        resource_type=PDFResourceType.IMAGE,
        scope=PDFResourceScope.PAGE,
        resource_name=resource_name,
        page_reference=page_reference,
        object_reference=object_reference,
    )
    mask_reference = None
    if smask and smask > 0:
        mask_object = _object_reference_from_xref(smask)
        mask_reference = PDFResourceReference(
            resource_id=resource_id(
                PDFResourceType.MASK,
                PDFResourceScope.PAGE,
                resource_name=f"{resource_name}-smask",
                object_reference=mask_object,
                page_index=page_reference.page_index,
            ),
            resource_type=PDFResourceType.MASK,
            scope=PDFResourceScope.PAGE,
            resource_name=f"{resource_name}-smask",
            page_reference=page_reference,
            object_reference=mask_object,
            parent_reference=reference.resource_id,
        )
    return PDFImageResourceDescriptor(
        reference=reference,
        status=PDFMappingStatus.RESOLVED,
        object_reference=object_reference,
        pages_using_resource=(page_reference,),
        width=width,
        height=height,
        bits_per_component=bpc,
        filter_chain=(_str_at(values, 8),) if _str_at(values, 8) else (),
        soft_mask_reference=mask_reference,
        dictionary_summary={
            "kind": "image",
            "color_space": color_space or "",
        },
        provenance=_provenance(
            handle.descriptor,
            operation="map_internal_structure.image",
            source=handle.resolved,
            options={},
            page_index=page_reference.page_index,
        ),
    )


def _mask_resource(
    handle: PyMuPDFPDFDocumentHandle,
    image: PDFImageResourceDescriptor,
    mask_reference: PDFResourceReference,
    page_reference: PDFPageReference,
) -> PDFImageResourceDescriptor:
    return PDFImageResourceDescriptor(
        reference=mask_reference,
        status=PDFMappingStatus.PARTIALLY_RECOVERED,
        object_reference=mask_reference.object_reference,
        pages_using_resource=(page_reference,),
        dictionary_summary={"kind": "soft_mask"},
        provenance=_provenance(
            handle.descriptor,
            operation="map_internal_structure.mask",
            source=handle.resolved,
            options={},
            page_index=page_reference.page_index,
        ),
    )


def _xobject_resource(
    handle: PyMuPDFPDFDocumentHandle,
    item: object,
    page_reference: PDFPageReference,
) -> PDFXObjectResource:
    values = _tuple(item)
    xref = _int_at(values, 0)
    resource_name = _str_at(values, 1) or f"xobject-{xref or page_reference.page_index}"
    xobject_type = _str_at(values, 2)
    object_reference = _object_reference_from_xref(xref)
    reference = PDFResourceReference(
        resource_id=resource_id(
            PDFResourceType.FORM_XOBJECT
            if xobject_type == "Form"
            else PDFResourceType.XOBJECT,
            PDFResourceScope.PAGE,
            resource_name=resource_name,
            object_reference=object_reference,
            page_index=page_reference.page_index,
        ),
        resource_type=PDFResourceType.FORM_XOBJECT
        if xobject_type == "Form"
        else PDFResourceType.XOBJECT,
        scope=PDFResourceScope.PAGE,
        resource_name=resource_name,
        page_reference=page_reference,
        object_reference=object_reference,
    )
    return PDFXObjectResource(
        reference=reference,
        status=PDFMappingStatus.RESOLVED,
        object_reference=object_reference,
        pages_using_resource=(page_reference,),
        xobject_type=xobject_type,
        dictionary_summary=_resource_summary("xobject", values),
        provenance=_provenance(
            handle.descriptor,
            operation="map_internal_structure.xobject",
            source=handle.resolved,
            options={},
            page_index=page_reference.page_index,
        ),
    )


def _unknown_resource(
    handle: PyMuPDFPDFDocumentHandle,
    item: object,
    page_reference: PDFPageReference,
) -> PDFUnknownResource:
    values = _tuple(item)
    declared_type = _str_at(values, 0) or "unknown"
    resource_name = _str_at(values, 1) or declared_type
    reference = PDFResourceReference(
        resource_id=resource_id(
            PDFResourceType.UNKNOWN,
            PDFResourceScope.PAGE,
            resource_name=resource_name,
            page_index=page_reference.page_index,
        ),
        resource_type=PDFResourceType.UNKNOWN,
        scope=PDFResourceScope.PAGE,
        resource_name=resource_name,
        page_reference=page_reference,
    )
    return PDFUnknownResource(
        reference=reference,
        status=PDFMappingStatus.PARTIALLY_RECOVERED,
        pages_using_resource=(page_reference,),
        declared_type=declared_type,
        reason="provider_reported_unknown_resource",
        dictionary_summary=_resource_summary("unknown", values),
        provenance=_provenance(
            handle.descriptor,
            operation="map_internal_structure.unknown_resource",
            source=handle.resolved,
            options={},
            page_index=page_reference.page_index,
        ),
    )


def _structure_capability_matrix(
    content_stream_count: int,
) -> tuple[PDFProviderCapabilityMatrixEntry, ...]:
    return (
        PDFProviderCapabilityMatrixEntry(
            feature="indirect_objects",
            support=PDFProviderSupportStatus.PARTIAL,
            strategy="xref_length_and_xref_object_when_available",
        ),
        PDFProviderCapabilityMatrixEntry(
            feature="content_streams",
            support=PDFProviderSupportStatus.PARTIAL
            if content_stream_count
            else PDFProviderSupportStatus.UNKNOWN,
            strategy="page_get_contents",
        ),
        PDFProviderCapabilityMatrixEntry(
            feature="content_operations",
            support=PDFProviderSupportStatus.UNSUPPORTED,
            strategy="operations_deferred_to_later_phase",
            limitation="raw_operator_sequence_not_exposed",
        ),
        PDFProviderCapabilityMatrixEntry(
            feature="fonts",
            support=PDFProviderSupportStatus.PARTIAL,
            strategy="page_get_fonts",
        ),
        PDFProviderCapabilityMatrixEntry(
            feature="images",
            support=PDFProviderSupportStatus.PARTIAL,
            strategy="page_get_images",
        ),
        PDFProviderCapabilityMatrixEntry(
            feature="xobjects",
            support=PDFProviderSupportStatus.PARTIAL,
            strategy="page_get_xobjects_when_available",
        ),
        PDFProviderCapabilityMatrixEntry(
            feature="paint_order",
            support=PDFProviderSupportStatus.PARTIAL,
            strategy="content_stream_order_only",
            limitation="operation_order_unavailable",
        ),
    )


_UNSUPPORTED_COUNT = -1


def _text_count(page: object) -> int | None:
    get_text = getattr(page, "get_text", None)
    if get_text is None:
        return _UNSUPPORTED_COUNT
    try:
        value = get_text("text")
    except Exception:
        return None
    if value is None:
        return 0
    return len(str(value).strip())


def _collection_count(page: object, method_name: str, **kwargs: object) -> int | None:
    method = getattr(page, method_name, None)
    if method is None:
        return _UNSUPPORTED_COUNT
    try:
        value = method(**kwargs)
    except Exception:
        return None
    if value is None:
        return 0
    try:
        return len(value)
    except TypeError:
        return sum(1 for _ in value)


def _state_from_optional_count(count: int | None) -> PDFInspectionState:
    if count == _UNSUPPORTED_COUNT:
        return PDFInspectionState.UNSUPPORTED
    if count is None:
        return PDFInspectionState.UNKNOWN
    return PDFInspectionState.PRESENT if count > 0 else PDFInspectionState.ABSENT


def _call(owner: object, method_name: str, *args: object, **kwargs: object) -> object | None:
    method = getattr(owner, method_name, None)
    if method is None:
        return None
    try:
        return method(*args, **kwargs)
    except Exception:
        return None


def _call_int(owner: object, method_name: str) -> int | None:
    value = _call(owner, method_name)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_sequence_call(
    owner: object,
    method_name: str,
    *args: object,
    **kwargs: object,
) -> tuple[object, ...]:
    value = _call(owner, method_name, *args, **kwargs)
    if value is None:
        return ()
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError:
        return (value,)


def _tuple(value: object) -> tuple[object, ...]:
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, dict):
        return tuple(value.values())
    return (value,)


def _int_at(values: tuple[object, ...], index: int) -> int | None:
    if index >= len(values):
        return None
    try:
        return int(values[index])
    except (TypeError, ValueError):
        return None


def _str_at(values: tuple[object, ...], index: int) -> str | None:
    if index >= len(values):
        return None
    value = values[index]
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _object_reference_from_xref(xref: int | None) -> PDFObjectReference | None:
    if xref is None or xref <= 0:
        return None
    return PDFObjectReference(object_number=xref, generation_number=0, xref=xref)


def _page_object_reference(page: object) -> PDFObjectReference | None:
    for name in ("xref", "xref_id"):
        value = getattr(page, name, None)
        if value is not None:
            try:
                return _object_reference_from_xref(int(value))
            except (TypeError, ValueError):
                return None
    return None


def _object_summary(
    document: object,
    xref: int,
    max_size: int,
) -> dict[str, str]:
    raw = _call(document, "xref_object", xref, compressed=False)
    if raw is None:
        return {}
    text = str(raw)
    if len(text) > max_size:
        text = f"{text[:max_size]}...<truncated>"
    summary: dict[str, str] = {"raw_summary": text}
    for key in ("Type", "Subtype"):
        marker = f"/{key}"
        index = text.find(marker)
        if index >= 0:
            value = text[index + len(marker) :].strip().split(maxsplit=1)[0]
            summary[key] = value.strip("/[]<>()")
    return summary


def _has_stream(document: object, xref: int) -> bool:
    if hasattr(document, "xref_is_stream"):
        value = _call(document, "xref_is_stream", xref)
        return bool(value)
    raw = _call(document, "xref_object", xref, compressed=False)
    return "stream" in str(raw) if raw is not None else False


def _stream_length(document: object, xref: int) -> int | None:
    for key in ("Length", "/Length"):
        value = _call(document, "xref_get_key", xref, key)
        if isinstance(value, tuple) and len(value) >= 2:
            try:
                return int(str(value[1]).strip())
            except ValueError:
                return None
    return None


def _filter_chain(document: object, xref: int) -> tuple[str, ...]:
    value = _call(document, "xref_get_key", xref, "Filter")
    if isinstance(value, tuple) and len(value) >= 2:
        text = str(value[1]).replace("[", " ").replace("]", " ")
        return tuple(part.strip("/") for part in text.split() if part.strip())
    return ()


def _resource_summary(kind: str, values: tuple[object, ...]) -> dict[str, str]:
    return {
        "kind": kind,
        "provider_tuple": "|".join(str(value) for value in values[:12]),
    }


def _backend_version(backend: object | None) -> str | None:
    if backend is None:
        return None
    for name in ("VersionBind", "__version__"):
        value = getattr(backend, name, None)
        if value:
            return str(value)
    return None


def _provenance(
    descriptor: PDFProviderDescriptor,
    *,
    operation: str,
    source: ResolvedDocumentSource,
    options: dict[str, object],
    page_index: int | None = None,
) -> PDFProviderProvenance:
    return PDFProviderProvenance(
        provider_id=descriptor.provider_id,
        provider_version=descriptor.provider_version,
        backend_name=descriptor.backend_name,
        backend_version=descriptor.backend_version,
        operation=operation,
        source_reference=source.source.origin_reference,
        source_hash=source.source.metadata.get("content_hash"),
        page_index=page_index,
        options=options,
    )


def _log(event: str, **fields: str) -> None:
    logger.info(event, extra={"event": event, **fields})


__all__ = [
    "PYMUPDF_PROVIDER_ID",
    "PyMuPDFPDFProvider",
    "create_pymupdf_pdf_provider",
    "register_pymupdf_pdf_provider",
]
