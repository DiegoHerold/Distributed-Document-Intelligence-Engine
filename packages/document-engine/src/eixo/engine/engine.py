from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import BinaryIO

from eixo.application import (
    CancelJob,
    CapabilityBackedDocumentService,
    GetJobResult,
    GetJobStatus,
    IngestDocument,
    InMemoryJobService,
    InspectDocument,
    ParseDocument,
    ProcessDocument,
    SubmitProcessingJob,
)
from eixo.core import (
    ConfigurationError,
    DocumentSource,
    DocumentIngestionResult,
    InspectionRequest,
    InspectionResult,
    InvalidStateTransitionError,
    JobId,
    JobResult,
    ParseRequest,
    ParseResult,
    ProcessingRequest,
    ProcessingResult,
    ValidationError,
)
from eixo.plugins import Capability, CapabilityRegistry, ProviderDescriptor
from eixo.runtime.local import LocalRuntime, LocalRuntimeConfig
from eixo.engine.configuration import LocalEngineConfig
from eixo.engine.lifecycle import EngineState

logger = logging.getLogger(__name__)

DocumentInput = DocumentSource | str | Path | bytes | bytearray | memoryview | BinaryIO


@dataclass(slots=True)
class DocumentEngine:
    registry: CapabilityRegistry = field(default_factory=CapabilityRegistry)
    runtime: LocalRuntime = field(default_factory=LocalRuntime)
    inspect_document: InspectDocument | None = None
    parse_document: ParseDocument | None = None
    process_document: ProcessDocument | None = None
    submit_processing_job: SubmitProcessingJob | None = None
    get_job_status_use_case: GetJobStatus | None = None
    get_job_result_use_case: GetJobResult | None = None
    cancel_job_use_case: CancelJob | None = None
    config: LocalEngineConfig = field(default_factory=LocalEngineConfig)
    state: EngineState = EngineState.CREATED

    @classmethod
    def local(
        cls,
        *,
        config: LocalEngineConfig | None = None,
        runtime: LocalRuntime | None = None,
        runtime_config: LocalRuntimeConfig | None = None,
        registry: CapabilityRegistry | None = None,
        providers: tuple[ProviderDescriptor, ...] = (),
        capabilities: tuple[Capability[object, object], ...] = (),
        data_directory: str | Path | None = None,
        max_concurrent_tasks: int | None = None,
        default_timeout: float | None = None,
    ) -> "DocumentEngine":
        if config is not None:
            engine_config = (
                replace(config, data_directory=Path(data_directory))
                if data_directory is not None
                else config
            )
        else:
            engine_config = LocalEngineConfig(
                runtime=runtime_config
                or LocalRuntimeConfig(
                    max_concurrent_tasks=max_concurrent_tasks or 8,
                    default_timeout=default_timeout if default_timeout is not None else 30.0,
                ),
                data_directory=(
                    Path(data_directory) if data_directory is not None else Path(".eixo/local")
                ),
            )
        if runtime is None:
            runtime = LocalRuntime(config=engine_config.runtime)
        registry = registry or CapabilityRegistry()
        for provider in providers:
            registry.register_provider(provider)
        for capability in capabilities:
            registry.register(capability)
        ingest_document = IngestDocument.local(engine_config.data_directory)
        service = CapabilityBackedDocumentService(
            registry=registry,
            runtime=runtime,
            ingest_document=ingest_document,
        )
        jobs = InMemoryJobService(processing_service=service, runtime=runtime)
        return cls(
            registry=registry,
            runtime=runtime,
            inspect_document=InspectDocument(service),
            parse_document=ParseDocument(service),
            process_document=ProcessDocument(service),
            submit_processing_job=SubmitProcessingJob(jobs),
            get_job_status_use_case=GetJobStatus(jobs),
            get_job_result_use_case=GetJobResult(jobs),
            cancel_job_use_case=CancelJob(jobs),
            config=engine_config,
        )

    def register_capability(self, capability: Capability[object, object]) -> None:
        self._ensure_mutable()
        self.registry.register(capability)

    async def __aenter__(self) -> "DocumentEngine":
        await self.start()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.shutdown()

    async def start(self) -> None:
        if self.state == EngineState.RUNNING:
            return
        if self.state == EngineState.STOPPED:
            raise InvalidStateTransitionError("Engine cannot be restarted after shutdown")
        if self.state in {EngineState.STARTING, EngineState.STOPPING}:
            raise InvalidStateTransitionError(f"Engine is {self.state}")
        self.state = EngineState.STARTING
        self._log("engine.starting")
        try:
            await self.runtime.start()
            self._ensure_composed()
            self.state = EngineState.RUNNING
            self._log("engine.started")
        except Exception:
            self.state = EngineState.FAILED
            self._log("engine.operation.failed", operation="start")
            raise

    async def shutdown(self) -> None:
        if self.state == EngineState.STOPPED:
            return
        if self.state == EngineState.STOPPING:
            return
        self.state = EngineState.STOPPING
        self._log("engine.stopping")
        await self.runtime.shutdown()
        self.state = EngineState.STOPPED
        self._log("engine.stopped")

    async def inspect(
        self,
        request_or_source: InspectionRequest | DocumentInput,
        *,
        options: dict[str, object] | None = None,
    ) -> InspectionResult:
        request = (
            request_or_source
            if isinstance(request_or_source, InspectionRequest)
            else InspectionRequest(
                source=self._source_from_input(request_or_source),
                options=options or {},
            )
        )
        await self._ensure_running()
        assert self.inspect_document is not None
        self._log_operation_started("inspect", request.correlation_id.value)
        result = await self.inspect_document.execute(request)
        self._log_operation_completed("inspect", request.correlation_id.value)
        return result

    async def parse(
        self,
        request_or_source: ParseRequest | DocumentInput,
        *,
        options: dict[str, object] | None = None,
    ) -> ParseResult:
        request = (
            request_or_source
            if isinstance(request_or_source, ParseRequest)
            else ParseRequest(
                source=self._source_from_input(request_or_source),
                options=options or {},
            )
        )
        await self._ensure_running()
        assert self.parse_document is not None
        self._log_operation_started("parse", request.correlation_id.value)
        result = await self.parse_document.execute(request)
        self._log_operation_completed("parse", request.correlation_id.value)
        return result

    async def process(
        self,
        request_or_source: ProcessingRequest | DocumentInput,
        *,
        options: dict[str, object] | None = None,
    ) -> ProcessingResult:
        request = (
            request_or_source
            if isinstance(request_or_source, ProcessingRequest)
            else ProcessingRequest(
                source=self._source_from_input(request_or_source),
                options=options or {},
            )
        )
        await self._ensure_running()
        assert self.process_document is not None
        self._log_operation_started("process", request.correlation_id.value)
        result = await self.process_document.execute(request)
        self._log_operation_completed("process", request.correlation_id.value)
        return result

    async def submit(
        self,
        request_or_source: ProcessingRequest | DocumentInput,
        *,
        options: dict[str, object] | None = None,
    ) -> JobResult:
        request = (
            request_or_source
            if isinstance(request_or_source, ProcessingRequest)
            else ProcessingRequest(
                source=self._source_from_input(request_or_source),
                options=options or {},
            )
        )
        await self._ensure_running()
        assert self.submit_processing_job is not None
        return await self.submit_processing_job.execute(request)

    async def ingest(
        self,
        source: DocumentInput,
    ) -> DocumentIngestionResult:
        await self._ensure_running()
        self._ensure_composed()
        assert self.process_document is not None
        service = self.process_document.service
        if not isinstance(service, CapabilityBackedDocumentService):
            raise ConfigurationError("Document ingestion is not available")
        return await service.ingest_document.execute(self._source_from_input(source))

    async def get_job_status(self, job_id: JobId | str) -> JobResult:
        await self._ensure_running()
        assert self.get_job_status_use_case is not None
        return await self.get_job_status_use_case.execute(self._job_id(job_id))

    async def get_job_result(self, job_id: JobId | str) -> ProcessingResult:
        await self._ensure_running()
        assert self.get_job_result_use_case is not None
        return await self.get_job_result_use_case.execute(self._job_id(job_id))

    async def cancel_job(self, job_id: JobId | str) -> JobResult:
        await self._ensure_running()
        assert self.cancel_job_use_case is not None
        return await self.cancel_job_use_case.execute(self._job_id(job_id))

    async def _ensure_running(self) -> None:
        if self.state == EngineState.RUNNING:
            return
        if self.state == EngineState.CREATED and self.config.auto_start:
            await self.start()
            return
        raise InvalidStateTransitionError(f"Engine is not accepting operations: {self.state}")

    def _ensure_composed(self) -> None:
        required = [
            self.inspect_document,
            self.parse_document,
            self.process_document,
            self.submit_processing_job,
            self.get_job_status_use_case,
            self.get_job_result_use_case,
            self.cancel_job_use_case,
        ]
        if any(item is None for item in required):
            raise ConfigurationError("DocumentEngine dependencies are incomplete")

    def _ensure_mutable(self) -> None:
        if self.state != EngineState.CREATED:
            raise InvalidStateTransitionError("Capabilities can only be registered before start")

    def _job_id(self, job_id: JobId | str) -> JobId:
        return job_id if isinstance(job_id, JobId) else JobId.parse(job_id)

    def _source_from_input(self, value: DocumentInput) -> DocumentSource:
        if isinstance(value, DocumentSource):
            return value
        if isinstance(value, (str, Path)):
            return DocumentSource.from_path(value)
        if isinstance(value, (bytes, bytearray, memoryview)):
            return DocumentSource.from_bytes(value)
        if hasattr(value, "read"):
            return DocumentSource.from_stream(value)
        raise ValidationError("Unsupported document source input")

    def _log(self, event: str, **fields: str) -> None:
        logger.info(event, extra={"event": event, **fields})

    def _log_operation_started(self, operation: str, correlation_id: str) -> None:
        self._log(
            "engine.operation.started",
            operation=operation,
            correlation_id=correlation_id,
        )

    def _log_operation_completed(self, operation: str, correlation_id: str) -> None:
        self._log(
            "engine.operation.completed",
            operation=operation,
            correlation_id=correlation_id,
        )
