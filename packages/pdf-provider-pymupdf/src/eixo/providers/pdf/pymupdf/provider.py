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
    PDFDocumentHandle,
    PDFEncryptionState,
    PDFOpenOptions,
    PDFPageGeometry,
    PDFPageHandle,
    PDFProbeOptions,
    PDFProbeResult,
    PDFProbeStatus,
    PDFProviderCapabilities,
    PDFProviderDescriptor,
    PDFProviderProvenance,
    PDFProviderRegistry,
    PDFSupportLevel,
    ProviderLimitation,
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
            supports_content_streams=PDFSupportLevel.UNSUPPORTED,
            supports_object_references=PDFSupportLevel.UNSUPPORTED,
            supports_embedded_fonts=PDFSupportLevel.UNSUPPORTED,
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
            width = rect[2] - rect[0] if rect is not None else 0.0
            height = rect[3] - rect[1] if rect is not None else 0.0
            return PDFPageGeometry(
                page_index=self.index,
                page_number=self.page_number,
                width=width,
                height=height,
                rotation=rotation,
                media_box=media_box,
                crop_box=crop_box,
                provenance=_provenance(
                    self.document_handle.descriptor,
                    operation="get_basic_geometry",
                    source=self.document_handle.resolved,
                    options=self.document_handle.options.safe_options(),
                    page_index=self.index,
                ),
            )


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
