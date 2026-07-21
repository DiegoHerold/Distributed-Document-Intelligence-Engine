from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Iterable

from eixo.core.errors import ConfigurationError, PDFProviderUnavailableError
from eixo.core.ids import ProviderId
from eixo.pdf.contracts import PDFProvider
from eixo.pdf.models import PDFProviderDescriptor, PDFSupportLevel


@dataclass(slots=True)
class PDFProviderRegistry:
    _providers: dict[ProviderId, PDFProvider] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def register(self, provider: PDFProvider) -> None:
        descriptor = provider.descriptor
        with self._lock:
            if descriptor.provider_id in self._providers:
                raise ConfigurationError(
                    f"PDF provider already registered: {descriptor.provider_id}"
                )
            self._providers[descriptor.provider_id] = provider

    def unregister(self, provider_id: ProviderId | str) -> None:
        with self._lock:
            self._providers.pop(_provider_id(provider_id), None)

    def list_providers(self) -> tuple[PDFProviderDescriptor, ...]:
        with self._lock:
            return tuple(provider.descriptor for provider in self._providers.values())

    def get(self, provider_id: ProviderId | str) -> PDFProvider:
        wanted = _provider_id(provider_id)
        with self._lock:
            try:
                return self._providers[wanted]
            except KeyError as exc:
                raise PDFProviderUnavailableError(
                    "PDF provider is not registered",
                    public_context={"provider_id": str(wanted)},
                ) from exc

    def resolve(
        self,
        *,
        preferred_provider: ProviderId | str | None = None,
        required_capabilities: Iterable[str] = (),
    ) -> PDFProvider:
        with self._lock:
            candidates = list(self._providers.values())
            if preferred_provider is not None:
                wanted = _provider_id(preferred_provider)
                candidates = [
                    provider
                    for provider in candidates
                    if provider.descriptor.provider_id == wanted
                ]
            required = tuple(required_capabilities)
            candidates = [
                provider
                for provider in candidates
                if _supports_required(provider, required)
            ]
            if not candidates:
                raise PDFProviderUnavailableError("No compatible PDF provider is registered")
            return sorted(
                candidates,
                key=lambda provider: str(provider.descriptor.provider_id),
            )[0]


def _provider_id(value: ProviderId | str) -> ProviderId:
    return value if isinstance(value, ProviderId) else ProviderId.parse(value)


def _supports_required(provider: PDFProvider, names: tuple[str, ...]) -> bool:
    for name in names:
        if provider.capabilities.support_for(name) not in {
            PDFSupportLevel.SUPPORTED,
            PDFSupportLevel.EXPERIMENTAL,
        }:
            return False
    return True


__all__ = ["PDFProviderRegistry"]
