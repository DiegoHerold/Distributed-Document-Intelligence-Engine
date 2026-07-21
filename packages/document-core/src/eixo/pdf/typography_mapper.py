from __future__ import annotations

from eixo.core import DocumentSource, EixoWarning
from eixo.core.versions import ContractVersion
from eixo.pdf.contracts import PDFDocumentHandle
from eixo.pdf.models import ProviderLimitation
from eixo.pdf.registry import PDFProviderRegistry
from eixo.pdf.structure import PDFInternalMappingOptions, PDFInternalStructureArtifact
from eixo.pdf.structure_mapper import DefaultPDFInternalStructureMapper
from eixo.pdf.typography import (
    PDFFontCapabilityMatrixEntry,
    PDFFontCatalog,
    PDFFontResource,
    PDFTypographyArtifact,
    PDFTypographyOptions,
    PDFTypographySupportStatus,
)


class DefaultPDFTypographyResolver:
    def __init__(
        self,
        registry: PDFProviderRegistry,
        *,
        structure_mapper: DefaultPDFInternalStructureMapper | None = None,
    ) -> None:
        self._registry = registry
        self._structure_mapper = structure_mapper or DefaultPDFInternalStructureMapper(registry)

    async def resolve(
        self,
        source: DocumentSource,
        options: PDFTypographyOptions | None = None,
    ) -> PDFTypographyArtifact:
        opts = options or PDFTypographyOptions()
        provider = self._registry.resolve(preferred_provider=opts.preferred_provider)
        async with await provider.open(source) as document:
            structure = await self._structure_mapper.map_document(document)
            return await self.resolve_document(
                document,
                options=opts,
                source_structure_artifact=structure,
            )

    async def resolve_document(
        self,
        document: PDFDocumentHandle,
        options: PDFTypographyOptions | None = None,
        *,
        source_structure_artifact: PDFInternalStructureArtifact | None = None,
    ) -> PDFTypographyArtifact:
        opts = options or PDFTypographyOptions()
        provider_method = getattr(document, "get_typography", None)
        if callable(provider_method):
            return await provider_method(opts, source_structure_artifact)
        structure = source_structure_artifact
        if structure is None:
            structure = await self._structure_mapper.map_document(
                document,
                PDFInternalMappingOptions(),
            )
        fonts = tuple(
            PDFFontResource.from_descriptor(descriptor)
            for descriptor in structure.resource_catalog.fonts
        )
        encodings = tuple(font.encoding for font in fonts if font.encoding is not None)
        catalog = PDFFontCatalog(
            fonts=fonts,
            encodings=encodings,
            capability_matrix=_fallback_capability_matrix(),
            warnings=(
                EixoWarning(
                    code="pdf.typography.provider_specific_mapping_unavailable",
                    message=(
                        "Typography was derived from the internal resource catalog; "
                        "glyph programs, metrics and Unicode maps are not decoded."
                    ),
                ),
            ),
            provenance=structure.provenance,
        )
        return PDFTypographyArtifact(
            artifact_version=ContractVersion("1.0.0"),
            provider=structure.provider,
            document_id=structure.document_id,
            source_structure_artifact=structure,
            font_catalog=catalog,
            unresolved_resources=structure.resource_catalog.unknown_resources,
            warnings=catalog.warnings,
            limitations=structure.limitations
            + (
                ProviderLimitation(
                    code="font_program_extraction_unavailable",
                    message="Embedded font programs are not extracted in the generic mapper.",
                    scope="font",
                ),
                ProviderLimitation(
                    code="font_metric_decoding_unavailable",
                    message="Font metrics are limited to provider resource metadata.",
                    scope="font",
                ),
            ),
            provenance=structure.provenance,
        )


def _fallback_capability_matrix() -> tuple[PDFFontCapabilityMatrixEntry, ...]:
    return (
        PDFFontCapabilityMatrixEntry(
            information="internal_name",
            support=PDFTypographySupportStatus.PROVIDER_DERIVED,
            origin="PDFResourceCatalog",
            precision="provider_metadata",
        ),
        PDFFontCapabilityMatrixEntry(
            information="encoding",
            support=PDFTypographySupportStatus.PARTIALLY_SUPPORTED,
            origin="PDFResourceCatalog",
            precision="provider_tuple",
            limitation="Encoding dictionaries and differences are not decoded.",
        ),
        PDFFontCapabilityMatrixEntry(
            information="glyph_id",
            support=PDFTypographySupportStatus.UNSUPPORTED,
            origin="generic_mapper",
            limitation="Requires provider text or font program support.",
        ),
        PDFFontCapabilityMatrixEntry(
            information="embedded_program",
            support=PDFTypographySupportStatus.UNSUPPORTED,
            origin="generic_mapper",
            limitation="No font bytes are extracted or exposed.",
        ),
    )


__all__ = ["DefaultPDFTypographyResolver"]
