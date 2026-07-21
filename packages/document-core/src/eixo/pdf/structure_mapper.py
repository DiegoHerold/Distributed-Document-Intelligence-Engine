from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Awaitable

from eixo.core import DocumentSource, EixoWarning
from eixo.core.versions import ContractVersion
from eixo.pdf.contracts import PDFDocumentHandle, PDFProvider
from eixo.pdf.models import (
    PDFProviderDescriptor,
    PDFProviderProvenance,
    ProviderLimitation,
)
from eixo.pdf.registry import PDFProviderRegistry
from eixo.pdf.structure import (
    PDFInternalMappingOptions,
    PDFInternalPageMap,
    PDFInternalStructureArtifact,
    PDFMappingStatus,
    PDFObjectGraph,
    PDFPageReference,
    PDFProviderCapabilityMatrixEntry,
    PDFProviderSupportStatus,
    PDFResourceCatalog,
)


@dataclass(frozen=True, slots=True)
class DefaultPDFInternalStructureMapper:
    provider_registry: PDFProviderRegistry

    async def map(
        self,
        source: DocumentSource,
        options: PDFInternalMappingOptions | None = None,
    ) -> PDFInternalStructureArtifact:
        opts = options or PDFInternalMappingOptions()
        provider = self.provider_registry.resolve(
            preferred_provider=opts.preferred_provider,
            required_capabilities=("supports_basic_info",),
        )
        async with await provider.open(source) as document:
            return await self.map_document(document, opts, provider=provider)

    async def map_document(
        self,
        document: PDFDocumentHandle,
        options: PDFInternalMappingOptions | None = None,
        *,
        provider: PDFProvider | None = None,
    ) -> PDFInternalStructureArtifact:
        opts = options or PDFInternalMappingOptions()
        native_mapper = getattr(document, "get_internal_structure", None)
        if native_mapper is not None:
            value = native_mapper(opts)
            if isinstance(value, Awaitable):
                value = await value
            if isinstance(value, PDFInternalStructureArtifact):
                return value
        return await _fallback_structure(document, opts, provider=provider)


async def _fallback_structure(
    document: PDFDocumentHandle,
    options: PDFInternalMappingOptions,
    *,
    provider: PDFProvider | None,
) -> PDFInternalStructureArtifact:
    started = time.perf_counter()
    descriptor = (
        provider.descriptor if provider is not None else _descriptor_from_document(document)
    )
    page_count = await document.get_page_count()
    pages = tuple(
        PDFInternalPageMap(
            page_reference=PDFPageReference(page_index=index, page_number=index + 1),
            provenance=_provenance(
                descriptor,
                operation="map_internal_structure.page_fallback",
                source=document.source,
                options=options,
            ),
        )
        for index in range(page_count)
    )
    return PDFInternalStructureArtifact(
        artifact_version=ContractVersion("1.0.0"),
        provider=descriptor,
        object_graph=PDFObjectGraph(),
        resource_catalog=PDFResourceCatalog(),
        pages=pages,
        capability_matrix=_fallback_capability_matrix(),
        warnings=(
            EixoWarning(
                code="pdf.structure.unsupported_by_provider",
                message=(
                    "Provider document handle does not expose internal PDF "
                    "structure mapping."
                ),
            ),
        ),
        limitations=descriptor.limitations
        + (
            ProviderLimitation(
                code="internal_structure_mapping_unavailable",
                message="Provider did not expose object graph/resource catalog mapping.",
                scope="provider",
            ),
        ),
        provenance=_provenance(
            descriptor,
            operation="map_internal_structure.fallback",
            source=document.source,
            options=options,
            duration_seconds=time.perf_counter() - started,
        ),
    )


def _fallback_capability_matrix() -> tuple[PDFProviderCapabilityMatrixEntry, ...]:
    return tuple(
        PDFProviderCapabilityMatrixEntry(
            feature=feature,
            support=PDFProviderSupportStatus.UNSUPPORTED,
            strategy="fallback_artifact_records_pages_only",
            limitation="unsupported_by_provider",
        )
        for feature in (
            "indirect_objects",
            "xref",
            "content_streams",
            "content_operations",
            "fonts",
            "images",
            "xobjects",
            "graphic_states",
            "color_spaces",
            "patterns",
            "shadings",
            "optional_layers",
            "paint_order",
        )
    )


def _descriptor_from_document(document: PDFDocumentHandle) -> PDFProviderDescriptor:
    descriptor = getattr(document, "descriptor", None)
    if isinstance(descriptor, PDFProviderDescriptor):
        return descriptor
    raise ValueError("document handle does not expose a PDF provider descriptor")


def _provenance(
    descriptor: PDFProviderDescriptor,
    *,
    operation: str,
    source: DocumentSource,
    options: PDFInternalMappingOptions,
    duration_seconds: float | None = None,
) -> PDFProviderProvenance:
    safe_options = options.safe_options()
    if duration_seconds is not None:
        safe_options = safe_options | {"duration_seconds": duration_seconds}
    return PDFProviderProvenance(
        provider_id=descriptor.provider_id,
        provider_version=descriptor.provider_version,
        backend_name=descriptor.backend_name,
        backend_version=descriptor.backend_version,
        operation=operation,
        source_reference=source.origin_reference,
        source_hash=source.metadata.get("content_hash"),
        options=safe_options,
    )


__all__ = ["DefaultPDFInternalStructureMapper"]
