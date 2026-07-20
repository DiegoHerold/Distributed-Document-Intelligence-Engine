from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import PurePath

from eixo.core import (
    CapabilityNotFoundError,
    ErrorCategory,
    ErrorResult,
    ExecutionCancelledError,
    ExecutionError,
    ExecutionTimeoutError,
    InspectionRequest,
    InspectionResult,
    InvalidStateTransitionError,
    JobId,
    JobNotFoundError,
    JobResult,
    JobStatus,
    ParseRequest,
    ParseResult,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
    UnsupportedFormatError,
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
        capability = self.registry.resolve(
            document_format=document_format_from_request(request),
            media_type=request.source.declared_media_type,
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


__all__ = [
    "CapabilityBackedDocumentService",
    "InMemoryJobService",
    "context_from_request",
]
