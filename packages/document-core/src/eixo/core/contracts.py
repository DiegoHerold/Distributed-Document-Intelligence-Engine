from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, ClassVar, Literal

from eixo.core.enums import ErrorCategory, JobStatus, ProcessingStatus, ResultStatus
from eixo.core.ids import ArtifactId, CorrelationId, DocumentId, JobId, TenantId
from eixo.core.metadata import ExecutionMetadata
from eixo.core.serialization import Serializable, to_jsonable
from eixo.core.versions import ContractVersion
from eixo.core.warnings import EixoWarning


@dataclass(frozen=True, slots=True)
class DocumentSource(Serializable):
    _kind: ClassVar[str] = "document"

    source_type: str
    filename: str | None = None
    declared_media_type: str | None = None
    declared_extension: str | None = None
    size: int | None = None
    origin_reference: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        filename: str | None = None,
        declared_media_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> "LocalPathSource":
        path_value = Path(path)
        return LocalPathSource(
            path=path_value,
            filename=filename or path_value.name,
            declared_media_type=declared_media_type,
            declared_extension=normalize_extension(path_value.suffix),
            origin_reference=str(path),
            metadata=metadata or {},
        )

    @classmethod
    def from_bytes(
        cls,
        content: bytes | bytearray | memoryview,
        *,
        filename: str | None = None,
        declared_mime: str | None = None,
        declared_media_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> "BytesSource":
        value = bytes(content)
        return BytesSource(
            content=value,
            filename=filename,
            declared_media_type=declared_media_type or declared_mime,
            declared_extension=extension_from_filename(filename),
            size=len(value),
            metadata=metadata or {},
        )

    @classmethod
    def from_stream(
        cls,
        stream: BinaryIO,
        *,
        filename: str | None = None,
        declared_mime: str | None = None,
        declared_media_type: str | None = None,
        size: int | None = None,
        close_on_cleanup: bool = False,
        metadata: dict[str, str] | None = None,
    ) -> "StreamSource":
        return StreamSource(
            stream=stream,
            filename=filename,
            declared_media_type=declared_media_type or declared_mime,
            declared_extension=extension_from_filename(filename),
            size=size,
            close_on_cleanup=close_on_cleanup,
            metadata=metadata or {},
        )

    def __post_init__(self) -> None:
        if self.size is not None and self.size < 0:
            raise ValueError("size cannot be negative")
        if self.declared_extension is not None and not self.declared_extension.startswith("."):
            raise ValueError("declared_extension must start with '.'")


@dataclass(frozen=True, slots=True)
class LocalPathSource(DocumentSource):
    path: Path = Path()
    source_type: Literal["local_path"] = "local_path"

    def __post_init__(self) -> None:
        DocumentSource.__post_init__(self)
        if not self.path:
            raise ValueError("path is required")


@dataclass(frozen=True, slots=True)
class BytesSource(DocumentSource):
    content: bytes = b""
    source_type: Literal["bytes"] = "bytes"

    def __post_init__(self) -> None:
        DocumentSource.__post_init__(self)
        if self.size is not None and self.size != len(self.content):
            raise ValueError("size must match content length")


@dataclass(frozen=True, slots=True)
class StreamSource(DocumentSource):
    stream: BinaryIO | None = field(default=None, repr=False, compare=False)
    close_on_cleanup: bool = False
    source_type: Literal["stream"] = "stream"

    def __post_init__(self) -> None:
        DocumentSource.__post_init__(self)
        if self.stream is None:
            raise ValueError("stream is required")
        if not hasattr(self.stream, "read"):
            raise ValueError("stream must be readable")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "filename": self.filename,
            "declared_media_type": self.declared_media_type,
            "declared_extension": self.declared_extension,
            "size": self.size,
            "origin_reference": self.origin_reference,
            "close_on_cleanup": self.close_on_cleanup,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ArtifactReferenceSource(DocumentSource):
    artifact_id: ArtifactId | None = None
    source_type: Literal["artifact_reference"] = "artifact_reference"

    def __post_init__(self) -> None:
        DocumentSource.__post_init__(self)
        if self.artifact_id is None:
            raise ValueError("artifact_id is required")


@dataclass(frozen=True, slots=True)
class ArtifactReference(Serializable):
    artifact_id: ArtifactId
    kind: str
    media_type: str | None = None
    storage_backend: str | None = None
    storage_key: str | None = None
    content_hash: str | None = None
    size_bytes: int | None = None
    original_filename: str | None = None
    created_at: str | None = None
    version: int = 1
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("size_bytes cannot be negative")
        if self.version <= 0:
            raise ValueError("version must be positive")


@dataclass(frozen=True, slots=True)
class ErrorResult(Serializable):
    code: str
    message: str
    category: ErrorCategory
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    correlation_id: CorrelationId | None = None


@dataclass(frozen=True, slots=True)
class InspectionRequest(Serializable):
    source: DocumentSource
    options: dict[str, Any] = field(default_factory=dict)
    correlation_id: CorrelationId = field(default_factory=CorrelationId.new)
    tenant_id: TenantId | None = None


@dataclass(frozen=True, slots=True)
class InspectionResult(Serializable):
    document_id: DocumentId | None
    detected_format: str | None
    declared_media_type: str | None
    detected_media_type: str | None
    size: int | None
    status: ResultStatus
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[EixoWarning, ...] = ()
    execution_metadata: ExecutionMetadata | None = None


@dataclass(frozen=True, slots=True)
class ParseRequest(Serializable):
    source: DocumentSource
    profile: str | None = None
    page_selection: tuple[int, ...] | None = None
    options: dict[str, Any] = field(default_factory=dict)
    requested_capability: str | None = None
    processing_profile: str | None = None
    correlation_id: CorrelationId = field(default_factory=CorrelationId.new)
    tenant_id: TenantId | None = None

    def __post_init__(self) -> None:
        if self.page_selection is not None:
            if not self.page_selection:
                raise ValueError("page_selection cannot be empty")
            if any(page <= 0 for page in self.page_selection):
                raise ValueError("page_selection uses 1-based positive page numbers")


@dataclass(frozen=True, slots=True)
class ParseResult(Serializable):
    document_id: DocumentId
    status: ResultStatus
    format: str | None = None
    profile: str | None = None
    artifact_reference: ArtifactReference | None = None
    scene_artifact_reference: ArtifactReference | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    page_count: int | None = None
    statistics: dict[str, Any] = field(default_factory=dict)
    fidelity_summary: dict[str, Any] = field(default_factory=dict)
    editability_summary: dict[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)
    artifacts: tuple[ArtifactReference, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    errors: tuple[ErrorResult, ...] = ()
    execution_metadata: ExecutionMetadata | None = None


@dataclass(frozen=True, slots=True)
class ProcessingRequest(Serializable):
    source: DocumentSource
    profile: str = "balanced"
    policies: dict[str, Any] = field(default_factory=dict)
    schema_reference: str | None = None
    template_reference: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    correlation_id: CorrelationId = field(default_factory=CorrelationId.new)
    tenant_id: TenantId | None = None
    contract_version: ContractVersion = field(default_factory=lambda: ContractVersion("1.0.0"))


@dataclass(frozen=True, slots=True)
class ProcessingResult(Serializable):
    job_id: JobId
    document_id: DocumentId | None
    status: ProcessingStatus
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: tuple[ArtifactReference, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    errors: tuple[ErrorResult, ...] = ()
    execution_metadata: ExecutionMetadata | None = None
    contract_version: ContractVersion = field(default_factory=lambda: ContractVersion("1.0.0"))


@dataclass(frozen=True, slots=True)
class JobResult(Serializable):
    job_id: JobId
    status: JobStatus
    progress: float = 0.0
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    result_reference: str | None = None
    error: ErrorResult | None = None
    warnings: tuple[EixoWarning, ...] = ()

    def __post_init__(self) -> None:
        if self.progress < 0.0 or self.progress > 1.0:
            raise ValueError("progress must be between 0 and 1")


def normalize_extension(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    return cleaned if cleaned.startswith(".") else f".{cleaned}"


def extension_from_filename(filename: str | None) -> str | None:
    if filename is None:
        return None
    return normalize_extension(Path(filename).suffix)
