from __future__ import annotations

from eixo.core import DocumentSource, EixoWarning
from eixo.core.versions import ContractVersion
from eixo.pdf.contracts import PDFDocumentHandle
from eixo.pdf.interactive import (
    PDFInteractiveArtifact,
    PDFInteractiveCapabilityMatrixEntry,
    PDFInteractiveExtractionOptions,
    PDFInteractiveSupportStatus,
    PDFPageInteractiveLayer,
)
from eixo.pdf.models import ProviderLimitation
from eixo.pdf.registry import PDFProviderRegistry
from eixo.pdf.structure import PDFInternalMappingOptions, PDFInternalStructureArtifact
from eixo.pdf.structure_mapper import DefaultPDFInternalStructureMapper


class DefaultPDFInteractiveExtractor:
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
        options: PDFInteractiveExtractionOptions | None = None,
    ) -> PDFInteractiveArtifact:
        opts = options or PDFInteractiveExtractionOptions()
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
        options: PDFInteractiveExtractionOptions | None = None,
        *,
        source_structure_artifact: PDFInternalStructureArtifact | None = None,
    ) -> PDFInteractiveArtifact:
        opts = options or PDFInteractiveExtractionOptions()
        structure = source_structure_artifact
        if structure is None:
            structure = await self._structure_mapper.map_document(
                document,
                PDFInternalMappingOptions(),
            )
        provider_method = getattr(document, "get_native_interactive", None)
        if callable(provider_method):
            return await provider_method(opts, structure)
        warning = EixoWarning(
            code="pdf.interactive.unavailable",
            message="The selected provider does not expose PDF interactive elements.",
            scope="pdf.interactive",
        )
        limitation = ProviderLimitation(
            code="interactive_extraction_unavailable",
            message="Native PDF interactive extraction is not available for this provider.",
            scope="interactive",
        )
        return PDFInteractiveArtifact(
            artifact_version=ContractVersion("1.0.0"),
            provider=structure.provider,
            document_id=structure.document_id,
            source_structure_artifact=structure,
            page_layers=tuple(
                PDFPageInteractiveLayer(page_reference=page.page_reference)
                for page in structure.pages
            ),
            capability_matrix=_fallback_capability_matrix(),
            warnings=(warning,),
            limitations=structure.limitations + (limitation,),
            provenance=structure.provenance,
        )


def _fallback_capability_matrix() -> tuple[PDFInteractiveCapabilityMatrixEntry, ...]:
    return (
        PDFInteractiveCapabilityMatrixEntry(
            information="links",
            support=PDFInteractiveSupportStatus.UNSUPPORTED,
            origin="generic_mapper",
            limitation="Requires provider link support.",
        ),
        PDFInteractiveCapabilityMatrixEntry(
            information="annotations",
            support=PDFInteractiveSupportStatus.UNKNOWN,
            origin="generic_mapper",
            limitation="Annotation extraction is provider-specific.",
        ),
        PDFInteractiveCapabilityMatrixEntry(
            information="forms",
            support=PDFInteractiveSupportStatus.UNKNOWN,
            origin="generic_mapper",
            limitation="Form extraction is provider-specific.",
        ),
        PDFInteractiveCapabilityMatrixEntry(
            information="layers",
            support=PDFInteractiveSupportStatus.UNKNOWN,
            origin="generic_mapper",
            limitation="Optional content group extraction is provider-specific.",
        ),
    )


__all__ = ["DefaultPDFInteractiveExtractor"]
