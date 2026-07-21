from __future__ import annotations

import asyncio
from dataclasses import dataclass

from eixo import (
    DefaultPDFTechnicalInspector,
    DocumentSource,
    PDFBasicInfo,
    PDFDocumentHandle,
    PDFEncryptionState,
    PDFInspectionOptions,
    PDFInspectionState,
    PDFOpenOptions,
    PDFPageGeometry,
    PDFPageHandle,
    PDFPageTechnicalHints,
    PDFProbeOptions,
    PDFProbeResult,
    PDFProbeStatus,
    PDFProviderCapabilities,
    PDFProviderDescriptor,
    PDFProviderRegistry,
    PDFSamplingStrategy,
    PDFSecurityStatus,
    PDFSupportLevel,
    PDFTechnicalInspector,
    PDFTechnicalProfile,
)
from eixo.core import ProviderId, ProviderVersion


def test_pdf_inspection_options_do_not_serialize_password() -> None:
    options = PDFInspectionOptions(password="secret")

    data = options.to_dict()

    assert "password" not in data
    assert data["password_provided"] is True
    assert "secret" not in str(data)


def test_pdf_technical_inspector_contract_returns_structured_inventory() -> None:
    async def run() -> None:
        provider = FakeInspectionProvider(page_count=3)
        registry = PDFProviderRegistry()
        registry.register(provider)
        inspector = DefaultPDFTechnicalInspector(registry)
        source = DocumentSource.from_bytes(b"%PDF-1.7\n", filename="contract.pdf")

        result = await inspector.inspect(
            source,
            PDFInspectionOptions(
                password="secret",
                inspect_all_pages=False,
                max_pages_to_inspect=1,
                sampling_strategy=PDFSamplingStrategy.FIRST,
            ),
        )

        assert isinstance(inspector, PDFTechnicalInspector)
        assert result.integrity.status.value == "valid"
        assert result.security.status == PDFSecurityStatus.NOT_ENCRYPTED
        assert result.security.authenticated == PDFInspectionState.NOT_APPLICABLE
        assert result.page_summary.total_pages == 3
        assert result.page_summary.inspected_pages == 1
        assert result.coverage is not None
        assert result.coverage.inspection_complete is False
        assert result.coverage.coverage_ratio == 1 / 3
        assert result.feature_inventory.native_text.status == PDFInspectionState.PRESENT
        assert result.feature_inventory.images.status == PDFInspectionState.ABSENT
        assert result.feature_inventory.vectors.status == PDFInspectionState.PRESENT
        assert result.technical_profile is not None
        assert result.technical_profile.profile == PDFTechnicalProfile.DIGITAL_TEXT
        assert result.metadata.fields["title"].normalized == "Contract Fixture"
        assert "secret" not in str(result.to_dict())

    asyncio.run(run())


def test_pdf_technical_inspector_returns_probe_only_for_encrypted_pdf() -> None:
    async def run() -> None:
        provider = FakeInspectionProvider(encrypted=True)
        registry = PDFProviderRegistry()
        registry.register(provider)
        inspector = DefaultPDFTechnicalInspector(registry)

        result = await inspector.inspect(
            DocumentSource.from_bytes(b"%PDF-1.7\nENCRYPTED\n", filename="locked.pdf")
        )

        assert provider.opened is False
        assert result.security.status == PDFSecurityStatus.ENCRYPTED_PASSWORD_REQUIRED
        assert result.page_summary.total_pages == 0
        assert result.coverage is not None
        assert result.coverage.features_inspected == PDFInspectionState.NOT_INSPECTED

    asyncio.run(run())


@dataclass(slots=True)
class FakeInspectionProvider:
    page_count: int = 1
    encrypted: bool = False
    opened: bool = False

    @property
    def descriptor(self) -> PDFProviderDescriptor:
        return PDFProviderDescriptor(
            provider_id=ProviderId("prov_pdf_inspection_fake"),
            name="Fake Inspection PDF Provider",
            provider_version=ProviderVersion("0.1.0"),
            backend_name="FakePDF",
            backend_version="0.1.0",
            capabilities=self.capabilities,
        )

    @property
    def capabilities(self) -> PDFProviderCapabilities:
        return PDFProviderCapabilities(
            supports_basic_info=PDFSupportLevel.SUPPORTED,
            supports_page_geometry=PDFSupportLevel.SUPPORTED,
            supports_incremental_page_access=PDFSupportLevel.SUPPORTED,
            supports_metadata_inspection=PDFSupportLevel.PARTIAL,
            supports_text_presence_inspection=PDFSupportLevel.PARTIAL,
            supports_vector_presence_inspection=PDFSupportLevel.PARTIAL,
        )

    async def probe(
        self,
        source: DocumentSource,
        options: PDFProbeOptions | None = None,
    ) -> PDFProbeResult:
        return PDFProbeResult(
            supported=True,
            status=PDFProbeStatus.ENCRYPTED if self.encrypted else PDFProbeStatus.VALID,
            confidence=1.0,
            detected_media_type="application/pdf",
            detected_version="1.7",
            encryption_state=PDFEncryptionState.PASSWORD_REQUIRED
            if self.encrypted
            else PDFEncryptionState.NOT_ENCRYPTED,
            requires_password=True if self.encrypted else False,
            provider_id=self.descriptor.provider_id,
            provider_version=self.descriptor.provider_version,
            backend_name=self.descriptor.backend_name,
            backend_version=self.descriptor.backend_version,
        )

    async def open(
        self,
        source: DocumentSource,
        options: PDFOpenOptions | None = None,
    ) -> PDFDocumentHandle:
        self.opened = True
        return FakeInspectionDocument(source, self.descriptor, self.page_count)


@dataclass(slots=True)
class FakeInspectionDocument:
    source: DocumentSource
    descriptor: PDFProviderDescriptor
    page_count: int
    closed: bool = False

    @property
    def provider_id(self) -> str:
        return str(self.descriptor.provider_id)

    async def __aenter__(self) -> PDFDocumentHandle:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.close()

    async def get_basic_info(self) -> PDFBasicInfo:
        return PDFBasicInfo(
            page_count=self.page_count,
            declared_version="1.7",
            interpreted_version="1.7",
            encryption_state=PDFEncryptionState.NOT_ENCRYPTED,
            requires_password=False,
            metadata={"title": "Contract Fixture"},
        )

    async def get_page_count(self) -> int:
        return self.page_count

    async def get_page(self, index: int) -> PDFPageHandle:
        return FakeInspectionPage(index)

    async def close(self) -> None:
        self.closed = True


@dataclass(slots=True)
class FakeInspectionPage:
    index: int

    @property
    def page_number(self) -> int:
        return self.index + 1

    @property
    def stable_id(self) -> str:
        return f"inspection-page-{self.index}"

    async def get_basic_geometry(self) -> PDFPageGeometry:
        return PDFPageGeometry(
            page_index=self.index,
            page_number=self.page_number,
            width=612,
            height=792,
            rotation=0,
        )

    async def get_technical_hints(self) -> PDFPageTechnicalHints:
        return PDFPageTechnicalHints(
            has_text=PDFInspectionState.PRESENT,
            has_images=PDFInspectionState.ABSENT,
            has_vectors=PDFInspectionState.PRESENT,
            has_links=PDFInspectionState.ABSENT,
            has_annotations=PDFInspectionState.ABSENT,
            has_forms=PDFInspectionState.ABSENT,
            approximate_text_count=120,
            approximate_image_count=0,
            approximate_vector_count=2,
        )
