from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from eixo import (
    DocumentSource,
    PDFBasicInfo,
    PDFEncryptionState,
    PDFPageGeometry,
    PDFParseProfile,
    PDFParseOptions,
    PDFProbeOptions,
    PDFProbeResult,
    PDFProbeStatus,
    PDFProviderCapabilities,
    PDFProviderDescriptor,
    PDFProviderProvenance,
    PDFProviderRegistry,
    PDFSupportLevel,
)
from eixo.core import (
    ContentHash,
    ContractVersion,
    DocumentId,
    ProviderId,
    ProviderVersion,
    ResultStatus,
)
from eixo.artifacts import LocalArtifactStore
from eixo.engine import DocumentEngine
from eixo.engine.pdf_public import parse_pdf_public


@dataclass(slots=True)
class FakePDFProvider:
    descriptor: PDFProviderDescriptor

    @property
    def capabilities(self) -> PDFProviderCapabilities:
        return self.descriptor.capabilities

    async def probe(
        self,
        source: DocumentSource,
        options: PDFProbeOptions | None = None,
    ) -> PDFProbeResult:
        return PDFProbeResult(
            supported=True,
            status=PDFProbeStatus.VALID,
            confidence=1.0,
            detected_media_type="application/pdf",
            detected_version="1.7",
            encryption_state=PDFEncryptionState.NOT_ENCRYPTED,
            requires_password=False,
            provider_id=self.descriptor.provider_id,
            provider_version=self.descriptor.provider_version,
            backend_name=self.descriptor.backend_name,
            backend_version=self.descriptor.backend_version,
        )

    async def open(self, source: DocumentSource, options=None) -> "FakePDFDocument":
        return FakePDFDocument(source=source, descriptor=self.descriptor)


@dataclass(slots=True)
class FakePDFDocument:
    source: DocumentSource
    descriptor: PDFProviderDescriptor
    closed: bool = False

    @property
    def provider_id(self) -> str:
        return str(self.descriptor.provider_id)

    async def __aenter__(self) -> "FakePDFDocument":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    async def close(self) -> None:
        self.closed = True

    async def get_basic_info(self) -> PDFBasicInfo:
        return PDFBasicInfo(
            page_count=1,
            declared_version="1.7",
            interpreted_version="1.7",
            encryption_state=PDFEncryptionState.NOT_ENCRYPTED,
            requires_password=False,
            metadata={"producer": "fake"},
            size_bytes=self.source.size,
            provider_id=self.descriptor.provider_id,
            provider_version=self.descriptor.provider_version,
            backend_name=self.descriptor.backend_name,
            backend_version=self.descriptor.backend_version,
            provenance=PDFProviderProvenance(
                provider_id=self.descriptor.provider_id,
                provider_version=self.descriptor.provider_version,
                backend_name=self.descriptor.backend_name,
                backend_version=self.descriptor.backend_version,
                operation="get_basic_info",
            ),
        )

    async def get_page_count(self) -> int:
        return 1

    async def get_page(self, index: int) -> "FakePDFPage":
        return FakePDFPage(index=index, descriptor=self.descriptor)


@dataclass(slots=True)
class FakePDFPage:
    index: int
    descriptor: PDFProviderDescriptor

    @property
    def page_number(self) -> int:
        return self.index + 1

    @property
    def stable_id(self) -> str:
        return f"pdf-page-{self.index}"

    async def get_basic_geometry(self) -> PDFPageGeometry:
        return PDFPageGeometry(
            page_index=self.index,
            page_number=self.page_number,
            width=612,
            height=792,
            rotation=0,
        )


def test_document_engine_local_registers_public_pdf_capabilities() -> None:
    engine = DocumentEngine.local()

    descriptors = engine.registry.list_capabilities()
    contracts = {(item.input_contract, item.output_contract) for item in descriptors}

    assert ("InspectionRequest", "InspectionResult") in contracts
    assert ("ParseRequest", "ParseResult") in contracts
    assert ("ProcessingRequest", "ProcessingResult") in contracts


def test_basic_pdf_parse_returns_summary_and_artifact_references(tmp_path: Path) -> None:
    async def run() -> None:
        registry = PDFProviderRegistry()
        registry.register(FakePDFProvider(descriptor=fake_descriptor()))
        document_id = DocumentId.new()
        source = DocumentSource.from_bytes(
            b"%PDF-1.7\n",
            filename="basic.pdf",
            declared_media_type="application/pdf",
            metadata={
                "document_id": str(document_id),
                "content_hash": ContentHash("sha256", "abc").digest,
            },
        )
        result = await parse_pdf_public(
            source,
            options=PDFParseOptions(
                profile=PDFParseProfile.BASIC,
            ),
            artifact_store=LocalArtifactStore(tmp_path),
            pdf_provider_registry=registry,
        )

        assert result.status is ResultStatus.SUCCESS
        assert result.format == "pdf"
        assert result.profile == "basic"
        assert result.page_count == 1
        assert result.artifact_reference is not None
        assert len(result.artifacts) == 2
        assert all(reference.storage_key for reference in result.artifacts)

    asyncio.run(run())


def fake_descriptor() -> PDFProviderDescriptor:
    return PDFProviderDescriptor(
        provider_id=ProviderId("prov_fake_pdf_public"),
        name="Fake PDF Provider",
        provider_version=ProviderVersion("1.0.0"),
        backend_name="fake",
        backend_version="1.0.0",
        capabilities=PDFProviderCapabilities(
            supports_basic_info=PDFSupportLevel.SUPPORTED,
            supports_page_geometry=PDFSupportLevel.SUPPORTED,
        ),
        metadata={"contract": str(ContractVersion("1.0.0"))},
    )
