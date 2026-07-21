from __future__ import annotations

from eixo.core import DocumentSource, EixoWarning
from eixo.core.versions import ContractVersion
from eixo.pdf.contracts import PDFDocumentHandle
from eixo.pdf.models import ProviderLimitation
from eixo.pdf.registry import PDFProviderRegistry
from eixo.pdf.structure import PDFInternalMappingOptions, PDFInternalStructureArtifact
from eixo.pdf.structure_mapper import DefaultPDFInternalStructureMapper
from eixo.pdf.vectors import (
    PDFNativeVectorArtifact,
    PDFNativeVectorOptions,
    PDFPageVectorLayer,
    PDFVectorCapabilityMatrixEntry,
    PDFVectorSupportStatus,
)


class DefaultPDFNativeVectorExtractor:
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
        options: PDFNativeVectorOptions | None = None,
    ) -> PDFNativeVectorArtifact:
        opts = options or PDFNativeVectorOptions()
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
        options: PDFNativeVectorOptions | None = None,
        *,
        source_structure_artifact: PDFInternalStructureArtifact | None = None,
    ) -> PDFNativeVectorArtifact:
        opts = options or PDFNativeVectorOptions()
        structure = source_structure_artifact
        if structure is None:
            structure = await self._structure_mapper.map_document(
                document,
                PDFInternalMappingOptions(),
            )
        provider_method = getattr(document, "get_native_vectors", None)
        if callable(provider_method):
            return await provider_method(opts, structure)
        warning = EixoWarning(
            code="pdf.vectors.unavailable",
            message="The selected provider does not expose native vector drawings.",
            scope="pdf.vector",
        )
        limitation = ProviderLimitation(
            code="vector_extraction_unavailable",
            message="Native vector extraction is not available for this provider.",
            scope="vector",
        )
        return PDFNativeVectorArtifact(
            artifact_version=ContractVersion("1.0.0"),
            provider=structure.provider,
            document_id=structure.document_id,
            source_structure_artifact=structure,
            page_layers=tuple(
                PDFPageVectorLayer(page_reference=page.page_reference)
                for page in structure.pages
            ),
            capability_matrix=_fallback_capability_matrix(),
            warnings=(warning,),
            limitations=structure.limitations + (limitation,),
            provenance=structure.provenance,
        )


def _fallback_capability_matrix() -> tuple[PDFVectorCapabilityMatrixEntry, ...]:
    return (
        PDFVectorCapabilityMatrixEntry(
            information="path drawings",
            support=PDFVectorSupportStatus.UNSUPPORTED,
            origin="generic_mapper",
            limitation="Requires provider native vector support.",
        ),
        PDFVectorCapabilityMatrixEntry(
            information="graphics state",
            support=PDFVectorSupportStatus.UNKNOWN,
            origin="generic_mapper",
            limitation="Graphics state resolution is provider-specific.",
        ),
        PDFVectorCapabilityMatrixEntry(
            information="clipping",
            support=PDFVectorSupportStatus.UNKNOWN,
            origin="generic_mapper",
            limitation="Clipping path extraction is provider-specific.",
        ),
    )


__all__ = ["DefaultPDFNativeVectorExtractor"]
