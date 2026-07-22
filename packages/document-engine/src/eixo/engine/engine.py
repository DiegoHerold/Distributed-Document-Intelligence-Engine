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
    PersistentJobService,
    InspectDocument,
    ParseDocument,
    ProcessDocument,
    SQLiteJobStore,
    SubmitProcessingJob,
)
from eixo.core import (
    ConfigurationError,
    DocumentSource,
    DocumentIngestionResult,
    InspectionRequest,
    InspectionResult,
    IngestionSecurityPolicy,
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
from eixo.pdf import PDFProvider, PDFProviderRegistry, PDFProviderSettings
from eixo.pdf import (
    DefaultPDFInternalStructureMapper,
    DefaultPDFInteractiveExtractor,
    DefaultPDFNativeImageExtractor,
    DefaultPDFNativeTextExtractor,
    DefaultPDFNativeVectorExtractor,
    DefaultPDFTechnicalInspector,
    DefaultPDFTypographyResolver,
    PDFInternalMappingOptions,
    PDFInternalStructureArtifact,
    PDFInternalStructureMapper,
    PDFImageExtractionOptions,
    PDFInteractiveArtifact,
    PDFInteractiveExtractionOptions,
    PDFInteractiveExtractor,
    PDFInspectionOptions,
    PDFNativeImageArtifact,
    PDFNativeImageExtractor,
    PDFNativeTextArtifact,
    PDFNativeTextExtractionOptions,
    PDFNativeTextExtractor,
    PDFNativeVectorArtifact,
    PDFNativeVectorExtractor,
    PDFNativeVectorOptions,
    PDFTechnicalInspection,
    PDFTechnicalInspector,
    PDFTypographyArtifact,
    PDFTypographyOptions,
    PDFTypographyResolver,
)
from eixo.runtime.local import LocalRuntime, LocalRuntimeConfig
from eixo.artifacts import LocalArtifactStore
from eixo.engine.configuration import LocalEngineConfig
from eixo.engine.lifecycle import EngineState
from eixo.engine.pdf_public import (
    PDFInspectionCapability,
    PDFParseCapability,
    PDFProcessingCapability,
    PUBLIC_PDF_PROVIDER_ID,
    public_pdf_provider_descriptor,
)

logger = logging.getLogger(__name__)

DocumentInput = DocumentSource | str | Path | bytes | bytearray | memoryview | BinaryIO


@dataclass(slots=True)
class DocumentEngine:
    registry: CapabilityRegistry = field(default_factory=CapabilityRegistry)
    pdf_provider_registry: PDFProviderRegistry = field(default_factory=PDFProviderRegistry)
    pdf_technical_inspector: PDFTechnicalInspector | None = None
    pdf_interactive_extractor: PDFInteractiveExtractor | None = None
    pdf_internal_structure_mapper: PDFInternalStructureMapper | None = None
    pdf_native_image_extractor: PDFNativeImageExtractor | None = None
    pdf_typography_resolver: PDFTypographyResolver | None = None
    pdf_native_text_extractor: PDFNativeTextExtractor | None = None
    pdf_native_vector_extractor: PDFNativeVectorExtractor | None = None
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
        pdf_providers: tuple[PDFProvider, ...] = (),
        pdf_provider_registry: PDFProviderRegistry | None = None,
        pdf_technical_inspector: PDFTechnicalInspector | None = None,
        pdf_interactive_extractor: PDFInteractiveExtractor | None = None,
        pdf_internal_structure_mapper: PDFInternalStructureMapper | None = None,
        pdf_native_image_extractor: PDFNativeImageExtractor | None = None,
        pdf_typography_resolver: PDFTypographyResolver | None = None,
        pdf_native_text_extractor: PDFNativeTextExtractor | None = None,
        pdf_native_vector_extractor: PDFNativeVectorExtractor | None = None,
        pdf: PDFProviderSettings | None = None,
        data_directory: str | Path | None = None,
        job_database_path: str | Path | None = None,
        security: IngestionSecurityPolicy | None = None,
        max_concurrent_tasks: int | None = None,
        default_timeout: float | None = None,
    ) -> "DocumentEngine":
        if config is not None:
            engine_config = config
            if data_directory is not None:
                engine_config = replace(engine_config, data_directory=Path(data_directory))
            if job_database_path is not None:
                engine_config = replace(
                    engine_config,
                    job_database_path=Path(job_database_path),
                )
            if security is not None:
                engine_config = replace(engine_config, security=security)
            if pdf is not None:
                engine_config = replace(engine_config, pdf=pdf)
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
                job_database_path=(
                    Path(job_database_path) if job_database_path is not None else None
                ),
                security=security or IngestionSecurityPolicy(),
                pdf=pdf or PDFProviderSettings(),
            )
        if runtime is None:
            runtime = LocalRuntime(config=engine_config.runtime)
        registry = registry or CapabilityRegistry()
        for provider in providers:
            registry.register_provider(provider)
        for capability in capabilities:
            registry.register(capability)
        pdf_registry = pdf_provider_registry or PDFProviderRegistry()
        for provider in pdf_providers:
            pdf_registry.register(provider)
        if not pdf_registry.list_providers():
            try:
                from eixo.providers.pdf.pymupdf import create_pymupdf_pdf_provider

                pdf_registry.register(create_pymupdf_pdf_provider())
            except Exception:
                logger.info("engine.pdf_provider.autoregistration_skipped")
        technical_inspector = pdf_technical_inspector or DefaultPDFTechnicalInspector(
            pdf_registry
        )
        interactive_extractor = pdf_interactive_extractor or DefaultPDFInteractiveExtractor(
            pdf_registry
        )
        internal_structure_mapper = (
            pdf_internal_structure_mapper
            or DefaultPDFInternalStructureMapper(pdf_registry)
        )
        native_image_extractor = pdf_native_image_extractor or DefaultPDFNativeImageExtractor(
            pdf_registry
        )
        typography_resolver = pdf_typography_resolver or DefaultPDFTypographyResolver(
            pdf_registry
        )
        native_text_extractor = pdf_native_text_extractor or DefaultPDFNativeTextExtractor(
            pdf_registry
        )
        native_vector_extractor = (
            pdf_native_vector_extractor or DefaultPDFNativeVectorExtractor(pdf_registry)
        )
        ingest_document = IngestDocument.local(
            engine_config.data_directory,
            security_policy=engine_config.security,
        )
        artifact_store = LocalArtifactStore(engine_config.data_directory)
        if not any(
            provider.provider_id == PUBLIC_PDF_PROVIDER_ID
            for provider in registry.list_providers()
        ):
            registry.register_provider(public_pdf_provider_descriptor())
        pdf_parse_capability = PDFParseCapability(
            pdf_provider_registry=pdf_registry,
            artifact_store=artifact_store,
            preferred_provider=engine_config.pdf.default_provider,
        )
        for capability in (
            PDFInspectionCapability(
                pdf_provider_registry=pdf_registry,
                artifact_store=artifact_store,
                preferred_provider=engine_config.pdf.default_provider,
            ),
            pdf_parse_capability,
            PDFProcessingCapability(pdf_parse_capability),
        ):
            if not any(
                item.capability_id == capability.descriptor.capability_id
                for item in registry.list_capabilities()
            ):
                registry.register(capability)
        service = CapabilityBackedDocumentService(
            registry=registry,
            runtime=runtime,
            ingest_document=ingest_document,
        )
        jobs = PersistentJobService(
            processing_service=service,
            runtime=runtime,
            store=SQLiteJobStore(
                engine_config.job_database_path
                or engine_config.data_directory / "jobs" / "jobs.sqlite3"
            ),
        )
        return cls(
            registry=registry,
            pdf_provider_registry=pdf_registry,
            pdf_technical_inspector=technical_inspector,
            pdf_interactive_extractor=interactive_extractor,
            pdf_internal_structure_mapper=internal_structure_mapper,
            pdf_native_image_extractor=native_image_extractor,
            pdf_typography_resolver=typography_resolver,
            pdf_native_text_extractor=native_text_extractor,
            pdf_native_vector_extractor=native_vector_extractor,
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

    def register_pdf_provider(self, provider: PDFProvider) -> None:
        self._ensure_mutable()
        self.pdf_provider_registry.register(provider)

    @property
    def pdf_provider(self) -> PDFProvider:
        return self.pdf_provider_registry.resolve(
            preferred_provider=self.config.pdf.default_provider
        )

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

    async def inspect_pdf(
        self,
        source: DocumentInput,
        *,
        options: PDFInspectionOptions | None = None,
    ) -> PDFTechnicalInspection:
        await self._ensure_running()
        if self.pdf_technical_inspector is None:
            raise ConfigurationError("PDF technical inspection is not available")
        self._log("engine.pdf_inspection.started")
        result = await self.pdf_technical_inspector.inspect(
            self._source_from_input(source),
            options,
        )
        self._log("engine.pdf_inspection.completed")
        return result

    async def map_pdf_internal_structure(
        self,
        source: DocumentInput,
        *,
        options: PDFInternalMappingOptions | None = None,
    ) -> PDFInternalStructureArtifact:
        await self._ensure_running()
        if self.pdf_internal_structure_mapper is None:
            raise ConfigurationError("PDF internal structure mapping is not available")
        self._log("engine.pdf_structure_mapping.started")
        result = await self.pdf_internal_structure_mapper.map(
            self._source_from_input(source),
            options,
        )
        self._log("engine.pdf_structure_mapping.completed")
        return result

    async def resolve_pdf_typography(
        self,
        source: DocumentInput,
        *,
        options: PDFTypographyOptions | None = None,
    ) -> PDFTypographyArtifact:
        await self._ensure_running()
        if self.pdf_typography_resolver is None:
            raise ConfigurationError("PDF typography resolution is not available")
        self._log("engine.pdf_typography.started")
        result = await self.pdf_typography_resolver.resolve(
            self._source_from_input(source),
            options,
        )
        self._log("engine.pdf_typography.completed")
        return result

    async def extract_pdf_native_images(
        self,
        source: DocumentInput,
        *,
        options: PDFImageExtractionOptions | None = None,
    ) -> PDFNativeImageArtifact:
        await self._ensure_running()
        if self.pdf_native_image_extractor is None:
            raise ConfigurationError("PDF native image extraction is not available")
        self._log("engine.pdf_native_images.started")
        result = await self.pdf_native_image_extractor.extract(
            self._source_from_input(source),
            options,
        )
        self._log("engine.pdf_native_images.completed")
        return result

    async def extract_pdf_native_text(
        self,
        source: DocumentInput,
        *,
        options: PDFNativeTextExtractionOptions | None = None,
    ) -> PDFNativeTextArtifact:
        await self._ensure_running()
        if self.pdf_native_text_extractor is None:
            raise ConfigurationError("PDF native text extraction is not available")
        self._log("engine.pdf_native_text.started")
        result = await self.pdf_native_text_extractor.extract(
            self._source_from_input(source),
            options,
        )
        self._log("engine.pdf_native_text.completed")
        return result

    async def extract_pdf_native_vectors(
        self,
        source: DocumentInput,
        *,
        options: PDFNativeVectorOptions | None = None,
    ) -> PDFNativeVectorArtifact:
        await self._ensure_running()
        if self.pdf_native_vector_extractor is None:
            raise ConfigurationError("PDF native vector extraction is not available")
        self._log("engine.pdf_native_vectors.started")
        result = await self.pdf_native_vector_extractor.extract(
            self._source_from_input(source),
            options,
        )
        self._log("engine.pdf_native_vectors.completed")
        return result

    async def extract_pdf_interactive(
        self,
        source: DocumentInput,
        *,
        options: PDFInteractiveExtractionOptions | None = None,
    ) -> PDFInteractiveArtifact:
        await self._ensure_running()
        if self.pdf_interactive_extractor is None:
            raise ConfigurationError("PDF interactive extraction is not available")
        self._log("engine.pdf_interactive.started")
        result = await self.pdf_interactive_extractor.extract(
            self._source_from_input(source),
            options,
        )
        self._log("engine.pdf_interactive.completed")
        return result

    async def parse(
        self,
        request_or_source: ParseRequest | DocumentInput,
        *,
        profile: str | None = None,
        pages: tuple[int, ...] | list[int] | None = None,
        options: dict[str, object] | None = None,
    ) -> ParseResult:
        request = (
            request_or_source
            if isinstance(request_or_source, ParseRequest)
            else ParseRequest(
                source=self._source_from_input(request_or_source),
                profile=profile,
                page_selection=tuple(pages) if pages is not None else None,
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
