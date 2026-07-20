from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from eixo.core import (
    CapabilityId,
    CapabilityStatus,
    CapabilityVersion,
    DocumentId,
    DocumentStatus,
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
class StoredInspectCapability:
    descriptor: CapabilityDescriptor

    async def execute(
        self,
        request: InspectionRequest,
        context: ExecutionContext,
    ) -> InspectionResult:
        return InspectionResult(
            document_id=DocumentId.parse(request.source.metadata["document_id"]),
            detected_format=request.source.metadata["detected_format"],
            declared_media_type=request.source.declared_media_type,
            detected_media_type="application/pdf",
            size=request.source.size,
            status=ResultStatus.SUCCESS,
            metadata={
                "artifact_id": request.source.metadata["artifact_id"],
                "content_hash": request.source.metadata["content_hash"],
            },
        )


@pytest.mark.anyio
async def test_engine_ingest_stores_original_and_document_record(tmp_path: Path) -> None:
    async with DocumentEngine.local(data_directory=tmp_path) as engine:
        result = await engine.ingest(b"%PDF-1.7\n")

    assert result.status == DocumentStatus.STORED
    assert result.original_artifact.storage_key is not None
    assert not Path(result.original_artifact.storage_key).is_absolute()
    assert (tmp_path / "documents" / str(result.document_id) / "document.json").exists()
    assert (
        tmp_path
        / "documents"
        / str(result.document_id)
        / "transitions.jsonl"
    ).exists()


@pytest.mark.anyio
async def test_inspect_uses_storage_flow_before_capability(tmp_path: Path) -> None:
    registry = registry_with_stored_inspector()

    async with DocumentEngine.local(registry=registry, data_directory=tmp_path) as engine:
        result = await engine.inspect(b"%PDF-1.7\n")

    assert result.detected_format == "pdf"
    assert result.document_id is not None
    assert result.metadata["artifact_id"].startswith("art_")
    assert result.metadata["content_hash"].startswith("sha256:")
    assert (tmp_path / "documents" / str(result.document_id) / "document.json").exists()


def registry_with_stored_inspector() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    provider_id = ProviderId.new()
    registry.register_provider(
        ProviderDescriptor(
            provider_id=provider_id,
            name="stored-provider",
            version=ProviderVersion("1.0.0"),
            status=CapabilityStatus.ACTIVE,
        )
    )
    registry.register(
        StoredInspectCapability(
            CapabilityDescriptor(
                capability_id=CapabilityId.new(),
                name="stored-inspect",
                description="Stored inspect test capability",
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
