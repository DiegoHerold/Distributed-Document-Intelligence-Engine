from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from pathlib import Path
from pathlib import PurePath

from eixo.application.document_ingestion import IngestDocument
from eixo.application.ingestion import (
    ContentIdentityService,
    LocalSourceResolver,
    SourceResolver,
    enrich_source_with_identity,
)
from eixo.application.jobs import (
    JobStore,
    JobTransitionPolicy,
    LocalJobRecoveryService,
    TERMINAL_STATUSES,
    job_to_result,
    new_job_record,
)
from eixo.core import (
    CapabilityNotFoundError,
    ErrorCategory,
    ErrorResult,
    ExecutionCancelledError,
    ExecutionError,
    ExecutionTimeoutError,
    InspectionRequest,
    InspectionResult,
    InvalidPDFError,
    InvalidPDFPasswordError,
    InvalidStateTransitionError,
    JobId,
    JobNotFoundError,
    JobResult,
    JobResultUnavailableError,
    JobStatus,
    JobStoredResult,
    ParseRequest,
    ParseResult,
    PDFPageOutOfRangeError,
    PDFPasswordRequiredError,
    PDFProviderExecutionError,
    PDFProviderUnavailableError,
    PDFResourceLimitExceededError,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
    DetectedDocumentFormat,
    DocumentIngestionResult,
    DocumentFormat,
    IdentifiedDocumentContent,
    UnsupportedFormatError,
    UnsupportedPDFError,
    ValidationError,
    isoformat_utc,
    utc_now,
)
from eixo.plugins import (
    CapabilityRegistry,
    ExecutionContext,
    ExecutionMode,
    ExecutionResult,
    ExecutionRuntime,
    ExecutionStatus,
    ExecutionTask,
)


def context_from_request(
    request: InspectionRequest | ParseRequest | ProcessingRequest,
) -> ExecutionContext:
    return ExecutionContext(
        correlation_id=request.correlation_id,
        tenant_id=request.tenant_id,
    )


@dataclass(frozen=True, slots=True)
class CapabilityBackedDocumentService:
    registry: CapabilityRegistry
    runtime: ExecutionRuntime
    source_resolver: SourceResolver = field(default_factory=LocalSourceResolver)
    content_identifier: ContentIdentityService = field(default_factory=ContentIdentityService)
    ingest_document: IngestDocument = field(
        default_factory=lambda: IngestDocument.local(Path(".eixo/local"))
    )

    async def inspect(self, request: InspectionRequest) -> InspectionResult:
        return await self._execute(
            request,
            input_contract="InspectionRequest",
            output_contract="InspectionResult",
        )

    async def parse(self, request: ParseRequest) -> ParseResult:
        return await self._execute(
            request,
            input_contract="ParseRequest",
            output_contract="ParseResult",
        )

    async def process(self, request: ProcessingRequest) -> ProcessingResult:
        return await self._execute(
            request,
            input_contract="ProcessingRequest",
            output_contract="ProcessingResult",
        )

    async def _execute(
        self,
        request: InspectionRequest | ParseRequest | ProcessingRequest,
        *,
        input_contract: str,
        output_contract: str,
    ):
        ingestion = await self.ingest_document.execute(request.source)
        request = request_with_ingestion_result(request, ingestion)
        detected_format = document_format_from_detection(ingestion.detected_format)
        media_type = ingestion.detected_format.canonical_mime or request.source.declared_media_type
        capability = self.registry.resolve(
            document_format=detected_format or document_format_from_request(request),
            media_type=media_type,
            input_contract=input_contract,
            output_contract=output_contract,
        )
        result = await self.runtime.execute_capability(
            capability,
            request,
            context=context_from_request(request),
        )
        if result.status != ExecutionStatus.COMPLETED:
            if result.error is not None:
                if result.error.code == ExecutionTimeoutError.code:
                    raise ExecutionTimeoutError(
                        result.error.message,
                        details=result.error.details,
                    )
                if result.error.code == ExecutionCancelledError.code:
                    raise ExecutionCancelledError(
                        result.error.message,
                        details=result.error.details,
                    )
                if result.error.code == UnsupportedFormatError.code:
                    raise UnsupportedFormatError(
                        result.error.message,
                        details=result.error.details,
                    )
                if result.error.code == ValidationError.code:
                    raise ValidationError(
                        result.error.message,
                        details=result.error.details,
                    )
                if result.error.code == PDFProviderUnavailableError.code:
                    raise PDFProviderUnavailableError(
                        result.error.message,
                        details=result.error.details,
                    )
                if result.error.code == UnsupportedPDFError.code:
                    raise UnsupportedPDFError(
                        result.error.message,
                        details=result.error.details,
                    )
                if result.error.code == InvalidPDFError.code:
                    raise InvalidPDFError(
                        result.error.message,
                        details=result.error.details,
                    )
                if result.error.code == PDFPasswordRequiredError.code:
                    raise PDFPasswordRequiredError(
                        result.error.message,
                        details=result.error.details,
                    )
                if result.error.code == InvalidPDFPasswordError.code:
                    raise InvalidPDFPasswordError(
                        result.error.message,
                        details=result.error.details,
                    )
                if result.error.code == PDFPageOutOfRangeError.code:
                    raise PDFPageOutOfRangeError(
                        result.error.message,
                        details=result.error.details,
                    )
                if result.error.code == PDFResourceLimitExceededError.code:
                    raise PDFResourceLimitExceededError(
                        result.error.message,
                        details=result.error.details,
                    )
                if result.error.code == PDFProviderExecutionError.code:
                    raise PDFProviderExecutionError(
                        result.error.message,
                        details=result.error.details,
                    )
                raise ExecutionError(result.error.message, details=result.error.details)
            raise ExecutionError(f"Capability execution ended with status {result.status}")
        return result.value


@dataclass(slots=True)
class InMemoryJobService:
    processing_service: CapabilityBackedDocumentService
    runtime: ExecutionRuntime
    _jobs: dict[JobId, JobResult] = field(default_factory=dict)
    _results: dict[JobId, ProcessingResult] = field(default_factory=dict)
    _handles: dict[JobId, object] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def submit(self, request: ProcessingRequest) -> JobResult:
        job_id = JobId.new()
        created_at = isoformat_utc(utc_now())
        job = JobResult(
            job_id=job_id,
            status=JobStatus.QUEUED,
            progress=0.0,
            created_at=created_at,
        )
        async with self._lock:
            self._jobs[job_id] = job

        async def run_processing(
            value: ProcessingRequest,
            context,
        ) -> ProcessingResult:
            async with self._lock:
                self._jobs[job_id] = JobResult(
                    job_id=job_id,
                    status=JobStatus.RUNNING,
                    progress=0.1,
                    created_at=created_at,
                    started_at=isoformat_utc(utc_now()),
                )
            return await self.processing_service.process(value)

        task = ExecutionTask(
            task_id=f"task_{job_id}",
            name="process-document-job",
            handler=run_processing,
            input=request,
            execution_mode=ExecutionMode.ASYNC,
        )
        handle = await self.runtime.submit(task, context=context_from_request(request))
        async with self._lock:
            self._handles[job_id] = handle
        asyncio.create_task(self._watch_job(job_id, handle))
        return job

    async def get_status(self, job_id: JobId) -> JobResult:
        await self._ensure_job(job_id)
        async with self._lock:
            handle = self._handles.get(job_id)
            existing = self._jobs[job_id]
        if handle is None:
            return existing
        status = handle.status
        if status == ExecutionStatus.RUNNING:
            progress = handle.progress.percentage / 100 if handle.progress else 0.5
            return JobResult(
                job_id=job_id,
                status=JobStatus.RUNNING,
                progress=progress,
                created_at=existing.created_at,
                started_at=existing.started_at,
            )
        if status == ExecutionStatus.QUEUED:
            return JobResult(
                job_id=job_id,
                status=JobStatus.QUEUED,
                progress=0.0,
                created_at=existing.created_at,
            )
        return existing

    async def get_result(self, job_id: JobId) -> ProcessingResult:
        await self._ensure_job(job_id)
        async with self._lock:
            if job_id in self._results:
                return self._results[job_id]
            handle = self._handles.get(job_id)
        if handle is not None and handle.status == ExecutionStatus.COMPLETED:
            result = await handle.wait()
            if result.status == ExecutionStatus.COMPLETED and result.value is not None:
                async with self._lock:
                    self._results.setdefault(job_id, result.value)
                return result.value
        raise InvalidStateTransitionError("Job result is not available yet")

    async def cancel(self, job_id: JobId) -> JobResult:
        await self._ensure_job(job_id)
        async with self._lock:
            current = self._jobs[job_id]
            handle = self._handles.get(job_id)
        if current.status == JobStatus.CANCELLED:
            return current
        if current.status == JobStatus.COMPLETED:
            raise InvalidStateTransitionError("Completed jobs cannot be cancelled")
        if handle is not None:
            await handle.cancel()
        job = JobResult(
            job_id=job_id,
            status=JobStatus.CANCELLED,
            progress=0.0,
            created_at=current.created_at,
            started_at=current.started_at,
            completed_at=isoformat_utc(utc_now()),
        )
        async with self._lock:
            self._jobs[job_id] = job
        return job

    async def _watch_job(self, job_id: JobId, handle) -> None:
        result: ExecutionResult[ProcessingResult] = await handle.wait()
        if result.status == ExecutionStatus.COMPLETED and result.value is not None:
            async with self._lock:
                previous = self._jobs[job_id]
                if previous.status == JobStatus.CANCELLED:
                    return
                self._results[job_id] = result.value
                self._jobs[job_id] = JobResult(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    progress=1.0,
                    created_at=previous.created_at,
                    started_at=previous.started_at,
                    completed_at=isoformat_utc(utc_now()),
                )
        elif result.status == ExecutionStatus.CANCELLED:
            async with self._lock:
                previous = self._jobs[job_id]
                self._jobs[job_id] = JobResult(
                    job_id=job_id,
                    status=JobStatus.CANCELLED,
                    created_at=previous.created_at,
                    started_at=previous.started_at,
                    completed_at=isoformat_utc(utc_now()),
                )
        else:
            error = result.error
            async with self._lock:
                previous = self._jobs[job_id]
                if previous.status == JobStatus.CANCELLED:
                    return
                self._jobs[job_id] = JobResult(
                    job_id=job_id,
                    status=JobStatus.FAILED,
                    created_at=previous.created_at,
                    started_at=previous.started_at,
                    completed_at=isoformat_utc(utc_now()),
                    error=ErrorResult(
                        code=error.code if error else "execution.error",
                        message=error.message if error else "Job failed",
                        category=error.category if error else ErrorCategory.EXECUTION,
                        retryable=error.retryable if error else False,
                        details=error.details if error else {},
                    ),
                )

    async def _ensure_job(self, job_id: JobId) -> None:
        async with self._lock:
            exists = job_id in self._jobs
        if not exists:
            raise JobNotFoundError(f"Job not found: {job_id}")


@dataclass(slots=True)
class PersistentJobService:
    processing_service: CapabilityBackedDocumentService
    runtime: ExecutionRuntime
    store: JobStore
    policy: JobTransitionPolicy = field(default_factory=JobTransitionPolicy.default)
    _handles: dict[JobId, object] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _recovered: bool = False

    async def submit(self, request: ProcessingRequest) -> JobResult:
        await self._ensure_recovered()
        job_id = JobId.new()
        created = new_job_record(job_id, request, operation="process")
        await self.store.create(created)
        queued = self.policy.transition(
            created,
            to_status=JobStatus.QUEUED,
            progress=0.0,
            stage="queued",
        )
        await self.store.update(queued, expected_version=created.version)

        async def run_processing(
            value: ProcessingRequest,
            context,
        ) -> ProcessingResult:
            current = await self.store.get(job_id)
            running = self.policy.transition(
                current,
                to_status=JobStatus.RUNNING,
                progress=0.1,
                stage="processing",
            )
            await self.store.update(running, expected_version=current.version)
            return await self.processing_service.process(value)

        task = ExecutionTask(
            task_id=f"task_{job_id}",
            name="process-document-job",
            handler=run_processing,
            input=request,
            execution_mode=ExecutionMode.ASYNC,
        )
        handle = await self.runtime.submit(task, context=context_from_request(request))
        async with self._lock:
            self._handles[job_id] = handle
        asyncio.create_task(self._watch_job(job_id, handle))
        return job_to_result(queued)

    async def get_status(self, job_id: JobId) -> JobResult:
        await self._ensure_recovered()
        record = await self.store.get(job_id)
        async with self._lock:
            handle = self._handles.get(job_id)
        if handle is not None and handle.status == ExecutionStatus.RUNNING:
            progress = handle.progress.percentage / 100 if handle.progress else record.progress
            if progress > record.progress:
                updated = replace(record, progress=progress, updated_at=isoformat_utc(utc_now()))
                await self.store.update(updated, expected_version=record.version)
                record = updated
        return job_to_result(record)

    async def get_result(self, job_id: JobId) -> ProcessingResult:
        await self._ensure_recovered()
        record = await self.store.get(job_id)
        if record.status == JobStatus.FAILED:
            raise JobResultUnavailableError("Job failed before producing a result")
        if record.status == JobStatus.CANCELLED:
            raise JobResultUnavailableError("Job was cancelled before producing a result")
        if not record.result_available:
            async with self._lock:
                handle = self._handles.get(job_id)
            if handle is not None and handle.status == ExecutionStatus.COMPLETED:
                await self._store_completed_handle(job_id, handle)
        return (await self.store.get_result(job_id)).result

    async def cancel(self, job_id: JobId) -> JobResult:
        await self._ensure_recovered()
        current = await self.store.get(job_id)
        if current.status == JobStatus.CANCELLED:
            return job_to_result(current)
        if current.status in {
            JobStatus.COMPLETED,
            JobStatus.REVIEW_REQUIRED,
            JobStatus.FAILED,
        }:
            raise InvalidStateTransitionError("Terminal jobs cannot be cancelled")
        async with self._lock:
            handle = self._handles.get(job_id)
        if current.status == JobStatus.CANCEL_REQUESTED:
            if handle is None or handle.status == ExecutionStatus.CANCELLED:
                cancelled = self.policy.transition(
                    current,
                    to_status=JobStatus.CANCELLED,
                    progress=0.0,
                    stage="cancelled",
                )
                await self.store.update(cancelled, expected_version=current.version)
                return job_to_result(cancelled)
            return job_to_result(current)
        if current.status == JobStatus.CREATED:
            cancelled = self.policy.transition(
                current,
                to_status=JobStatus.CANCELLED,
                progress=0.0,
                stage="cancelled",
            )
            await self.store.update(cancelled, expected_version=current.version)
            return job_to_result(cancelled)
        requested = self.policy.transition(
            current,
            to_status=JobStatus.CANCEL_REQUESTED,
            stage="cancelling",
        )
        await self.store.update(requested, expected_version=current.version)
        if handle is None:
            cancelled = self.policy.transition(
                requested,
                to_status=JobStatus.CANCELLED,
                progress=0.0,
                stage="cancelled",
            )
            await self.store.update(cancelled, expected_version=requested.version)
            return job_to_result(cancelled)
        if handle is not None:
            await handle.cancel()
            if handle.status == ExecutionStatus.CANCELLED:
                cancelled = self.policy.transition(
                    requested,
                    to_status=JobStatus.CANCELLED,
                    progress=0.0,
                    stage="cancelled",
                )
                await self.store.update(cancelled, expected_version=requested.version)
                return job_to_result(cancelled)
        return job_to_result(requested)

    async def _watch_job(self, job_id: JobId, handle) -> None:
        result: ExecutionResult[ProcessingResult] = await handle.wait()
        await self._store_execution_result(job_id, result)

    async def _store_completed_handle(self, job_id: JobId, handle) -> None:
        result: ExecutionResult[ProcessingResult] = await handle.wait()
        await self._store_execution_result(job_id, result)

    async def _store_execution_result(
        self,
        job_id: JobId,
        result: ExecutionResult[ProcessingResult],
    ) -> None:
        current = await self.store.get(job_id)
        if current.status in TERMINAL_STATUSES:
            return
        if result.status == ExecutionStatus.COMPLETED and result.value is not None:
            await self.store.save_result(
                JobStoredResult(
                    job_id=job_id,
                    result=result.value,
                    stored_at=isoformat_utc(utc_now()),
                )
            )
            to_status = (
                JobStatus.REVIEW_REQUIRED
                if result.value.status == ProcessingStatus.REVIEW_REQUIRED
                else JobStatus.COMPLETED
            )
            completed = self.policy.transition(
                current,
                to_status=to_status,
                progress=1.0,
                stage="completed",
                result_available=True,
            )
            await self.store.update(completed, expected_version=current.version)
            return
        if result.status == ExecutionStatus.CANCELLED:
            if current.status not in {JobStatus.CREATED, JobStatus.CANCEL_REQUESTED}:
                requested = self.policy.transition(
                    current,
                    to_status=JobStatus.CANCEL_REQUESTED,
                    stage="cancelling",
                )
                await self.store.update(requested, expected_version=current.version)
                current = requested
            cancelled = self.policy.transition(
                current,
                to_status=JobStatus.CANCELLED,
                progress=0.0,
                stage="cancelled",
            )
            await self.store.update(cancelled, expected_version=current.version)
            return
        error = result.error
        failed = self.policy.transition(
            current,
            to_status=JobStatus.FAILED,
            stage="failed",
            error=ErrorResult(
                code=error.code if error else "execution.error",
                message=error.message if error else "Job failed",
                category=error.category if error else ErrorCategory.EXECUTION,
                retryable=error.retryable if error else False,
                details=error.details if error else {},
            ),
        )
        await self.store.update(failed, expected_version=current.version)

    async def _ensure_recovered(self) -> None:
        if self._recovered:
            return
        async with self._lock:
            if self._recovered:
                return
            await LocalJobRecoveryService(self.store, self.policy).recover()
            self._recovered = True


def document_format_from_request(
    request: InspectionRequest | ParseRequest | ProcessingRequest,
) -> str | None:
    filename = request.source.filename
    if request.source.source_type != "local_path":
        return None
    if not filename:
        return None
    suffix = PurePath(filename).suffix
    return suffix.lstrip(".") or None


def document_format_from_detection(value: DetectedDocumentFormat) -> str | None:
    if value.format == DocumentFormat.UNKNOWN:
        return None
    return value.format.value


def request_with_identified_source(
    request: InspectionRequest | ParseRequest | ProcessingRequest,
    identified: IdentifiedDocumentContent,
) -> InspectionRequest | ParseRequest | ProcessingRequest:
    source = enrich_source_with_identity(request.source, identified)
    return replace(request, source=source)


def request_with_ingestion_result(
    request: InspectionRequest | ParseRequest | ProcessingRequest,
    ingestion: DocumentIngestionResult,
) -> InspectionRequest | ParseRequest | ProcessingRequest:
    metadata = dict(request.source.metadata)
    metadata.update(
        {
            "document_id": str(ingestion.document_id),
            "artifact_id": str(ingestion.original_artifact.artifact_id),
            "content_hash": ingestion.identity.content_hash.canonical_value,
            "detected_format": ingestion.detected_format.format.value,
        }
    )
    source = replace(request.source, size=ingestion.size_bytes, metadata=metadata)
    return replace(request, source=source)


__all__ = [
    "CapabilityBackedDocumentService",
    "InMemoryJobService",
    "PersistentJobService",
    "context_from_request",
    "document_format_from_detection",
    "request_with_identified_source",
    "request_with_ingestion_result",
]
