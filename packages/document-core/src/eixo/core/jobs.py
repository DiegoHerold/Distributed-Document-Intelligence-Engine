from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from eixo.core.contracts import ErrorResult, ProcessingResult
from eixo.core.enums import JobStatus
from eixo.core.ids import DocumentId, JobId
from eixo.core.serialization import Serializable
from eixo.core.warnings import EixoWarning


@dataclass(frozen=True, slots=True)
class JobRecord(Serializable):
    job_id: JobId
    operation: str
    status: JobStatus
    request: dict[str, Any]
    document_id: DocumentId | None = None
    stage: str | None = None
    progress: float = 0.0
    result_available: bool = False
    result_reference: str | None = None
    error: ErrorResult | None = None
    warnings: tuple[EixoWarning, ...] = ()
    created_at: str | None = None
    queued_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    cancel_requested_at: str | None = None
    cancelled_at: str | None = None
    updated_at: str | None = None
    version: int = 1
    metadata: dict[str, str] = field(default_factory=dict)
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.operation.strip():
            raise ValueError("operation is required")
        if self.progress < 0.0 or self.progress > 1.0:
            raise ValueError("progress must be between 0 and 1")
        if self.version <= 0:
            raise ValueError("version must be positive")
        if self.schema_version <= 0:
            raise ValueError("schema_version must be positive")


@dataclass(frozen=True, slots=True)
class JobStoredResult(Serializable):
    job_id: JobId
    result: ProcessingResult
    stored_at: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version <= 0:
            raise ValueError("schema_version must be positive")


@dataclass(frozen=True, slots=True)
class JobQuery(Serializable):
    status: JobStatus | None = None
    document_id: DocumentId | None = None
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.offset < 0:
            raise ValueError("offset cannot be negative")


@dataclass(frozen=True, slots=True)
class JobPage(Serializable):
    items: tuple[JobRecord, ...]
    total: int
    limit: int
    offset: int


__all__ = ["JobPage", "JobQuery", "JobRecord", "JobStoredResult"]
