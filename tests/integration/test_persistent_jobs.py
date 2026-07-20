from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import anyio
import pytest

from eixo.core import (
    CapabilityId,
    CapabilityStatus,
    CapabilityVersion,
    DocumentId,
    JobStatus,
    JobResultUnavailableError,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
    ProviderId,
    ProviderVersion,
)
from eixo.engine import DocumentEngine
from eixo.plugins import CapabilityDescriptor, CapabilityRegistry, ExecutionContext
from eixo.plugins import ProviderDescriptor


@dataclass(slots=True)
class PersistentProcessCapability:
    descriptor: CapabilityDescriptor

    async def execute(
        self,
        request: ProcessingRequest,
        context: ExecutionContext,
    ) -> ProcessingResult:
        return ProcessingResult(
            job_id=__import__("eixo.core").core.JobId.new(),
            document_id=DocumentId.parse(request.source.metadata["document_id"]),
            status=ProcessingStatus.COMPLETED,
            data={"persisted": True},
        )


@pytest.mark.anyio
async def test_completed_job_survives_new_engine_instance(tmp_path: Path) -> None:
    registry = registry_with_process_capability()

    async with DocumentEngine.local(registry=registry, data_directory=tmp_path) as engine:
        job = await engine.submit(b"%PDF-1.7\n")
        result = await wait_for_job_result(engine, job.job_id)
        assert result.data == {"persisted": True}

    async with DocumentEngine.local(data_directory=tmp_path) as recovered_engine:
        status = await recovered_engine.get_job_status(job.job_id)
        recovered = await recovered_engine.get_job_result(job.job_id)

    assert status.status == JobStatus.COMPLETED
    assert recovered.data == {"persisted": True}


async def wait_for_job_result(engine: DocumentEngine, job_id) -> ProcessingResult:
    for _ in range(20):
        try:
            return await engine.get_job_result(job_id)
        except JobResultUnavailableError:
            await anyio.sleep(0.05)
    return await engine.get_job_result(job_id)


def registry_with_process_capability() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    provider_id = ProviderId.new()
    registry.register_provider(
        ProviderDescriptor(
            provider_id=provider_id,
            name="persistent-provider",
            version=ProviderVersion("1.0.0"),
            status=CapabilityStatus.ACTIVE,
        )
    )
    registry.register(
        PersistentProcessCapability(
            CapabilityDescriptor(
                capability_id=CapabilityId.new(),
                name="persistent-process",
                description="Persistent process test capability",
                version=CapabilityVersion("1.0.0"),
                input_contract="ProcessingRequest",
                output_contract="ProcessingResult",
                supported_formats=("pdf",),
                supported_media_types=("application/pdf",),
                provider_id=provider_id,
                provider_version=ProviderVersion("1.0.0"),
            )
        )
    )
    return registry
