from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from eixo import DocumentEngine as PublicDocumentEngine
from eixo.core import (
    BytesSource,
    CapabilityId,
    CapabilityNotFoundError,
    CapabilityStatus,
    CapabilityVersion,
    DocumentId,
    InspectionRequest,
    InspectionResult,
    InvalidStateTransitionError,
    JobStatus,
    ParseRequest,
    ParseResult,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
    ProviderId,
    ProviderVersion,
    ResultStatus,
)
from eixo.engine import DocumentEngine, EngineState, LocalEngineConfig
from eixo.plugins import CapabilityDescriptor, CapabilityRegistry, ExecutionContext
from eixo.plugins import ProviderDescriptor
from eixo.runtime.local import LocalRuntime, LocalRuntimeConfig


@dataclass(slots=True)
class FakeInspectCapability:
    descriptor: CapabilityDescriptor

    async def execute(
        self,
        request: InspectionRequest,
        context: ExecutionContext,
    ) -> InspectionResult:
        return InspectionResult(
            document_id=DocumentId.new(),
            detected_format="bytes",
            declared_media_type=request.source.declared_media_type,
            detected_media_type="application/octet-stream",
            size=request.source.size,
            status=ResultStatus.SUCCESS,
            metadata={"correlation_id": str(context.correlation_id)},
        )


@dataclass(slots=True)
class FakeParseCapability:
    descriptor: CapabilityDescriptor

    async def execute(self, request: ParseRequest, context: ExecutionContext) -> ParseResult:
        return ParseResult(document_id=DocumentId.new(), status=ResultStatus.SUCCESS)


@dataclass(slots=True)
class FakeProcessCapability:
    descriptor: CapabilityDescriptor
    delay: float = 0.0

    async def execute(
        self,
        request: ProcessingRequest,
        context: ExecutionContext,
    ) -> ProcessingResult:
        if self.delay:
            await asyncio.sleep(self.delay)
        return ProcessingResult(
            job_id=__import__("eixo.core").core.JobId.new(),
            document_id=DocumentId.new(),
            status=ProcessingStatus.COMPLETED,
            data={"profile": request.profile, "correlation_id": str(context.correlation_id)},
        )


def descriptor(
    *,
    capability_id: CapabilityId,
    provider_id: ProviderId,
    name: str,
    input_contract: str,
    output_contract: str,
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        name=name,
        description=name,
        version=CapabilityVersion("1.0.0"),
        input_contract=input_contract,
        output_contract=output_contract,
        supported_formats=("bytes",),
        supported_media_types=("application/octet-stream",),
        provider_id=provider_id,
        provider_version=ProviderVersion("1.0.0"),
    )


def registry_with_fakes(*, slow_process: bool = False) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    provider_id = ProviderId.new()
    registry.register_provider(
        ProviderDescriptor(
            provider_id=provider_id,
            name="fake-provider",
            version=ProviderVersion("1.0.0"),
            status=CapabilityStatus.ACTIVE,
        )
    )
    registry.register(
        FakeInspectCapability(
            descriptor(
                capability_id=CapabilityId.new(),
                provider_id=provider_id,
                name="inspect",
                input_contract="InspectionRequest",
                output_contract="InspectionResult",
            )
        )
    )
    registry.register(
        FakeParseCapability(
            descriptor(
                capability_id=CapabilityId.new(),
                provider_id=provider_id,
                name="parse",
                input_contract="ParseRequest",
                output_contract="ParseResult",
            )
        )
    )
    registry.register(
        FakeProcessCapability(
            descriptor(
                capability_id=CapabilityId.new(),
                provider_id=provider_id,
                name="process",
                input_contract="ProcessingRequest",
                output_contract="ProcessingResult",
            ),
            delay=0.2 if slow_process else 0.0,
        )
    )
    return registry


def source() -> BytesSource:
    return BytesSource(
        content=b"hello",
        size=5,
        filename="sample.bin",
        declared_media_type="application/octet-stream",
    )


def test_public_imports_expose_document_engine() -> None:
    assert PublicDocumentEngine is DocumentEngine


def test_local_factory_defaults_custom_config_and_injection() -> None:
    runtime = LocalRuntime(LocalRuntimeConfig(max_concurrent_tasks=3))
    registry = registry_with_fakes()
    engine = DocumentEngine.local(
        config=LocalEngineConfig(runtime=LocalRuntimeConfig(max_concurrent_tasks=2)),
        runtime=runtime,
        registry=registry,
    )

    assert engine.runtime is runtime
    assert engine.registry is registry
    assert engine.config.runtime.max_concurrent_tasks == 2


def test_local_factory_accepts_provider_and_capability_registration() -> None:
    provider_id = ProviderId.new()
    capability = FakeInspectCapability(
        descriptor(
            capability_id=CapabilityId.new(),
            provider_id=provider_id,
            name="inspect",
            input_contract="InspectionRequest",
            output_contract="InspectionResult",
        )
    )
    engine = DocumentEngine.local(
        providers=(
            ProviderDescriptor(
                provider_id=provider_id,
                name="fake-provider",
                version=ProviderVersion("1.0.0"),
            ),
        ),
        capabilities=(capability,),
    )

    assert engine.registry.list_capabilities()[0].name == "inspect"


def test_lifecycle_auto_start_context_manager_and_reject_after_shutdown() -> None:
    async def run() -> None:
        engine = DocumentEngine.local(registry=registry_with_fakes())
        assert engine.state is EngineState.CREATED
        inspected = await engine.inspect(source())
        assert inspected.status is ResultStatus.SUCCESS
        assert engine.state is EngineState.RUNNING
        await engine.start()
        await engine.shutdown()
        await engine.shutdown()
        with pytest.raises(InvalidStateTransitionError):
            await engine.inspect(source())

        async with DocumentEngine.local(registry=registry_with_fakes()) as ctx_engine:
            assert ctx_engine.state is EngineState.RUNNING
        assert ctx_engine.state is EngineState.STOPPED

    asyncio.run(run())


def test_inspect_parse_and_process_delegate_to_application_use_cases() -> None:
    async def run() -> None:
        async with DocumentEngine.local(registry=registry_with_fakes()) as engine:
            inspected = await engine.inspect(source())
            parsed = await engine.parse(ParseRequest(source=source()))
            processed = await engine.process(
                ProcessingRequest(source=source(), profile="fast")
            )

            assert inspected.metadata["correlation_id"].startswith("corr_")
            assert parsed.status is ResultStatus.SUCCESS
            assert processed.status is ProcessingStatus.COMPLETED
            assert processed.data["profile"] == "fast"

    asyncio.run(run())


def test_capability_absent_is_preserved_as_domain_error() -> None:
    async def run() -> None:
        engine = DocumentEngine.local()
        with pytest.raises(CapabilityNotFoundError):
            await engine.inspect(source())
        await engine.shutdown()

    asyncio.run(run())


def test_submit_status_result_and_cancel_job() -> None:
    async def run() -> None:
        async with DocumentEngine.local(registry=registry_with_fakes()) as engine:
            job = await engine.submit(ProcessingRequest(source=source()))
            assert job.status is JobStatus.QUEUED
            await asyncio.sleep(0.1)
            status = await engine.get_job_status(job.job_id)
            result = await engine.get_job_result(job.job_id)
            assert status.status in {JobStatus.COMPLETED, JobStatus.RUNNING}
            assert result.status is ProcessingStatus.COMPLETED

        async with DocumentEngine.local(
            registry=registry_with_fakes(slow_process=True)
        ) as engine:
            job = await engine.submit(ProcessingRequest(source=source()))
            cancelled = await engine.cancel_job(job.job_id)
            assert cancelled.status is JobStatus.CANCELLED

    asyncio.run(run())


def test_concurrent_operations_keep_context_isolated() -> None:
    async def run() -> None:
        async with DocumentEngine.local(registry=registry_with_fakes()) as engine:
            results = await asyncio.gather(
                *(engine.inspect(source()) for _ in range(5))
            )
            correlation_ids = {result.metadata["correlation_id"] for result in results}
            assert len(correlation_ids) == 5

    asyncio.run(run())
