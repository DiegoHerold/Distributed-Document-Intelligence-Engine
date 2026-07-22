from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from eixo import DocumentEngine
from eixo.core import (
    BytesSource,
    CapabilityId,
    CapabilityNotFoundError,
    CapabilityStatus,
    CapabilityVersion,
    CorrelationId,
    DocumentId,
    ExecutionTimeoutError,
    InspectionRequest,
    InspectionResult,
    JobId,
    JobStatus,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
    ProviderId,
    ProviderVersion,
    ResultStatus,
)
from eixo.plugins import (
    CapabilityDescriptor,
    CapabilityRegistry,
    ExecutionContext,
    ExecutionMode,
    ExecutionOptions,
    ExecutionStatus,
    ExecutionTask,
    ProviderDescriptor,
)
from eixo.engine.pdf_public import (
    PDF_INSPECT_CAPABILITY_ID,
    PDF_PARSE_CAPABILITY_ID,
    PDF_PROCESS_CAPABILITY_ID,
)
from eixo.runtime.local import LocalRuntime, LocalRuntimeConfig


def test_kernel_descriptor_declares_compatibility_and_execution_traits() -> None:
    descriptor = CapabilityDescriptor(
        capability_id=CapabilityId("cap_kernel"),
        name="kernel-process",
        description="Kernel test capability",
        version=CapabilityVersion("0.1.0"),
        input_contract="ProcessingRequest",
        output_contract="ProcessingResult",
        supported_formats=("PDF",),
        supported_media_types=("APPLICATION/PDF",),
        resource_class="cpu",
        deterministic=True,
        supports_cancellation=True,
        supports_progress=True,
        provider_id=ProviderId("prov_kernel"),
    )

    assert descriptor.supported_formats == ("pdf",)
    assert descriptor.supported_media_types == ("application/pdf",)
    assert descriptor.supports(
        input_contract="ProcessingRequest",
        output_contract="ProcessingResult",
        document_format=".pdf",
        media_type="application/pdf",
    )
    assert not descriptor.supports(document_format="xlsx")


def test_kernel_local_processing_flow_uses_registry_and_runtime() -> None:
    async def run() -> None:
        async with engine_with_kernel_capability() as engine:
            result = await engine.process(
                ProcessingRequest(source=source(), profile="balanced")
            )

        assert result.status is ProcessingStatus.COMPLETED
        assert result.data == {"processed_by": "kernel-fake", "profile": "balanced"}

    asyncio.run(run())


def test_kernel_job_flow_status_result_cancel_and_isolation() -> None:
    async def run() -> None:
        async with engine_with_kernel_capability() as engine:
            job = await engine.submit(ProcessingRequest(source=source()))
            assert job.status is JobStatus.QUEUED
            await asyncio.sleep(0.05)
            status = await engine.get_job_status(job.job_id)
            result = await engine.get_job_result(job.job_id)

        async with engine_with_kernel_capability(delay=0.2) as engine:
            cancel_job = await engine.submit(ProcessingRequest(source=source()))
            cancelled = await engine.cancel_job(cancel_job.job_id)

        assert status.status is JobStatus.COMPLETED
        assert result.status is ProcessingStatus.COMPLETED
        assert cancelled.status is JobStatus.CANCELLED


def test_kernel_engines_do_not_share_mutable_state() -> None:
    first = engine_with_kernel_capability()
    second = DocumentEngine.local()
    first_capability_ids = {
        capability.capability_id for capability in first.registry.list_capabilities()
    }
    second_capability_ids = {
        capability.capability_id for capability in second.registry.list_capabilities()
    }

    assert first.registry is not second.registry
    assert first.runtime is not second.runtime
    assert first_capability_ids == {
        CapabilityId("cap_kernel_process"),
        PDF_INSPECT_CAPABILITY_ID,
        PDF_PARSE_CAPABILITY_ID,
        PDF_PROCESS_CAPABILITY_ID,
    }
    assert second_capability_ids == {
        PDF_INSPECT_CAPABILITY_ID,
        PDF_PARSE_CAPABILITY_ID,
        PDF_PROCESS_CAPABILITY_ID,
    }


def test_kernel_missing_capability_and_timeout_are_structured() -> None:
    async def run() -> None:
        async with DocumentEngine.local() as engine:
            with pytest.raises(CapabilityNotFoundError):
                await engine.process(ProcessingRequest(source=csv_source()))

        async with engine_with_kernel_capability(
            delay=0.2,
            timeout=0.01,
        ) as engine:
            with pytest.raises(ExecutionTimeoutError):
                await engine.process(ProcessingRequest(source=source()))

    asyncio.run(run())


def test_kernel_runtime_progress_cancel_and_failure_contracts() -> None:
    async def run() -> None:
        updates = []
        async with LocalRuntime(LocalRuntimeConfig(default_timeout=0.05)) as runtime:
            progress_handle = await runtime.submit(
                ExecutionTask(
                    task_id="task_kernel_progress",
                    name="kernel-progress",
                    handler=progress_task,
                    input=1,
                ),
                context=ExecutionContext(correlation_id=CorrelationId.new()),
                options=ExecutionOptions(disable_timeout=True),
            )
            progress_handle._progress.subscribe(updates.append)
            progress_result = await progress_handle.wait()

            cancel_handle = await runtime.submit(
                ExecutionTask(
                    task_id="task_kernel_cancel",
                    name="kernel-cancel",
                    handler=slow_task,
                    input=1,
                    execution_mode=ExecutionMode.ASYNC,
                ),
                context=ExecutionContext(correlation_id=CorrelationId.new()),
                options=ExecutionOptions(disable_timeout=True),
            )
            await cancel_handle.cancel()
            cancel_result = await cancel_handle.wait()

            failure = await runtime.execute(
                ExecutionTask(
                    task_id="task_kernel_failure",
                    name="kernel-failure",
                    handler=failing_task,
                    input=1,
                ),
                context=ExecutionContext(correlation_id=CorrelationId.new()),
                options=ExecutionOptions(disable_timeout=True),
            )

        assert progress_result.status is ExecutionStatus.COMPLETED
        assert updates
        assert cancel_result.status is ExecutionStatus.CANCELLED
        assert failure.status is ExecutionStatus.FAILED
        assert failure.error is not None
        assert failure.error.code == "execution.error"

    asyncio.run(run())


async def progress_task(value: int, context) -> int:
    assert context.progress is not None
    await context.progress.report(current=1, total=2, stage="kernel")
    return value


async def slow_task(value: int, context) -> int:
    await asyncio.sleep(1)
    return value


async def failing_task(value: int, context) -> int:
    raise RuntimeError("kernel failure")


def engine_with_kernel_capability(
    *,
    delay: float = 0.0,
    timeout: float = 30.0,
) -> DocumentEngine:
    registry = CapabilityRegistry()
    provider_id = ProviderId("prov_kernel")
    registry.register_provider(
        ProviderDescriptor(
            provider_id=provider_id,
            name="kernel-provider",
            version=ProviderVersion("0.1.0"),
            status=CapabilityStatus.ACTIVE,
        )
    )
    registry.register(KernelProcessCapability(provider_id=provider_id, delay=delay))
    return DocumentEngine.local(
        registry=registry,
        default_timeout=timeout,
    )


def source() -> BytesSource:
    content = b"%PDF-1.7\n"
    return BytesSource(
        content=content,
        filename="kernel.pdf",
        declared_media_type="application/pdf",
        size=len(content),
    )


def csv_source() -> BytesSource:
    content = b"a,b\n1,2\n"
    return BytesSource(
        content=content,
        filename="kernel.csv",
        declared_media_type="text/csv",
        size=len(content),
    )


@dataclass(frozen=True, slots=True)
class KernelProcessCapability:
    provider_id: ProviderId
    delay: float = 0.0

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            capability_id=CapabilityId("cap_kernel_process"),
            name="kernel-process",
            description="Kernel processing capability",
            version=CapabilityVersion("0.1.0"),
            input_contract="ProcessingRequest",
            output_contract="ProcessingResult",
            supported_media_types=("application/pdf",),
            deterministic=True,
            supports_cancellation=True,
            supports_progress=True,
            provider_id=self.provider_id,
            provider_version=ProviderVersion("0.1.0"),
        )

    async def execute(
        self,
        request: ProcessingRequest,
        context: ExecutionContext,
    ) -> ProcessingResult:
        if self.delay:
            await asyncio.sleep(self.delay)
        return ProcessingResult(
            job_id=JobId.new(),
            document_id=DocumentId("doc_kernel"),
            status=ProcessingStatus.COMPLETED,
            data={"processed_by": "kernel-fake", "profile": request.profile},
        )


@dataclass(frozen=True, slots=True)
class KernelInspectCapability:
    provider_id: ProviderId

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            capability_id=CapabilityId("cap_kernel_inspect"),
            name="kernel-inspect",
            description="Kernel inspection capability",
            version=CapabilityVersion("0.1.0"),
            input_contract="InspectionRequest",
            output_contract="InspectionResult",
            supported_media_types=("application/pdf",),
            provider_id=self.provider_id,
        )

    async def execute(
        self,
        request: InspectionRequest,
        context: ExecutionContext,
    ) -> InspectionResult:
        return InspectionResult(
            document_id=DocumentId("doc_kernel"),
            detected_format="pdf",
            declared_media_type=request.source.declared_media_type,
            detected_media_type=request.source.declared_media_type,
            size=request.source.size,
            status=ResultStatus.SUCCESS,
        )
