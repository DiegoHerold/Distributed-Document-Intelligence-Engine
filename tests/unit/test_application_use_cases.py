from __future__ import annotations

import asyncio
from dataclasses import dataclass

from eixo.application import (
    CancelJob,
    GetJobResult,
    GetJobStatus,
    InspectDocument,
    ParseDocument,
    ProcessDocument,
    SubmitProcessingJob,
)
from eixo.core import (
    BytesSource,
    DocumentId,
    InspectionRequest,
    InspectionResult,
    JobId,
    JobResult,
    JobStatus,
    ParseRequest,
    ParseResult,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
    ResultStatus,
)


@dataclass(slots=True)
class FakeServices:
    job_id: JobId
    document_id: DocumentId

    async def inspect(self, request: InspectionRequest) -> InspectionResult:
        return InspectionResult(
            document_id=self.document_id,
            detected_format="bytes",
            declared_media_type=request.source.declared_media_type,
            detected_media_type="application/octet-stream",
            size=request.source.size,
            status=ResultStatus.SUCCESS,
        )

    async def parse(self, request: ParseRequest) -> ParseResult:
        return ParseResult(document_id=self.document_id, status=ResultStatus.SUCCESS)

    async def process(self, request: ProcessingRequest) -> ProcessingResult:
        return ProcessingResult(
            job_id=self.job_id,
            document_id=self.document_id,
            status=ProcessingStatus.COMPLETED,
        )

    async def submit(self, request: ProcessingRequest) -> JobResult:
        return JobResult(job_id=self.job_id, status=JobStatus.QUEUED)

    async def get_status(self, job_id: JobId) -> JobResult:
        return JobResult(job_id=job_id, status=JobStatus.RUNNING, progress=0.5)

    async def get_result(self, job_id: JobId) -> ProcessingResult:
        return ProcessingResult(
            job_id=job_id,
            document_id=self.document_id,
            status=ProcessingStatus.COMPLETED,
        )

    async def cancel(self, job_id: JobId) -> JobResult:
        return JobResult(job_id=job_id, status=JobStatus.CANCELLED)


def test_all_initial_use_cases_delegate_to_ports() -> None:
    services = FakeServices(job_id=JobId.new(), document_id=DocumentId.new())
    source = BytesSource(content=b"abc", size=3)

    async def run() -> None:
        inspected = await InspectDocument(services).execute(InspectionRequest(source=source))
        parsed = await ParseDocument(services).execute(ParseRequest(source=source))
        processed = await ProcessDocument(services).execute(ProcessingRequest(source=source))
        submitted = await SubmitProcessingJob(services).execute(ProcessingRequest(source=source))
        status = await GetJobStatus(services).execute(services.job_id)
        result = await GetJobResult(services).execute(services.job_id)
        cancelled = await CancelJob(services).execute(services.job_id)

        assert inspected.status is ResultStatus.SUCCESS
        assert parsed.document_id == services.document_id
        assert processed.status is ProcessingStatus.COMPLETED
        assert submitted.status is JobStatus.QUEUED
        assert status.progress == 0.5
        assert result.document_id == services.document_id
        assert cancelled.status is JobStatus.CANCELLED

    asyncio.run(run())

