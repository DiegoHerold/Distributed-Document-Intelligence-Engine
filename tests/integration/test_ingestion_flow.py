from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from eixo.core import (
    CapabilityId,
    CapabilityStatus,
    CapabilityVersion,
    DocumentId,
    InspectionRequest,
    InspectionResult,
    ProviderId,
    ProviderVersion,
    ResultStatus,
)
from eixo.engine import DocumentEngine
from eixo.plugins import CapabilityDescriptor, CapabilityRegistry, ExecutionContext
from eixo.plugins import ProviderDescriptor


@dataclass(slots=True)
class PdfInspectCapability:
    descriptor: CapabilityDescriptor

    async def execute(
        self,
        request: InspectionRequest,
        context: ExecutionContext,
    ) -> InspectionResult:
        return InspectionResult(
            document_id=DocumentId.new(),
            detected_format=request.source.metadata["detected_format"],
            declared_media_type=request.source.declared_media_type,
            detected_media_type="application/pdf",
            size=request.source.size,
            status=ResultStatus.SUCCESS,
            metadata={"content_hash": request.source.metadata["content_hash"]},
        )


@pytest.mark.anyio
async def test_engine_resolves_and_identifies_path_before_capability_lookup(
    tmp_path: Path,
) -> None:
    document = tmp_path / "misleading.bin"
    document.write_bytes(b"%PDF-1.7\n")
    registry = registry_with_pdf_inspector()

    async with DocumentEngine.local(registry=registry) as engine:
        result = await engine.inspect(str(document))

    assert result.detected_format == "pdf"
    assert result.detected_media_type == "application/pdf"
    assert result.size == document.stat().st_size
    assert result.metadata["content_hash"].startswith("sha256:")


def registry_with_pdf_inspector() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    provider_id = ProviderId.new()
    registry.register_provider(
        ProviderDescriptor(
            provider_id=provider_id,
            name="pdf-provider",
            version=ProviderVersion("1.0.0"),
            status=CapabilityStatus.ACTIVE,
        )
    )
    registry.register(
        PdfInspectCapability(
            CapabilityDescriptor(
                capability_id=CapabilityId.new(),
                name="pdf-inspect",
                description="PDF inspection test capability",
                version=CapabilityVersion("1.0.0"),
                input_contract="InspectionRequest",
                output_contract="InspectionResult",
                supported_formats=("pdf",),
                supported_media_types=("application/pdf",),
                provider_id=provider_id,
                provider_version=ProviderVersion("1.0.0"),
            )
        )
    )
    return registry
