from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from eixo.core.contracts import ArtifactReference, ErrorResult
from eixo.core.enums import DocumentStatus
from eixo.core.ids import DocumentId, JobId
from eixo.core.ingestion import DetectedDocumentFormat, DocumentIdentity
from eixo.core.serialization import Serializable
from eixo.core.warnings import EixoWarning


@dataclass(frozen=True, slots=True)
class DocumentStateTransition(Serializable):
    transition_id: str
    document_id: DocumentId
    from_status: DocumentStatus | None
    to_status: DocumentStatus
    occurred_at: str
    reason: str
    actor: str | None = None
    job_id: JobId | None = None
    error: ErrorResult | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.transition_id.strip():
            raise ValueError("transition_id is required")
        if not self.reason.strip():
            raise ValueError("reason is required")


@dataclass(frozen=True, slots=True)
class DocumentRecord(Serializable):
    document_id: DocumentId
    content_identity: DocumentIdentity
    status: DocumentStatus
    created_at: str
    updated_at: str
    original_artifact: ArtifactReference | None = None
    source_metadata: dict[str, str] = field(default_factory=dict)
    detected_format: DetectedDocumentFormat | None = None
    current_job_id: JobId | None = None
    warnings: tuple[EixoWarning, ...] = ()
    failure: ErrorResult | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise ValueError("version must be positive")


@dataclass(frozen=True, slots=True)
class DocumentIngestionResult(Serializable):
    document_id: DocumentId
    status: DocumentStatus
    identity: DocumentIdentity
    original_artifact: ArtifactReference
    detected_format: DetectedDocumentFormat
    size_bytes: int
    warnings: tuple[EixoWarning, ...] = ()
    transitions: tuple[DocumentStateTransition, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "DocumentIngestionResult",
    "DocumentRecord",
    "DocumentStateTransition",
]
