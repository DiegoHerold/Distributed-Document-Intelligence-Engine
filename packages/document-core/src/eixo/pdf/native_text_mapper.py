from __future__ import annotations

from eixo.core import DocumentSource, EixoWarning
from eixo.core.versions import ContractVersion
from eixo.pdf.contracts import PDFDocumentHandle
from eixo.pdf.models import ProviderLimitation
from eixo.pdf.native_text import (
    PDFNativeTextArtifact,
    PDFNativeTextExtractionOptions,
    PDFNativeTextLayer,
    PDFNativeTextStatistics,
)
from eixo.pdf.registry import PDFProviderRegistry
from eixo.pdf.structure import PDFInternalMappingOptions, PDFInternalStructureArtifact
from eixo.pdf.structure_mapper import DefaultPDFInternalStructureMapper
from eixo.pdf.typography import PDFTypographyArtifact, PDFTypographyOptions
from eixo.pdf.typography_mapper import DefaultPDFTypographyResolver


class DefaultPDFNativeTextExtractor:
    def __init__(
        self,
        registry: PDFProviderRegistry,
        *,
        structure_mapper: DefaultPDFInternalStructureMapper | None = None,
        typography_resolver: DefaultPDFTypographyResolver | None = None,
    ) -> None:
        self._registry = registry
        self._structure_mapper = structure_mapper or DefaultPDFInternalStructureMapper(registry)
        self._typography_resolver = typography_resolver or DefaultPDFTypographyResolver(
            registry,
            structure_mapper=self._structure_mapper,
        )

    async def extract(
        self,
        source: DocumentSource,
        options: PDFNativeTextExtractionOptions | None = None,
    ) -> PDFNativeTextArtifact:
        opts = options or PDFNativeTextExtractionOptions()
        provider = self._registry.resolve(preferred_provider=opts.preferred_provider)
        async with await provider.open(source) as document:
            structure = await self._structure_mapper.map_document(document)
            typography = await self._typography_resolver.resolve_document(
                document,
                options=PDFTypographyOptions(
                    page_selection=opts.page_selection,
                    preferred_provider=opts.preferred_provider,
                ),
                source_structure_artifact=structure,
            )
            return await self.extract_document(
                document,
                options=opts,
                source_structure_artifact=structure,
                typography_artifact=typography,
            )

    async def extract_document(
        self,
        document: PDFDocumentHandle,
        options: PDFNativeTextExtractionOptions | None = None,
        *,
        source_structure_artifact: PDFInternalStructureArtifact | None = None,
        typography_artifact: PDFTypographyArtifact | None = None,
    ) -> PDFNativeTextArtifact:
        opts = options or PDFNativeTextExtractionOptions()
        structure = source_structure_artifact
        if structure is None:
            structure = await self._structure_mapper.map_document(
                document,
                PDFInternalMappingOptions(),
            )
        typography = typography_artifact
        if typography is None:
            typography = await self._typography_resolver.resolve_document(
                document,
                source_structure_artifact=structure,
            )
        provider_method = getattr(document, "get_native_text", None)
        if callable(provider_method):
            return await provider_method(opts, typography, structure)
        warning = EixoWarning(
            code="pdf.native_text.unsupported_by_provider",
            message="The selected provider does not expose native text extraction.",
        )
        return PDFNativeTextArtifact(
            artifact_version=ContractVersion("1.0.0"),
            provider=structure.provider,
            document_id=structure.document_id,
            source_structure_artifact=structure,
            typography_artifact=typography,
            pages=(),
            text_layer=PDFNativeTextLayer(
                font_references=typography.font_catalog.fonts,
                text_styles=typography.font_catalog.text_styles,
                warnings=(warning,),
                provenance=structure.provenance,
            ),
            warnings=(warning,),
            limitations=structure.limitations
            + (
                ProviderLimitation(
                    code="native_text_extraction_unavailable",
                    message="Native text extraction is not implemented for this provider.",
                    scope="text",
                ),
            ),
            statistics=PDFNativeTextStatistics(),
            provenance=structure.provenance,
        )


__all__ = ["DefaultPDFNativeTextExtractor"]
