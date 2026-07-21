from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError

import pytest

from eixo import (
    DefaultPDFInternalStructureMapper,
    DocumentSource,
    PDFBasicInfo,
    PDFContentStream,
    PDFContentStreamReference,
    PDFFontResourceDescriptor,
    PDFDocumentHandle,
    PDFEncryptionState,
    PDFInternalMappingOptions,
    PDFInternalStructureArtifact,
    PDFMappingStatus,
    PDFObjectGraph,
    PDFObjectReference,
    PDFObjectRelation,
    PDFObjectRelationType,
    PDFPageReference,
    PDFProviderCapabilityMatrixEntry,
    PDFProviderDescriptor,
    PDFProviderSupportStatus,
    PDFProviderRegistry,
    PDFResourceCatalog,
    PDFResourceReference,
    PDFResourceScope,
    PDFResourceType,
    PDFSupportLevel,
    PDFProviderCapabilities,
    object_reference_id,
    resource_id,
)
from eixo.core import ContractVersion, ProviderId, ProviderVersion


def test_pdf_internal_mapping_options_serialize_safe_defaults() -> None:
    options = PDFInternalMappingOptions(max_objects=12, max_raw_summary_size=128)

    data = options.to_dict()

    assert data["include_indirect_objects"] is True
    assert data["max_objects"] == 12
    assert "password" not in str(data)
    with pytest.raises(ValueError):
        PDFInternalMappingOptions(max_object_depth=0)


def test_pdf_references_and_resource_ids_are_deterministic_and_scoped() -> None:
    obj = PDFObjectReference(object_number=42, generation_number=0, xref=42)
    page = PDFPageReference(page_index=0, page_number=1, object_reference=obj)
    font = PDFResourceReference(
        resource_id=resource_id(
            PDFResourceType.FONT,
            PDFResourceScope.PAGE,
            resource_name="F1",
            object_reference=obj,
            page_index=0,
        ),
        resource_type=PDFResourceType.FONT,
        scope=PDFResourceScope.PAGE,
        resource_name="F1",
        page_reference=page,
        object_reference=obj,
    )
    inherited_font = PDFResourceReference(
        resource_id=resource_id(
            PDFResourceType.FONT,
            PDFResourceScope.INHERITED,
            resource_name="F1",
            page_index=0,
        ),
        resource_type=PDFResourceType.FONT,
        scope=PDFResourceScope.INHERITED,
        resource_name="F1",
        page_reference=page,
    )

    assert obj.stable_id == "pdfobj:42:0"
    assert object_reference_id(42) == "pdfobj:42:0"
    assert font.resource_id == "pdffont:pdfobj:42:0"
    assert inherited_font.resource_id != font.resource_id
    with pytest.raises(FrozenInstanceError):
        obj.xref = 10  # type: ignore[misc]


def test_pdf_object_graph_catalog_and_artifact_are_serializable() -> None:
    descriptor = PDFProviderDescriptor(
        provider_id=ProviderId("prov_pdf_contract"),
        name="Contract PDF Provider",
        provider_version=ProviderVersion("0.1.0"),
        backend_name="ContractPDF",
        backend_version="0.1.0",
        capabilities=PDFProviderCapabilities(supports_basic_info=PDFSupportLevel.SUPPORTED),
    )
    page = PDFPageReference(page_index=0, page_number=1)
    resource = PDFResourceReference(
        resource_id="pdffont:pdfobj:8:0",
        resource_type=PDFResourceType.FONT,
        scope=PDFResourceScope.PAGE,
        resource_name="F1",
        page_reference=page,
        object_reference=PDFObjectReference(object_number=8, generation_number=0, xref=8),
    )
    stream_ref = PDFContentStreamReference(
        stream_id="pdfstream:10:0",
        page_reference=page,
        object_reference=PDFObjectReference(object_number=10, generation_number=0, xref=10),
    )
    catalog = PDFResourceCatalog(
        fonts=(
            PDFFontResourceDescriptor(
                reference=resource,
                status=PDFMappingStatus.RESOLVED,
                base_font="Helvetica",
                pages_using_resource=(page,),
            ),
        )
    )
    graph = PDFObjectGraph(
        relations=(
            PDFObjectRelation(
                source_id=stream_ref.stream_id,
                target_id=resource.resource_id,
                relation_type=PDFObjectRelationType.USES_RESOURCE,
            ),
        )
    )
    artifact = PDFInternalStructureArtifact(
        artifact_version=ContractVersion("1.0.0"),
        provider=descriptor,
        object_graph=graph,
        resource_catalog=catalog,
        pages=(),
        capability_matrix=(
            PDFProviderCapabilityMatrixEntry(
                feature="fonts",
                support=PDFProviderSupportStatus.PARTIAL,
                strategy="fixture",
            ),
        ),
    )

    assert catalog.get(resource.resource_id) is not None
    assert catalog.pages_using(resource.resource_id) == (page,)
    assert graph.relations_from(stream_ref.stream_id)[0].target_id == resource.resource_id
    data = artifact.to_dict()
    assert data["artifact_version"] == "1.0.0"
    assert data["resource_catalog"]["fonts"][0]["base_font"] == "Helvetica"
    assert "ContractPDF" in str(data)


def test_pdf_content_stream_rejects_negative_lengths() -> None:
    stream = PDFContentStreamReference(stream_id="pdfstream:inline:0")

    with pytest.raises(ValueError):
        PDFContentStream(stream_reference=stream, byte_length=-1)


def test_default_internal_structure_mapper_returns_explicit_fallback() -> None:
    async def run() -> None:
        registry = PDFProviderRegistry()
        registry.register(FallbackProvider())
        mapper = DefaultPDFInternalStructureMapper(registry)

        artifact = await mapper.map(
            DocumentSource.from_bytes(b"%PDF-1.7\n", filename="fallback.pdf")
        )

        assert artifact.pages[0].page_reference.page_number == 1
        assert artifact.object_graph.objects == ()
        assert artifact.resource_catalog.all_resources() == ()
        assert artifact.warnings[0].code == "pdf.structure.unsupported_by_provider"
        assert artifact.limitations[-1].code == "internal_structure_mapping_unavailable"

    asyncio.run(run())


class FallbackProvider:
    descriptor = PDFProviderDescriptor(
        provider_id=ProviderId("prov_pdf_fallback"),
        name="Fallback PDF Provider",
        provider_version=ProviderVersion("0.1.0"),
        backend_name="FallbackPDF",
        backend_version="0.1.0",
        capabilities=PDFProviderCapabilities(supports_basic_info=PDFSupportLevel.SUPPORTED),
    )

    @property
    def capabilities(self) -> PDFProviderCapabilities:
        return self.descriptor.capabilities

    async def probe(self, source, options=None):
        raise NotImplementedError

    async def open(self, source, options=None) -> PDFDocumentHandle:
        return FallbackDocument(source, self.descriptor)


class FallbackDocument:
    def __init__(self, source: DocumentSource, descriptor: PDFProviderDescriptor) -> None:
        self._source = source
        self.descriptor = descriptor
        self.closed = False

    @property
    def provider_id(self) -> str:
        return str(self.descriptor.provider_id)

    @property
    def source(self) -> DocumentSource:
        return self._source

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()

    async def get_basic_info(self) -> PDFBasicInfo:
        return PDFBasicInfo(
            page_count=1,
            declared_version="1.7",
            interpreted_version="1.7",
            encryption_state=PDFEncryptionState.NOT_ENCRYPTED,
            requires_password=False,
        )

    async def get_page_count(self) -> int:
        return 1

    async def get_page(self, index: int):
        raise NotImplementedError

    async def close(self) -> None:
        self.closed = True
