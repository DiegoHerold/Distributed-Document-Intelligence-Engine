from __future__ import annotations

from eixo.core import DocumentSource, EixoWarning
from eixo.core.versions import ContractVersion
from eixo.pdf.contracts import PDFDocumentHandle
from eixo.pdf.images import (
    PDFImageCapabilityMatrixEntry,
    PDFImageCatalog,
    PDFImageExtractionOptions,
    PDFImageResource,
    PDFImageSupportStatus,
    PDFNativeImageArtifact,
    PDFNativeImageStatistics,
    PDFPageImageLayer,
)
from eixo.pdf.models import ProviderLimitation
from eixo.pdf.registry import PDFProviderRegistry
from eixo.pdf.structure import PDFInternalMappingOptions, PDFInternalStructureArtifact
from eixo.pdf.structure_mapper import DefaultPDFInternalStructureMapper


class DefaultPDFNativeImageExtractor:
    def __init__(
        self,
        registry: PDFProviderRegistry,
        *,
        structure_mapper: DefaultPDFInternalStructureMapper | None = None,
    ) -> None:
        self._registry = registry
        self._structure_mapper = structure_mapper or DefaultPDFInternalStructureMapper(registry)

    async def extract(
        self,
        source: DocumentSource,
        options: PDFImageExtractionOptions | None = None,
    ) -> PDFNativeImageArtifact:
        opts = options or PDFImageExtractionOptions()
        provider = self._registry.resolve(preferred_provider=opts.preferred_provider)
        async with await provider.open(source) as document:
            structure = await self._structure_mapper.map_document(document)
            return await self.extract_document(
                document,
                options=opts,
                source_structure_artifact=structure,
            )

    async def extract_document(
        self,
        document: PDFDocumentHandle,
        options: PDFImageExtractionOptions | None = None,
        *,
        source_structure_artifact: PDFInternalStructureArtifact | None = None,
    ) -> PDFNativeImageArtifact:
        opts = options or PDFImageExtractionOptions()
        structure = source_structure_artifact
        if structure is None:
            structure = await self._structure_mapper.map_document(
                document,
                PDFInternalMappingOptions(),
            )
        provider_method = getattr(document, "get_native_images", None)
        if callable(provider_method):
            return await provider_method(opts, structure)
        resources = tuple(
            PDFImageResource.from_descriptor(descriptor)
            for descriptor in (
                structure.resource_catalog.images + structure.resource_catalog.masks
            )
        )
        warning = EixoWarning(
            code="pdf.images.occurrences_unavailable",
            message=(
                "The selected provider does not expose native image occurrences; "
                "only resource descriptors were converted."
            ),
        )
        catalog = PDFImageCatalog(
            resources=resources,
            unresolved_resources=tuple(
                resource.resource_reference
                for resource in resources
                if resource.resource_reference
            ),
            capability_matrix=_fallback_capability_matrix(),
            warnings=(warning,),
            limitations=(
                ProviderLimitation(
                    code="image_occurrence_mapping_unavailable",
                    message="Native image occurrence mapping is not available.",
                    scope="image",
                ),
            ),
            provenance=structure.provenance,
        )
        return PDFNativeImageArtifact(
            artifact_version=ContractVersion("1.0.0"),
            provider=structure.provider,
            document_id=structure.document_id,
            source_structure_artifact=structure,
            image_catalog=catalog,
            pages=tuple(
                PDFPageImageLayer(page_reference=page.page_reference)
                for page in structure.pages
            ),
            statistics=PDFNativeImageStatistics(
                image_resource_count=len(resources),
                image_mask_count=sum(1 for resource in resources if resource.image_mask),
                soft_mask_count=sum(1 for resource in resources if resource.soft_mask_reference),
                unresolved_resource_count=len(resources),
            ),
            warnings=(warning,),
            limitations=structure.limitations + catalog.limitations,
            provenance=structure.provenance,
        )


def _fallback_capability_matrix() -> tuple[PDFImageCapabilityMatrixEntry, ...]:
    return (
        PDFImageCapabilityMatrixEntry(
            information="Image XObject",
            support=PDFImageSupportStatus.PROVIDER_DERIVED,
            origin="PDFResourceCatalog",
            precision="resource_descriptor",
        ),
        PDFImageCapabilityMatrixEntry(
            information="occurrence geometry",
            support=PDFImageSupportStatus.UNSUPPORTED,
            origin="generic_mapper",
            limitation="Requires provider image occurrence support.",
        ),
        PDFImageCapabilityMatrixEntry(
            information="encoded bytes",
            support=PDFImageSupportStatus.UNKNOWN,
            origin="generic_mapper",
            limitation="Binary extraction is provider-specific.",
        ),
    )


__all__ = ["DefaultPDFNativeImageExtractor"]
