from __future__ import annotations

import asyncio
from dataclasses import dataclass

from eixo import BytesSource, DocumentEngine, ProcessingRequest, ProcessingResult, ProcessingStatus
from eixo.core import (
    CapabilityId,
    CapabilityStatus,
    CapabilityVersion,
    DocumentId,
    JobId,
    ProviderId,
    ProviderVersion,
)
from eixo.plugins import CapabilityDescriptor, ExecutionContext, ProviderDescriptor


@dataclass(slots=True)
class EchoProcessingCapability:
    descriptor: CapabilityDescriptor

    async def execute(
        self,
        request: ProcessingRequest,
        context: ExecutionContext,
    ) -> ProcessingResult:
        return ProcessingResult(
            job_id=JobId.new(),
            document_id=DocumentId.new(),
            status=ProcessingStatus.COMPLETED,
            data={"filename": request.source.filename, "echo": True},
        )


async def main() -> None:
    provider_id = ProviderId.new()
    provider = ProviderDescriptor(
        provider_id=provider_id,
        name="example-provider",
        version=ProviderVersion("1.0.0"),
        status=CapabilityStatus.ACTIVE,
    )
    capability = EchoProcessingCapability(
        CapabilityDescriptor(
            capability_id=CapabilityId.new(),
            name="example-processing",
            description="Educational example capability.",
            version=CapabilityVersion("1.0.0"),
            input_contract="ProcessingRequest",
            output_contract="ProcessingResult",
            supported_formats=("pdf",),
            supported_media_types=("application/pdf",),
            provider_id=provider_id,
            provider_version=ProviderVersion("1.0.0"),
        )
    )
    source = BytesSource(
        content=b"%PDF-1.7\n",
        filename="example.pdf",
        declared_media_type="application/pdf",
        size=9,
    )
    async with DocumentEngine.local(providers=(provider,), capabilities=(capability,)) as engine:
        result = await engine.process(ProcessingRequest(source=source))
        print(result.status.value)
        print(result.data["filename"])


if __name__ == "__main__":
    asyncio.run(main())
