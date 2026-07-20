from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from eixo.application.document_lifecycle import (
    artifact_reference_from_dict,
    error_result_from_dict,
    eixo_warning_from_dict,
)
from eixo.core import (
    ErrorCategory,
    ErrorResult,
    InvalidJobTransitionError,
    JobAlreadyExistsError,
    JobConcurrencyError,
    JobId,
    JobNotFoundError,
    JobPage,
    JobPersistenceError,
    JobQuery,
    JobRecord,
    JobRecoveryError,
    JobResult,
    JobResultUnavailableError,
    JobSerializationError,
    JobStatus,
    JobStoredResult,
    ProcessingResult,
    ProcessingStatus,
    isoformat_utc,
    utc_now,
)
from eixo.core.ids import DocumentId
from eixo.core.serialization import to_jsonable

SCHEMA_VERSION = 1
TERMINAL_STATUSES = {
    JobStatus.COMPLETED,
    JobStatus.REVIEW_REQUIRED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
}


class JobStore(Protocol):
    async def create(self, job: JobRecord) -> None:
        ...

    async def get(self, job_id: JobId) -> JobRecord:
        ...

    async def update(self, job: JobRecord, *, expected_version: int | None = None) -> None:
        ...

    async def list(self, query: JobQuery | None = None) -> JobPage:
        ...

    async def save_result(self, result: JobStoredResult) -> None:
        ...

    async def get_result(self, job_id: JobId) -> JobStoredResult:
        ...


@dataclass(frozen=True, slots=True)
class JobTransitionPolicy:
    allowed_transitions: dict[JobStatus, frozenset[JobStatus]]

    @classmethod
    def default(cls) -> "JobTransitionPolicy":
        return cls(
            allowed_transitions={
                JobStatus.CREATED: frozenset({JobStatus.QUEUED, JobStatus.CANCELLED}),
                JobStatus.QUEUED: frozenset(
                    {JobStatus.RUNNING, JobStatus.CANCEL_REQUESTED, JobStatus.FAILED}
                ),
                JobStatus.RUNNING: frozenset(
                    {
                        JobStatus.COMPLETED,
                        JobStatus.REVIEW_REQUIRED,
                        JobStatus.FAILED,
                        JobStatus.CANCEL_REQUESTED,
                        JobStatus.CANCELLED,
                    }
                ),
                JobStatus.CANCEL_REQUESTED: frozenset(
                    {JobStatus.CANCELLED, JobStatus.COMPLETED, JobStatus.FAILED}
                ),
                JobStatus.COMPLETED: frozenset(),
                JobStatus.REVIEW_REQUIRED: frozenset(),
                JobStatus.FAILED: frozenset(),
                JobStatus.CANCELLED: frozenset(),
            }
        )

    def transition(
        self,
        record: JobRecord,
        *,
        to_status: JobStatus,
        progress: float | None = None,
        stage: str | None = None,
        error: ErrorResult | None = None,
        result_available: bool | None = None,
    ) -> JobRecord:
        allowed = self.allowed_transitions.get(record.status, frozenset())
        if to_status not in allowed and to_status != record.status:
            raise InvalidJobTransitionError(
                f"Invalid job status transition: {record.status} -> {to_status}",
                public_context={
                    "from_status": record.status.value,
                    "to_status": to_status.value,
                },
            )
        now = isoformat_utc(utc_now())
        return replace(
            record,
            status=to_status,
            stage=stage if stage is not None else record.stage,
            progress=progress if progress is not None else record.progress,
            error=error if error is not None else record.error,
            result_available=(
                result_available if result_available is not None else record.result_available
            ),
            queued_at=(
                now
                if to_status == JobStatus.QUEUED and record.queued_at is None
                else record.queued_at
            ),
            started_at=(
                now
                if to_status == JobStatus.RUNNING and record.started_at is None
                else record.started_at
            ),
            finished_at=now if to_status in TERMINAL_STATUSES else record.finished_at,
            cancel_requested_at=(
                now
                if to_status == JobStatus.CANCEL_REQUESTED
                and record.cancel_requested_at is None
                else record.cancel_requested_at
            ),
            cancelled_at=now if to_status == JobStatus.CANCELLED else record.cancelled_at,
            updated_at=now,
            version=record.version + 1,
        )


@dataclass(frozen=True, slots=True)
class SQLiteJobStore:
    database_path: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "database_path", Path(self.database_path))
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    async def create(self, job: JobRecord) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        job_id, document_id, operation, status, stage, request_json,
                        progress, result_available, result_reference, error_json,
                        warnings_json, created_at, queued_at, started_at, finished_at,
                        cancel_requested_at, cancelled_at, updated_at, version,
                        metadata_json, schema_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    job_to_row(job),
                )
        except sqlite3.IntegrityError as exc:
            raise JobAlreadyExistsError(f"Job already exists: {job.job_id}") from exc
        except sqlite3.Error as exc:
            raise JobPersistenceError("Could not create job", cause=exc) from exc

    async def get(self, job_id: JobId) -> JobRecord:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM jobs WHERE job_id = ?",
                    (str(job_id),),
                ).fetchone()
        except sqlite3.Error as exc:
            raise JobPersistenceError("Could not read job", cause=exc) from exc
        if row is None:
            raise JobNotFoundError(f"Job not found: {job_id}")
        return job_from_row(row)

    async def update(self, job: JobRecord, *, expected_version: int | None = None) -> None:
        current = await self.get(job.job_id)
        if expected_version is not None and current.version != expected_version:
            raise JobConcurrencyError(
                "Job version conflict",
                public_context={
                    "expected_version": expected_version,
                    "actual_version": current.version,
                },
            )
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE jobs SET
                        document_id = ?, operation = ?, status = ?, stage = ?,
                        request_json = ?, progress = ?, result_available = ?,
                        result_reference = ?, error_json = ?, warnings_json = ?,
                        created_at = ?, queued_at = ?, started_at = ?,
                        finished_at = ?, cancel_requested_at = ?, cancelled_at = ?,
                        updated_at = ?, version = ?, metadata_json = ?,
                        schema_version = ?
                    WHERE job_id = ?
                    """,
                    job_update_row(job),
                )
            if cursor.rowcount != 1:
                raise JobNotFoundError(f"Job not found: {job.job_id}")
        except sqlite3.Error as exc:
            raise JobPersistenceError("Could not update job", cause=exc) from exc

    async def list(self, query: JobQuery | None = None) -> JobPage:
        query = query or JobQuery()
        conditions: list[str] = []
        params: list[object] = []
        if query.status is not None:
            conditions.append("status = ?")
            params.append(query.status.value)
        if query.document_id is not None:
            conditions.append("document_id = ?")
            params.append(str(query.document_id))
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        try:
            with self._connect() as conn:
                total = int(
                    conn.execute(f"SELECT COUNT(*) FROM jobs {where}", params).fetchone()[0]
                )
                rows = conn.execute(
                    f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (*params, query.limit, query.offset),
                ).fetchall()
        except sqlite3.Error as exc:
            raise JobPersistenceError("Could not list jobs", cause=exc) from exc
        return JobPage(
            items=tuple(job_from_row(row) for row in rows),
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def save_result(self, result: JobStoredResult) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO job_results (
                        job_id, result_json, stored_at, schema_version
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(job_id) DO UPDATE SET
                        result_json = excluded.result_json,
                        stored_at = excluded.stored_at,
                        schema_version = excluded.schema_version
                    """,
                    (
                        str(result.job_id),
                        dumps(result.result),
                        result.stored_at,
                        result.schema_version,
                    ),
                )
        except sqlite3.Error as exc:
            raise JobPersistenceError("Could not save job result", cause=exc) from exc

    async def get_result(self, job_id: JobId) -> JobStoredResult:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM job_results WHERE job_id = ?",
                    (str(job_id),),
                ).fetchone()
        except sqlite3.Error as exc:
            raise JobPersistenceError("Could not read job result", cause=exc) from exc
        if row is None:
            raise JobResultUnavailableError(f"Job result is not available: {job_id}")
        return JobStoredResult(
            job_id=JobId.parse(str(row["job_id"])),
            result=processing_result_from_dict(loads(row["result_json"])),
            stored_at=str(row["stored_at"]),
            schema_version=int(row["schema_version"]),
        )

    def _migrate(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    document_id TEXT,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT,
                    request_json TEXT NOT NULL,
                    progress REAL NOT NULL,
                    result_available INTEGER NOT NULL,
                    result_reference TEXT,
                    error_json TEXT,
                    warnings_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    queued_at TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    cancel_requested_at TEXT,
                    cancelled_at TEXT,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    schema_version INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_results (
                    job_id TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL,
                    stored_at TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_document_id ON jobs(document_id)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_updated_at ON jobs(updated_at)")
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, isoformat_utc(utc_now())),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn


@dataclass(frozen=True, slots=True)
class LocalJobRecoveryService:
    store: JobStore
    policy: JobTransitionPolicy

    async def recover(self) -> None:
        page = await self.store.list(JobQuery(limit=500))
        for record in page.items:
            if record.status in TERMINAL_STATUSES:
                continue
            await self._recover_record(record)

    async def _recover_record(self, record: JobRecord) -> None:
        try:
            if record.status == JobStatus.CANCEL_REQUESTED:
                recovered = self.policy.transition(
                    record,
                    to_status=JobStatus.CANCELLED,
                    progress=record.progress,
                    error=None,
                )
            elif record.status in {JobStatus.CREATED, JobStatus.QUEUED, JobStatus.RUNNING}:
                error = ErrorResult(
                    code="job.interrupted",
                    message="Local job was interrupted by application restart.",
                    category=ErrorCategory.EXECUTION,
                    retryable=True,
                )
                recovered = self.policy.transition(
                    record,
                    to_status=JobStatus.FAILED,
                    error=error,
                )
            else:
                return
            await self.store.update(recovered, expected_version=record.version)
        except Exception as exc:
            raise JobRecoveryError("Could not recover local jobs", cause=exc) from exc


def job_to_result(record: JobRecord) -> JobResult:
    return JobResult(
        job_id=record.job_id,
        status=record.status,
        progress=record.progress,
        created_at=record.created_at,
        started_at=record.started_at,
        completed_at=record.finished_at,
        result_reference=record.result_reference,
        error=record.error,
        warnings=record.warnings,
    )


def new_job_record(job_id: JobId, request: Any, *, operation: str) -> JobRecord:
    now = isoformat_utc(utc_now())
    source_metadata = getattr(getattr(request, "source", None), "metadata", {}) or {}
    document_id = None
    raw_document_id = source_metadata.get("document_id")
    if raw_document_id:
        document_id = DocumentId.parse(raw_document_id)
    return JobRecord(
        job_id=job_id,
        operation=operation,
        status=JobStatus.CREATED,
        request=to_jsonable(request),
        document_id=document_id,
        progress=0.0,
        result_available=False,
        created_at=now,
        updated_at=now,
    )


def job_to_row(job: JobRecord) -> tuple[object, ...]:
    return (
        str(job.job_id),
        str(job.document_id) if job.document_id else None,
        job.operation,
        job.status.value,
        job.stage,
        dumps(job.request),
        job.progress,
        1 if job.result_available else 0,
        job.result_reference,
        dumps(job.error) if job.error else None,
        dumps(job.warnings),
        job.created_at,
        job.queued_at,
        job.started_at,
        job.finished_at,
        job.cancel_requested_at,
        job.cancelled_at,
        job.updated_at,
        job.version,
        dumps(job.metadata),
        job.schema_version,
    )


def job_update_row(job: JobRecord) -> tuple[object, ...]:
    row = job_to_row(job)
    return (
        row[1],
        row[2],
        row[3],
        row[4],
        row[5],
        row[6],
        row[7],
        row[8],
        row[9],
        row[10],
        row[11],
        row[12],
        row[13],
        row[14],
        row[15],
        row[16],
        row[17],
        row[18],
        row[19],
        row[20],
        row[0],
    )


def job_from_row(row: sqlite3.Row) -> JobRecord:
    return JobRecord(
        job_id=JobId.parse(str(row["job_id"])),
        document_id=(
            DocumentId.parse(str(row["document_id"])) if row["document_id"] else None
        ),
        operation=str(row["operation"]),
        status=JobStatus(str(row["status"])),
        stage=row["stage"],
        request=loads(row["request_json"]),
        progress=float(row["progress"]),
        result_available=bool(row["result_available"]),
        result_reference=row["result_reference"],
        error=error_result_from_dict(loads_or_none(row["error_json"])),
        warnings=tuple(eixo_warning_from_dict(item) for item in loads(row["warnings_json"])),
        created_at=row["created_at"],
        queued_at=row["queued_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        cancel_requested_at=row["cancel_requested_at"],
        cancelled_at=row["cancelled_at"],
        updated_at=row["updated_at"],
        version=int(row["version"]),
        metadata={str(k): str(v) for k, v in loads(row["metadata_json"]).items()},
        schema_version=int(row["schema_version"]),
    )


def processing_result_from_dict(payload: dict[str, Any]) -> ProcessingResult:
    return ProcessingResult(
        job_id=JobId.parse(str(payload["job_id"])),
        document_id=(
            DocumentId.parse(str(payload["document_id"]))
            if payload.get("document_id") is not None
            else None
        ),
        status=ProcessingStatus(str(payload["status"])),
        data=dict(payload.get("data", {})),
        artifacts=tuple(
            artifact_reference_from_dict(item)
            for item in payload.get("artifacts", [])
            if item is not None
        ),
        warnings=tuple(eixo_warning_from_dict(item) for item in payload.get("warnings", [])),
        errors=tuple(
            error
            for error in (error_result_from_dict(item) for item in payload.get("errors", []))
            if error is not None
        ),
    )


def dumps(value: Any) -> str:
    try:
        return json.dumps(to_jsonable(value), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise JobSerializationError("Could not serialize job data", cause=exc) from exc


def loads(value: str) -> dict[str, Any] | list[Any]:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise JobSerializationError("Could not deserialize job data", cause=exc) from exc


def loads_or_none(value: str | None) -> Any:
    if value is None:
        return None
    return loads(value)


__all__ = [
    "JobStore",
    "JobTransitionPolicy",
    "LocalJobRecoveryService",
    "SQLiteJobStore",
    "TERMINAL_STATUSES",
    "job_to_result",
    "new_job_record",
    "processing_result_from_dict",
]
