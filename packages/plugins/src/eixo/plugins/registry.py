from __future__ import annotations

from threading import RLock
from typing import Any

from eixo.core.enums import CapabilityStatus
from eixo.core.errors import (
    CapabilityAlreadyRegisteredError,
    CapabilityNotFoundError,
    ConfigurationError,
    IncompatibleCapabilityError,
)
from eixo.core.ids import CapabilityId, ProviderId
from eixo.plugins.capabilities import (
    Capability,
    CapabilityDescriptor,
    ProviderDescriptor,
    normalize_format,
    normalize_media_type,
)


class CapabilityRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._providers: dict[ProviderId, ProviderDescriptor] = {}
        self._capabilities: dict[CapabilityId, Capability[Any, Any]] = {}

    def register_provider(self, provider: ProviderDescriptor) -> None:
        with self._lock:
            if provider.provider_id in self._providers:
                raise CapabilityAlreadyRegisteredError(
                    f"Provider already registered: {provider.provider_id}"
                )
            self._providers[provider.provider_id] = provider

    def unregister_provider(self, provider_id: ProviderId) -> None:
        with self._lock:
            if any(
                cap.descriptor.provider_id == provider_id for cap in self._capabilities.values()
            ):
                raise ConfigurationError("provider still has registered capabilities")
            self._providers.pop(provider_id, None)

    def register(self, capability: Capability[Any, Any]) -> None:
        descriptor = capability.descriptor
        with self._lock:
            if descriptor.provider_id is None:
                raise ConfigurationError("capability provider_id is required")
            if descriptor.provider_id not in self._providers:
                raise ConfigurationError("capability provider is not registered")
            if descriptor.capability_id in self._capabilities:
                raise CapabilityAlreadyRegisteredError(
                    f"Capability already registered: {descriptor.capability_id}"
                )
            if descriptor.status != CapabilityStatus.ACTIVE:
                raise IncompatibleCapabilityError("only active capabilities can be registered")
            self._capabilities[descriptor.capability_id] = capability

    def unregister(self, capability_id: CapabilityId) -> None:
        with self._lock:
            self._capabilities.pop(capability_id, None)

    def get(self, capability_id: CapabilityId) -> Capability[Any, Any]:
        with self._lock:
            try:
                return self._capabilities[capability_id]
            except KeyError as exc:
                raise CapabilityNotFoundError(
                    f"Capability not found: {capability_id}",
                    details={"capability_id": str(capability_id)},
                ) from exc

    def list_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        with self._lock:
            return tuple(cap.descriptor for cap in self._capabilities.values())

    def list_providers(self) -> tuple[ProviderDescriptor, ...]:
        with self._lock:
            return tuple(self._providers.values())

    def list_versions(self, capability_id: CapabilityId) -> tuple[str, ...]:
        with self._lock:
            versions = [
                str(cap.descriptor.version)
                for cap in self._capabilities.values()
                if cap.descriptor.capability_id == capability_id
            ]
            return tuple(sorted(set(versions)))

    def find_by_format(self, document_format: str) -> tuple[Capability[Any, Any], ...]:
        fmt = normalize_format(document_format)
        with self._lock:
            return tuple(
                cap
                for cap in self._capabilities.values()
                if cap.descriptor.supports(document_format=fmt)
                and cap.descriptor.supported_formats
            )

    def find_by_contracts(
        self,
        *,
        input_contract: str | None = None,
        output_contract: str | None = None,
    ) -> tuple[Capability[Any, Any], ...]:
        with self._lock:
            return tuple(
                cap
                for cap in self._capabilities.values()
                if cap.descriptor.supports(
                    input_contract=input_contract,
                    output_contract=output_contract,
                )
            )

    def resolve(
        self,
        *,
        capability_id: CapabilityId | None = None,
        document_format: str | None = None,
        media_type: str | None = None,
        input_contract: str | None = None,
        output_contract: str | None = None,
    ) -> Capability[Any, Any]:
        with self._lock:
            candidates = list(self._capabilities.values())
            if capability_id is not None:
                candidates = [
                    cap
                    for cap in candidates
                    if cap.descriptor.capability_id == capability_id
                ]
            if document_format is not None:
                fmt = normalize_format(document_format)
                candidates = [
                    cap
                    for cap in candidates
                    if cap.descriptor.supports(document_format=fmt)
                ]
            if media_type is not None:
                mt = normalize_media_type(media_type)
                candidates = [
                    cap
                    for cap in candidates
                    if cap.descriptor.supports(media_type=mt)
                ]
            if input_contract is not None:
                candidates = [
                    cap
                    for cap in candidates
                    if cap.descriptor.supports(input_contract=input_contract)
                ]
            if output_contract is not None:
                candidates = [
                    cap
                    for cap in candidates
                    if cap.descriptor.supports(output_contract=output_contract)
                ]
            active = [
                cap
                for cap in candidates
                if cap.descriptor.status == CapabilityStatus.ACTIVE
                and cap.descriptor.provider_id in self._providers
                and self._providers[cap.descriptor.provider_id].status == CapabilityStatus.ACTIVE
            ]
            if not active:
                raise CapabilityNotFoundError("No compatible capability found")
            ordered = sorted(active, key=lambda cap: cap.descriptor.priority)
            same_priority = (
                len(ordered) > 1
                and ordered[0].descriptor.priority == ordered[1].descriptor.priority
            )
            if same_priority:
                raise IncompatibleCapabilityError(
                    "Multiple compatible capabilities have same priority"
                )
            return ordered[0]
