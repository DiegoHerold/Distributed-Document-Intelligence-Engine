from __future__ import annotations

from typing import Protocol

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


class InspectionService(Protocol):
    async def inspect(self, request: InspectionRequest) -> InspectionResult:
        ...


class ParsingService(Protocol):
    async def parse(self, request: ParseRequest) -> ParseResult:
        ...


class ProcessingService(Protocol):
    async def process(self, request: ProcessingRequest) -> ProcessingResult:
        ...


class JobExecutor(Protocol):
    async def submit(self, request: ProcessingRequest) -> JobResult:
        ...

    async def cancel(self, job_id: JobId) -> JobResult:
        ...


class JobRepository(Protocol):
    async def get_status(self, job_id: JobId) -> JobResult:
        ...


class ResultRepository(Protocol):
    async def get_result(self, job_id: JobId) -> ProcessingResult:
        ...

