from __future__ import annotations

from dataclasses import dataclass

from eixo.application.ports import (
    InspectionService,
    JobExecutor,
    JobRepository,
    ParsingService,
    ProcessingService,
    ResultRepository,
)
from eixo.core.contracts import (
    InspectionRequest,
    InspectionResult,
    JobResult,
    ParseRequest,
    ParseResult,
    ProcessingRequest,
    ProcessingResult,
)
from eixo.core.ids import JobId


@dataclass(frozen=True, slots=True)
class InspectDocument:
    service: InspectionService

    async def execute(self, request: InspectionRequest) -> InspectionResult:
        return await self.service.inspect(request)


@dataclass(frozen=True, slots=True)
class ParseDocument:
    service: ParsingService

    async def execute(self, request: ParseRequest) -> ParseResult:
        return await self.service.parse(request)


@dataclass(frozen=True, slots=True)
class ProcessDocument:
    service: ProcessingService

    async def execute(self, request: ProcessingRequest) -> ProcessingResult:
        return await self.service.process(request)


@dataclass(frozen=True, slots=True)
class SubmitProcessingJob:
    executor: JobExecutor

    async def execute(self, request: ProcessingRequest) -> JobResult:
        return await self.executor.submit(request)


@dataclass(frozen=True, slots=True)
class GetJobStatus:
    repository: JobRepository

    async def execute(self, job_id: JobId) -> JobResult:
        return await self.repository.get_status(job_id)


@dataclass(frozen=True, slots=True)
class GetJobResult:
    repository: ResultRepository

    async def execute(self, job_id: JobId) -> ProcessingResult:
        return await self.repository.get_result(job_id)


@dataclass(frozen=True, slots=True)
class CancelJob:
    executor: JobExecutor

    async def execute(self, job_id: JobId) -> JobResult:
        return await self.executor.cancel(job_id)

