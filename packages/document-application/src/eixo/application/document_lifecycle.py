from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from eixo.core import (
    ArtifactReference,
    ArtifactId,
    ContentHash,
    DetectedDocumentFormat,
    DetectionConfidence,
    DocumentFormat,
    DocumentId,
    DocumentIdentity,
    DocumentNotFoundError,
    DocumentRecord,
    DocumentRepositoryError,
    DocumentStateTransition,
    DocumentStatus,
    DocumentVersionConflictError,
    ErrorResult,
    JobId,
    isoformat_utc,
    utc_now,
)
from eixo.core.serialization import to_jsonable
from eixo.core.warnings import EixoWarning


class DocumentRepository(Protocol):
    async def create(self, document: DocumentRecord) -> None:
        ...

    async def get(self, document_id: DocumentId) -> DocumentRecord:
        ...

    async def update(
        self,
        document: DocumentRecord,
        *,
        expected_version: int | None = None,
    ) -> None:
        ...

    async def append_transition(self, transition: DocumentStateTransition) -> None:
        ...

    async def transitions(
        self,
        document_id: DocumentId,
    ) -> tuple[DocumentStateTransition, ...]:
        ...


@dataclass(frozen=True, slots=True)
class DocumentLifecycle:
    allowed_transitions: dict[DocumentStatus, frozenset[DocumentStatus]]

    @classmethod
    def default(cls) -> "DocumentLifecycle":
        return cls(
            allowed_transitions={
                DocumentStatus.RECEIVED: frozenset(
                    {DocumentStatus.VALIDATED, DocumentStatus.FAILED}
                ),
                DocumentStatus.VALIDATED: frozenset(
                    {DocumentStatus.STORED, DocumentStatus.FAILED}
                ),
                DocumentStatus.STORED: frozenset(
                    {
                        DocumentStatus.PROCESSING,
                        DocumentStatus.FAILED,
                        DocumentStatus.CANCELLED,
                    }
                ),
                DocumentStatus.PROCESSING: frozenset(
                    {
                        DocumentStatus.COMPLETED,
                        DocumentStatus.REVIEW_REQUIRED,
                        DocumentStatus.FAILED,
                        DocumentStatus.CANCELLED,
                    }
                ),
                DocumentStatus.COMPLETED: frozenset({DocumentStatus.PROCESSING}),
                DocumentStatus.REVIEW_REQUIRED: frozenset({DocumentStatus.PROCESSING}),
                DocumentStatus.FAILED: frozenset({DocumentStatus.PROCESSING}),
                DocumentStatus.CANCELLED: frozenset(),
            }
        )

    def transition(
        self,
        document: DocumentRecord,
        *,
        to_status: DocumentStatus,
        reason: str,
        actor: str | None = None,
        job_id: JobId | None = None,
        error: ErrorResult | None = None,
        metadata: dict[str, str] | None = None,
    ) -> tuple[DocumentRecord, DocumentStateTransition]:
        allowed = self.allowed_transitions.get(document.status, frozenset())
        if to_status not in allowed:
            raise DocumentRepositoryError(
                f"Invalid document status transition: {document.status} -> {to_status}",
                public_context={
                    "from_status": document.status.value,
                    "to_status": to_status.value,
                },
            )
        occurred_at = isoformat_utc(utc_now())
        transition = DocumentStateTransition(
            transition_id=f"tr_{uuid4().hex}",
            document_id=document.document_id,
            from_status=document.status,
            to_status=to_status,
            occurred_at=occurred_at,
            reason=reason,
            actor=actor,
            job_id=job_id,
            error=error,
            metadata=metadata or {},
        )
        updated = replace(
            document,
            status=to_status,
            updated_at=occurred_at,
            current_job_id=job_id if job_id is not None else document.current_job_id,
            failure=error if to_status == DocumentStatus.FAILED else document.failure,
            version=document.version + 1,
        )
        return updated, transition


@dataclass(frozen=True, slots=True)
class LocalDocumentRepository:
    base_directory: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_directory", Path(self.base_directory))

    async def create(self, document: DocumentRecord) -> None:
        directory = self._document_directory(document.document_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "document.json"
        if path.exists():
            raise DocumentVersionConflictError("Document already exists")
        self._write_json_atomic(path, to_jsonable(document))

    async def get(self, document_id: DocumentId) -> DocumentRecord:
        path = self._document_directory(document_id) / "document.json"
        if not path.exists():
            raise DocumentNotFoundError(f"Document not found: {document_id}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DocumentRepositoryError("Document record is invalid", cause=exc) from exc
        return document_record_from_dict(payload)

    async def update(
        self,
        document: DocumentRecord,
        *,
        expected_version: int | None = None,
    ) -> None:
        current = await self.get(document.document_id)
        if expected_version is not None and current.version != expected_version:
            raise DocumentVersionConflictError(
                "Document version conflict",
                public_context={
                    "expected_version": expected_version,
                    "actual_version": current.version,
                },
            )
        path = self._document_directory(document.document_id) / "document.json"
        self._write_json_atomic(path, to_jsonable(document))

    async def append_transition(self, transition: DocumentStateTransition) -> None:
        directory = self._document_directory(transition.document_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "transitions.jsonl"
        line = json.dumps(to_jsonable(transition), sort_keys=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

    async def transitions(
        self,
        document_id: DocumentId,
    ) -> tuple[DocumentStateTransition, ...]:
        path = self._document_directory(document_id) / "transitions.jsonl"
        if not path.exists():
            return ()
        try:
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        except OSError as exc:
            raise DocumentRepositoryError("Could not read document transitions", cause=exc) from exc
        return tuple(document_transition_from_dict(json.loads(line)) for line in lines)

    def _document_directory(self, document_id: DocumentId) -> Path:
        return self.base_directory / "documents" / str(document_id)

    def _write_json_atomic(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_directory = self.base_directory / "temporary"
        temporary_directory.mkdir(parents=True, exist_ok=True)
        fd, raw_path = tempfile.mkstemp(prefix="document-", suffix=".json", dir=temporary_directory)
        temp_path = Path(raw_path)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise


def new_document_record(
    *,
    identity: DocumentIdentity,
    detected_format: DetectedDocumentFormat,
    source_metadata: dict[str, str],
    warnings: tuple[EixoWarning, ...],
) -> tuple[DocumentRecord, DocumentStateTransition]:
    document_id = DocumentId.new()
    now = isoformat_utc(utc_now())
    record = DocumentRecord(
        document_id=document_id,
        content_identity=identity,
        status=DocumentStatus.RECEIVED,
        created_at=now,
        updated_at=now,
        source_metadata=source_metadata,
        detected_format=detected_format,
        warnings=warnings,
    )
    transition = DocumentStateTransition(
        transition_id=f"tr_{uuid4().hex}",
        document_id=document_id,
        from_status=None,
        to_status=DocumentStatus.RECEIVED,
        occurred_at=now,
        reason="document_received",
        actor="eixo",
    )
    return record, transition


def document_record_from_dict(payload: dict[str, object]) -> DocumentRecord:
    return DocumentRecord(
        document_id=DocumentId.parse(str(payload["document_id"])),
        content_identity=document_identity_from_dict(dict(payload["content_identity"])),
        status=DocumentStatus(str(payload["status"])),
        created_at=str(payload["created_at"]),
        updated_at=str(payload["updated_at"]),
        original_artifact=artifact_reference_from_dict(payload.get("original_artifact")),
        source_metadata={
            str(k): str(v)
            for k, v in dict(payload.get("source_metadata", {})).items()
        },
        detected_format=detected_format_from_dict(payload.get("detected_format")),
        current_job_id=job_id_from_value(payload.get("current_job_id")),
        warnings=tuple(eixo_warning_from_dict(item) for item in payload.get("warnings", [])),
        failure=error_result_from_dict(payload.get("failure")),
        version=int(payload.get("version", 1)),
    )


def document_transition_from_dict(payload: dict[str, object]) -> DocumentStateTransition:
    from_status = payload.get("from_status")
    return DocumentStateTransition(
        transition_id=str(payload["transition_id"]),
        document_id=DocumentId.parse(str(payload["document_id"])),
        from_status=DocumentStatus(str(from_status)) if from_status is not None else None,
        to_status=DocumentStatus(str(payload["to_status"])),
        occurred_at=str(payload["occurred_at"]),
        reason=str(payload["reason"]),
        actor=optional_str(payload.get("actor")),
        job_id=job_id_from_value(payload.get("job_id")),
        error=error_result_from_dict(payload.get("error")),
        metadata={str(k): str(v) for k, v in dict(payload.get("metadata", {})).items()},
    )


def document_identity_from_dict(payload: dict[str, object]) -> DocumentIdentity:
    return DocumentIdentity(
        content_hash=content_hash_from_dict(dict(payload["content_hash"])),
        size_bytes=int(payload["size_bytes"]),
        detected_format=detected_format_from_dict(payload["detected_format"]),
        identity_version=str(payload.get("identity_version", "1.0")),
    )


def content_hash_from_dict(payload: dict[str, object]) -> ContentHash:
    return ContentHash(str(payload["algorithm"]), str(payload["digest"]))


def detected_format_from_dict(value: object) -> DetectedDocumentFormat:
    payload = dict(value)
    return DetectedDocumentFormat(
        format=DocumentFormat(str(payload["format"])),
        canonical_mime=optional_str(payload.get("canonical_mime")),
        detected_extension=optional_str(payload.get("detected_extension")),
        confidence=DetectionConfidence(str(payload.get("confidence", "unknown"))),
        detection_method=str(payload.get("detection_method", "unknown")),
        declared_mime=optional_str(payload.get("declared_mime")),
        declared_extension=optional_str(payload.get("declared_extension")),
        mime_matches=optional_bool(payload.get("mime_matches")),
        extension_matches=optional_bool(payload.get("extension_matches")),
        warnings=tuple(eixo_warning_from_dict(item) for item in payload.get("warnings", [])),
    )


def artifact_reference_from_dict(value: object) -> ArtifactReference | None:
    if value is None:
        return None
    payload = dict(value)
    return ArtifactReference(
        artifact_id=ArtifactId.parse(str(payload["artifact_id"])),
        kind=str(payload["kind"]),
        media_type=optional_str(payload.get("media_type")),
        storage_backend=optional_str(payload.get("storage_backend")),
        storage_key=optional_str(payload.get("storage_key")),
        content_hash=optional_str(payload.get("content_hash")),
        size_bytes=optional_int(payload.get("size_bytes")),
        original_filename=optional_str(payload.get("original_filename")),
        created_at=optional_str(payload.get("created_at")),
        version=int(payload.get("version", 1)),
        metadata={str(k): str(v) for k, v in dict(payload.get("metadata", {})).items()},
    )


def eixo_warning_from_dict(value: object) -> EixoWarning:
    from eixo.core import Severity

    payload = dict(value)
    return EixoWarning(
        code=str(payload["code"]),
        message=str(payload["message"]),
        severity=Severity(str(payload.get("severity", "warning"))),
        scope=optional_str(payload.get("scope")),
        details=dict(payload.get("details", {})),
    )


def error_result_from_dict(value: object) -> ErrorResult | None:
    if value is None:
        return None
    from eixo.core import ErrorCategory

    payload = dict(value)
    return ErrorResult(
        code=str(payload["code"]),
        message=str(payload["message"]),
        category=ErrorCategory(str(payload["category"])),
        retryable=bool(payload.get("retryable", False)),
        details=dict(payload.get("details", {})),
    )


def job_id_from_value(value: object) -> JobId | None:
    if value is None:
        return None
    return JobId.parse(str(value))


def optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


__all__ = [
    "DocumentLifecycle",
    "DocumentRepository",
    "LocalDocumentRepository",
    "document_record_from_dict",
    "document_transition_from_dict",
    "new_document_record",
]
