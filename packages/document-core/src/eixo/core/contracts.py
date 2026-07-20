from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from eixo.core.enums import ErrorCategory, JobStatus, ProcessingStatus, ResultStatus
from eixo.core.ids import ArtifactId, CorrelationId, DocumentId, JobId, TenantId
from eixo.core.metadata import ExecutionMetadata
from eixo.core.serialization import Serializable
from eixo.core.versions import ContractVersion
from eixo.core.warnings import EixoWarning


@dataclass(frozen=True, slots=True)
class DocumentSource(Serializable):
    source_type: str
    filename: str | None = None
    declared_media_type: str | None = None
    size: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.size is not None and self.size < 0:
            raise ValueError("size cannot be negative")


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
    metadata: dict[str, str] = field(default_factory=dict)


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
    options: dict[str, Any] = field(default_factory=dict)
    requested_capability: str | None = None
    processing_profile: str | None = None
    correlation_id: CorrelationId = field(default_factory=CorrelationId.new)
    tenant_id: TenantId | None = None


@dataclass(frozen=True, slots=True)
class ParseResult(Serializable):
    document_id: DocumentId
    status: ResultStatus
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
