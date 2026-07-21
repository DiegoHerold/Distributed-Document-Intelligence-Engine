from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from eixo import (
    ClosedPDFDocumentError,
    DocumentSource,
    PDFBasicInfo,
    PDFDocumentHandle,
    PDFOpenOptions,
    PDFPageGeometry,
    PDFPageHandle,
    PDFPageOutOfRangeError,
    PDFProbeOptions,
    PDFProbeResult,
    PDFProbeStatus,
    PDFProviderCapabilities,
    PDFProviderDescriptor,
    PDFProviderRegistry,
    PDFSupportLevel,
)
from eixo.core import ProviderId, ProviderVersion


def test_pdf_provider_registry_resolves_default_and_explicit_provider() -> None:
    provider = FakePDFProvider()
    registry = PDFProviderRegistry()
    registry.register(provider)

    assert registry.resolve() is provider
    assert registry.resolve(preferred_provider="prov_pdf_fake") is provider
    assert registry.resolve(
        required_capabilities=("supports_basic_info",)
    ) is provider


def test_pdf_provider_registry_rejects_missing_or_incompatible_provider() -> None:
    registry = PDFProviderRegistry()

    with pytest.raises(Exception) as exc_info:
        registry.resolve()

    assert getattr(exc_info.value, "code") == "pdf.provider_unavailable"

    registry.register(FakePDFProvider())

    with pytest.raises(Exception) as incompatible:
        registry.resolve(required_capabilities=("supports_rendering",))

    assert getattr(incompatible.value, "code") == "pdf.provider_unavailable"


def test_pdf_provider_contract_open_page_close_and_use_after_close() -> None:
    async def run() -> None:
        provider = FakePDFProvider()
        source = DocumentSource.from_bytes(b"%PDF-1.7\n", filename="one.pdf")

        probe = await provider.probe(source, PDFProbeOptions())
        assert probe.supported is True
        assert probe.status == PDFProbeStatus.VALID

        async with await provider.open(source, PDFOpenOptions()) as document:
            assert isinstance(document, PDFDocumentHandle)
            assert await document.get_page_count() == 1
            info = await document.get_basic_info()
            assert info.page_count == 1
            page = await document.get_page(0)
            assert isinstance(page, PDFPageHandle)
            assert page.index == 0
            assert page.page_number == 1
            geometry = await page.get_basic_geometry()
            assert geometry.width == 612
            assert geometry.height == 792
            with pytest.raises(PDFPageOutOfRangeError):
                await document.get_page(1)

        assert document.closed is True
        await document.close()
        with pytest.raises(ClosedPDFDocumentError):
            await document.get_page_count()

    asyncio.run(run())


@dataclass(slots=True)
class FakePDFProvider:
    descriptor: PDFProviderDescriptor = PDFProviderDescriptor(
        provider_id=ProviderId("prov_pdf_fake"),
        name="Fake PDF Provider",
        provider_version=ProviderVersion("0.1.0"),
        backend_name="FakePDF",
        backend_version="0.1.0",
        capabilities=PDFProviderCapabilities(
            supports_basic_info=PDFSupportLevel.SUPPORTED,
            supports_page_geometry=PDFSupportLevel.SUPPORTED,
            supports_incremental_page_access=PDFSupportLevel.SUPPORTED,
        ),
    )

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
            encryption_state=__import__("eixo").PDFEncryptionState.NOT_ENCRYPTED,
            requires_password=False,
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
        return FakePDFDocument(source)


@dataclass(slots=True)
class FakePDFDocument:
    source: DocumentSource
    closed: bool = False

    @property
    def provider_id(self) -> str:
        return "prov_pdf_fake"

    async def __aenter__(self) -> PDFDocumentHandle:
        self._ensure_open()
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.close()

    async def get_basic_info(self) -> PDFBasicInfo:
        self._ensure_open()
        return PDFBasicInfo(
            page_count=1,
            declared_version="1.7",
            interpreted_version="1.7",
            encryption_state=__import__("eixo").PDFEncryptionState.NOT_ENCRYPTED,
            requires_password=False,
        )

    async def get_page_count(self) -> int:
        self._ensure_open()
        return 1

    async def get_page(self, index: int) -> PDFPageHandle:
        self._ensure_open()
        if index != 0:
            raise PDFPageOutOfRangeError("PDF page index is out of range")
        return FakePDFPage(index)

    async def close(self) -> None:
        self.closed = True

    def _ensure_open(self) -> None:
        if self.closed:
            raise ClosedPDFDocumentError("PDF document handle is closed")


@dataclass(slots=True)
class FakePDFPage:
    index: int

    @property
    def page_number(self) -> int:
        return self.index + 1

    @property
    def stable_id(self) -> str:
        return f"fake-page-{self.index}"

    async def get_basic_geometry(self) -> PDFPageGeometry:
        return PDFPageGeometry(
            page_index=self.index,
            page_number=self.page_number,
            width=612,
            height=792,
            rotation=0,
        )
