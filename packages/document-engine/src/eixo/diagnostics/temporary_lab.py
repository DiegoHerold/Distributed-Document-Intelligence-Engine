from __future__ import annotations

import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path, PurePath
from typing import Any, Protocol
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from eixo.core import EmptyFileError, FileTooLargeError, ValidationError
from eixo.diagnostics.pdf_validation_lab import PDFValidationBatchResult, validate_pdf_batch


class TemporaryDiagnosticSessionStatus(StrEnum):
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"
    EXPIRED = "expired"


class TemporaryDiagnosticDocumentStatus(StrEnum):
    QUEUED = "queued"
    INSPECTING = "inspecting"
    EXTRACTING = "extracting"
    BUILDING_SCENE = "building_scene"
    GENERATING_DIAGNOSTIC = "generating_diagnostic"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class TemporaryDiagnosticConfig:
    root_directory: Path = field(
        default_factory=lambda: Path(tempfile.gettempdir())
        / "eixo"
        / "temporary-diagnostics"
    )
    heartbeat_interval: float = 25.0
    inactive_session_grace_period: float = 90.0
    maximum_session_lifetime: float = 60.0 * 60.0 * 2.0
    cleanup_interval: float = 30.0
    max_upload_size: int = 10 * 1024 * 1024

    def __post_init__(self) -> None:
        if self.heartbeat_interval <= 0:
            raise ValueError("heartbeat_interval must be positive")
        if self.inactive_session_grace_period <= 0:
            raise ValueError("inactive_session_grace_period must be positive")
        if self.maximum_session_lifetime <= 0:
            raise ValueError("maximum_session_lifetime must be positive")
        if self.cleanup_interval <= 0:
            raise ValueError("cleanup_interval must be positive")
        if self.max_upload_size <= 0:
            raise ValueError("max_upload_size must be positive")


@dataclass(slots=True)
class TemporaryDiagnosticDocument:
    document_id: str
    session_id: str
    filename: str
    size: int
    upload_path: Path
    status: TemporaryDiagnosticDocumentStatus = TemporaryDiagnosticDocumentStatus.QUEUED
    stage: str = "aguardando"
    progress: float = 0.0
    page_count: int = 0
    warning_count: int = 0
    limitation_count: int = 0
    error: str | None = None
    report_directory: Path | None = None
    html_report_path: Path | None = None
    export_path: Path | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "size": self.size,
            "status": self.status.value,
            "stage": self.stage,
            "progress": self.progress,
            "page_count": self.page_count,
            "warning_count": self.warning_count,
            "limitation_count": self.limitation_count,
            "error": self.error,
            "report_url": (
                f"/lab/sessions/{self.session_id}/documents/"
                f"{self.document_id}/files/report.html"
                if self.html_report_path is not None
                else None
            ),
        }


@dataclass(slots=True)
class DiagnosticTemporarySession:
    session_id: str
    root_directory: Path
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    status: TemporaryDiagnosticSessionStatus = TemporaryDiagnosticSessionStatus.ACTIVE
    uploaded_document_ids: list[str] = field(default_factory=list)
    temporary_artifact_ids: list[str] = field(default_factory=list)
    documents: dict[str, TemporaryDiagnosticDocument] = field(default_factory=dict)

    @property
    def uploads_directory(self) -> Path:
        return self.root_directory / "uploads"

    @property
    def artifacts_directory(self) -> Path:
        return self.root_directory / "artifacts"

    @property
    def previews_directory(self) -> Path:
        return self.root_directory / "previews"

    @property
    def reports_directory(self) -> Path:
        return self.root_directory / "reports"

    @property
    def runtime_directory(self) -> Path:
        return self.root_directory / "runtime"

    def touch(self, now: datetime | None = None) -> None:
        self.last_activity_at = now or _now()

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity_at": self.last_activity_at.isoformat(),
            "status": self.status.value,
            "uploaded_document_ids": list(self.uploaded_document_ids),
            "temporary_artifact_ids": list(self.temporary_artifact_ids),
            "expires_at": self.expires_at.isoformat(),
            "heartbeat_interval": None,
            "documents": [document.to_public_dict() for document in self.documents.values()],
        }


class TemporaryDiagnosticEngine(Protocol):
    async def __aenter__(self) -> Any:
        ...

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        ...


TemporaryDiagnosticEngineFactory = Callable[[Path], TemporaryDiagnosticEngine]


class TemporaryDiagnosticStore:
    def __init__(self, config: TemporaryDiagnosticConfig | None = None) -> None:
        self.config = config or TemporaryDiagnosticConfig()
        self.root_directory = self.config.root_directory.resolve()
        self.sessions: dict[str, DiagnosticTemporarySession] = {}
        self._last_cleanup = 0.0

    def create_session(self) -> DiagnosticTemporarySession:
        self.cleanup_due()
        session_id = f"diagtmp_{uuid4().hex}"
        now = _now()
        session = DiagnosticTemporarySession(
            session_id=session_id,
            root_directory=self.root_directory / session_id,
            created_at=now,
            last_activity_at=now,
            expires_at=now + timedelta(seconds=self.config.maximum_session_lifetime),
        )
        for directory in (
            session.uploads_directory,
            session.artifacts_directory,
            session.previews_directory,
            session.reports_directory,
            session.runtime_directory,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> DiagnosticTemporarySession:
        self.cleanup_due()
        session = self.sessions.get(session_id)
        if session is None or session.status is TemporaryDiagnosticSessionStatus.CLOSED:
            raise ValidationError("Temporary diagnostic session was not found")
        session.touch()
        return session

    def heartbeat(self, session_id: str) -> DiagnosticTemporarySession:
        session = self.get_session(session_id)
        session.touch()
        return session

    def save_upload(
        self,
        session_id: str,
        *,
        filename: str | None,
        content: bytes,
    ) -> TemporaryDiagnosticDocument:
        session = self.get_session(session_id)
        safe_name = sanitize_temporary_filename(filename)
        validate_pdf_upload(content, max_size=self.config.max_upload_size)
        document_id = f"doc_{uuid4().hex}"
        upload_path = session.uploads_directory / f"{document_id}.pdf"
        upload_path.write_bytes(content)
        document = TemporaryDiagnosticDocument(
            document_id=document_id,
            session_id=session_id,
            filename=safe_name,
            size=len(content),
            upload_path=upload_path,
        )
        session.documents[document_id] = document
        session.uploaded_document_ids.append(document_id)
        session.touch()
        return document

    async def process_document(
        self,
        session_id: str,
        document_id: str,
        *,
        profile: str,
        engine_factory: TemporaryDiagnosticEngineFactory,
    ) -> TemporaryDiagnosticDocument:
        session = self.get_session(session_id)
        document = self._get_document(session, document_id)
        if profile not in {"visual", "full_fidelity"}:
            raise ValidationError("profile must be visual or full_fidelity")
        document.status = TemporaryDiagnosticDocumentStatus.INSPECTING
        document.stage = "inspecionando"
        document.progress = 0.15
        try:
            document.status = TemporaryDiagnosticDocumentStatus.EXTRACTING
            document.stage = "extraindo"
            document.progress = 0.35
            async with engine_factory(session.runtime_directory) as engine:
                document.status = TemporaryDiagnosticDocumentStatus.BUILDING_SCENE
                document.stage = "montando cena"
                document.progress = 0.6
                result = await validate_pdf_batch(
                    engine,
                    document.upload_path,
                    output_directory=session.reports_directory,
                    profile=profile,
                    diagnostic_preview=True,
                    temporary_mode=True,
                )
            document.status = TemporaryDiagnosticDocumentStatus.GENERATING_DIAGNOSTIC
            document.stage = "gerando diagnostico"
            document.progress = 0.85
            self._apply_batch_result(document, result)
        except Exception as exc:
            document.status = TemporaryDiagnosticDocumentStatus.FAILED
            document.stage = "falhou"
            document.progress = 1.0
            document.error = _safe_error(exc)
        session.touch()
        return document

    def remove_document(self, session_id: str, document_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        document = self._get_document(session, document_id)
        document.status = TemporaryDiagnosticDocumentStatus.CANCELLED
        document.stage = "cancelado"
        document.upload_path.unlink(missing_ok=True)
        if document.report_directory is not None:
            _remove_path(document.report_directory)
            parent = document.report_directory.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        session.documents.pop(document_id, None)
        session.uploaded_document_ids = [
            value for value in session.uploaded_document_ids if value != document_id
        ]
        session.touch()
        return session.to_public_dict()

    def close_session(
        self,
        session_id: str,
        *,
        expired: bool = False,
    ) -> dict[str, Any]:
        session = self.sessions.get(session_id)
        if session is None:
            return {"session_id": session_id, "status": "closed"}
        session.status = (
            TemporaryDiagnosticSessionStatus.EXPIRED
            if expired
            else TemporaryDiagnosticSessionStatus.CLOSING
        )
        _remove_path(session.root_directory)
        session.status = TemporaryDiagnosticSessionStatus.CLOSED
        self.sessions.pop(session_id, None)
        return {"session_id": session_id, "status": "closed"}

    def cleanup_due(self) -> None:
        current = time.monotonic()
        if current - self._last_cleanup < self.config.cleanup_interval:
            return
        self._last_cleanup = current
        TemporaryDiagnosticSessionCleaner(self).cleanup()

    def cleanup_expired(self) -> list[str]:
        return TemporaryDiagnosticSessionCleaner(self).cleanup()

    def export_document(
        self,
        session_id: str,
        document_id: str,
        *,
        include_original: bool = False,
    ) -> Path:
        session = self.get_session(session_id)
        document = self._get_document(session, document_id)
        if document.report_directory is None or not document.report_directory.exists():
            raise ValidationError("Document diagnostic report is not available")
        export_path = session.reports_directory / f"{document.document_id}-diagnostic.zip"
        with ZipFile(export_path, "w", compression=ZIP_DEFLATED) as archive:
            for item in document.report_directory.rglob("*"):
                if item.is_file():
                    archive.write(item, item.relative_to(document.report_directory))
            if include_original:
                archive.write(document.upload_path, Path("original") / document.filename)
        document.export_path = export_path
        session.touch()
        return export_path

    def resolve_report_file(
        self,
        session_id: str,
        document_id: str,
        relative_path: str,
    ) -> Path:
        session = self.get_session(session_id)
        document = self._get_document(session, document_id)
        if document.report_directory is None:
            raise ValidationError("Document diagnostic report is not available")
        resolved = _safe_child(document.report_directory, relative_path)
        if not resolved.is_file():
            raise ValidationError("Diagnostic report file was not found")
        return resolved

    def _get_document(
        self,
        session: DiagnosticTemporarySession,
        document_id: str,
    ) -> TemporaryDiagnosticDocument:
        document = session.documents.get(document_id)
        if document is None:
            raise ValidationError("Temporary diagnostic document was not found")
        return document

    def _apply_batch_result(
        self,
        document: TemporaryDiagnosticDocument,
        result: PDFValidationBatchResult,
    ) -> None:
        validation = result.documents[0] if result.documents else None
        if validation is None:
            document.status = TemporaryDiagnosticDocumentStatus.FAILED
            document.stage = "falhou"
            document.error = "No diagnostic result was produced"
            document.progress = 1.0
            return
        if validation.state.value == "completed_with_warnings":
            document.status = TemporaryDiagnosticDocumentStatus.COMPLETED_WITH_WARNINGS
        elif validation.state.value == "completed":
            document.status = TemporaryDiagnosticDocumentStatus.COMPLETED
        else:
            document.status = TemporaryDiagnosticDocumentStatus.FAILED
            document.error = validation.error
        document.stage = document.status.value
        document.progress = 1.0
        document.page_count = validation.page_count
        document.warning_count = validation.warning_count
        document.limitation_count = validation.limitation_count
        document.report_directory = validation.output_directory
        document.html_report_path = validation.html_report_path


class TemporaryDiagnosticSessionCleaner:
    def __init__(self, store: TemporaryDiagnosticStore) -> None:
        self.store = store

    def cleanup(self, now: datetime | None = None) -> list[str]:
        current = now or _now()
        removed: list[str] = []
        for session_id, session in list(self.store.sessions.items()):
            inactive_for = (current - session.last_activity_at).total_seconds()
            expired = current >= session.expires_at
            abandoned = inactive_for >= self.store.config.inactive_session_grace_period
            if expired or abandoned:
                self.store.close_session(session_id, expired=True)
                removed.append(session_id)
        removed.extend(self.cleanup_orphans(current))
        return removed

    def cleanup_orphans(self, now: datetime | None = None) -> list[str]:
        current = now or _now()
        removed: list[str] = []
        root = self.store.root_directory
        if not root.exists():
            return removed
        active = set(self.store.sessions)
        for item in root.iterdir():
            if not item.is_dir() or item.name in active:
                continue
            age = current.timestamp() - item.stat().st_mtime
            if age >= self.store.config.maximum_session_lifetime:
                _remove_path(item)
                removed.append(item.name)
        return removed


def validate_pdf_upload(content: bytes, *, max_size: int) -> None:
    if not content:
        raise EmptyFileError("Uploaded PDF cannot be empty")
    if len(content) > max_size:
        raise FileTooLargeError("Uploaded PDF exceeds configured maximum size")
    if content[:1024].find(b"%PDF-") < 0:
        raise ValidationError("Uploaded file is not a valid PDF")


def sanitize_temporary_filename(value: str | None) -> str:
    if value is None or not value.strip():
        return "document.pdf"
    name = PurePath(value.replace("\\", "/")).name.strip()
    if not name or name in {".", ".."} or "\x00" in name:
        raise ValidationError("Invalid upload filename")
    cleaned = "".join(char if char.isalnum() or char in "._- ()" else "_" for char in name)
    if not cleaned.lower().endswith(".pdf"):
        cleaned = f"{cleaned}.pdf"
    return cleaned


def _safe_child(root: Path, relative_path: str) -> Path:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    if not normalized or ".." in Path(normalized).parts:
        raise ValidationError("Invalid diagnostic report path")
    resolved_root = root.resolve()
    resolved = (resolved_root / normalized).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValidationError("Invalid diagnostic report path")
    return resolved


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def _safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _now() -> datetime:
    return datetime.now(UTC)


__all__ = [
    "DiagnosticTemporarySession",
    "TemporaryDiagnosticConfig",
    "TemporaryDiagnosticDocument",
    "TemporaryDiagnosticDocumentStatus",
    "TemporaryDiagnosticEngineFactory",
    "TemporaryDiagnosticSessionCleaner",
    "TemporaryDiagnosticSessionStatus",
    "TemporaryDiagnosticStore",
    "sanitize_temporary_filename",
    "validate_pdf_upload",
]
