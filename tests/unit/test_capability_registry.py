from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from eixo.core import (
    CapabilityAlreadyRegisteredError,
    CapabilityId,
    CapabilityNotFoundError,
    CapabilityStatus,
    CapabilityVersion,
    CorrelationId,
    IncompatibleCapabilityError,
    ProviderId,
    ProviderVersion,
)
from eixo.plugins import (
    CapabilityDescriptor,
    CapabilityRegistry,
    ExecutionContext,
    ProviderDescriptor,
)


@dataclass(slots=True)
class FakeCapability:
    descriptor: CapabilityDescriptor

    async def execute(self, request: str, context: ExecutionContext) -> str:
        return f"{request}:{context.correlation_id}"


def make_registry() -> tuple[CapabilityRegistry, FakeCapability]:
    registry = CapabilityRegistry()
    provider_id = ProviderId.new()
    registry.register_provider(
        ProviderDescriptor(
            provider_id=provider_id,
            name="fake",
            version=ProviderVersion("1.0.0"),
            status=CapabilityStatus.ACTIVE,
        )
    )
    capability = FakeCapability(
        CapabilityDescriptor(
            capability_id=CapabilityId.new(),
            name="inspect",
            description="Fake inspection",
            version=CapabilityVersion("1.0.0"),
            input_contract="InspectionRequest",
            output_contract="InspectionResult",
            supported_formats=("PDF",),
            supported_media_types=("application/pdf",),
            provider_id=provider_id,
            provider_version=ProviderVersion("1.0.0"),
        )
    )
    return registry, capability


def test_register_find_and_execute_capability() -> None:
    registry, capability = make_registry()
    registry.register(capability)

    resolved = registry.resolve(document_format="pdf", input_contract="InspectionRequest")
    output = asyncio.run(
        resolved.execute("request", ExecutionContext(correlation_id=CorrelationId.new()))
    )

    assert output.startswith("request:corr_")
    assert registry.find_by_format(".PDF")[0].descriptor.name == "inspect"
    assert registry.find_by_contracts(output_contract="InspectionResult")


def test_registry_rejects_duplicates_and_missing_capabilities() -> None:
    registry, capability = make_registry()
    registry.register(capability)

    with pytest.raises(CapabilityAlreadyRegisteredError):
        registry.register(capability)
    with pytest.raises(CapabilityNotFoundError):
        registry.get(CapabilityId.new())


def test_registry_detects_ambiguous_resolution() -> None:
    registry, capability = make_registry()
    registry.register(capability)
    provider_id = capability.descriptor.provider_id
    assert provider_id is not None
    other = FakeCapability(
        CapabilityDescriptor(
            capability_id=CapabilityId.new(),
            name="inspect-other",
            description="Fake inspection",
            version=CapabilityVersion("1.0.0"),
            input_contract="InspectionRequest",
            output_contract="InspectionResult",
            supported_formats=("pdf",),
            supported_media_types=("application/pdf",),
            provider_id=provider_id,
            provider_version=ProviderVersion("1.0.0"),
        )
    )
    registry.register(other)

    with pytest.raises(IncompatibleCapabilityError):
        registry.resolve(document_format="pdf")

