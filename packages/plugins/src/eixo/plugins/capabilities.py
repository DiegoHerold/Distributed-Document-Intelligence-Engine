from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from eixo.core.enums import CapabilityStatus
from eixo.core.ids import CapabilityId, CorrelationId, ProviderId, TenantId, TraceId
from eixo.core.serialization import Serializable
from eixo.core.versions import CapabilityVersion, ProviderVersion

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


def normalize_format(value: str) -> str:
    normalized = value.strip().lower().lstrip(".")
    if not normalized:
        raise ValueError("format cannot be empty")
    return normalized


def normalize_media_type(value: str) -> str:
    normalized = value.strip().lower()
    if "/" not in normalized:
        raise ValueError("media type must contain '/'")
    return normalized


@dataclass(frozen=True, slots=True)
class ExecutionContext(Serializable):
    correlation_id: CorrelationId
    trace_id: TraceId | None = None
    tenant_id: TenantId | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor(Serializable):
    capability_id: CapabilityId
    name: str
    description: str
    version: CapabilityVersion
    input_contract: str
    output_contract: str
    supported_formats: tuple[str, ...] = ()
    supported_media_types: tuple[str, ...] = ()
    resource_class: str | None = None
    deterministic: bool = True
    supports_cancellation: bool = False
    supports_progress: bool = False
    provider_id: ProviderId | None = None
    provider_version: ProviderVersion | None = None
    status: CapabilityStatus = CapabilityStatus.ACTIVE
    priority: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("capability name cannot be empty")
        if not self.input_contract.strip() or not self.output_contract.strip():
            raise ValueError("input and output contracts are required")
        object.__setattr__(
            self,
            "supported_formats",
            tuple(sorted({normalize_format(v) for v in self.supported_formats})),
        )
        object.__setattr__(
            self,
            "supported_media_types",
            tuple(sorted({normalize_media_type(v) for v in self.supported_media_types})),
        )
        if self.priority < 0:
            raise ValueError("priority cannot be negative")
        if self.resource_class is not None and not self.resource_class.strip():
            raise ValueError("resource_class cannot be empty")

    def supports(
        self,
        *,
        input_contract: str | None = None,
        output_contract: str | None = None,
        document_format: str | None = None,
        media_type: str | None = None,
    ) -> bool:
        if input_contract is not None and self.input_contract != input_contract:
            return False
        if output_contract is not None and self.output_contract != output_contract:
            return False
        if document_format is not None:
            fmt = normalize_format(document_format)
            if self.supported_formats and fmt not in self.supported_formats:
                return False
        if media_type is not None:
            mt = normalize_media_type(media_type)
            if self.supported_media_types and mt not in self.supported_media_types:
                return False
        return True


@dataclass(frozen=True, slots=True)
class ProviderDescriptor(Serializable):
    provider_id: ProviderId
    name: str
    version: ProviderVersion
    status: CapabilityStatus = CapabilityStatus.ACTIVE
    capabilities: tuple[CapabilityId, ...] = ()
    configuration_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("provider name cannot be empty")


@runtime_checkable
class Capability(Protocol, Generic[InputT, OutputT]):
    descriptor: CapabilityDescriptor

    async def execute(self, request: InputT, context: ExecutionContext) -> OutputT:
        ...
