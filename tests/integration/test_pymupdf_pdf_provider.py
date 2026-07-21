from __future__ import annotations

import asyncio
import importlib
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from eixo import (
    DocumentEngine,
    DocumentSource,
    CorruptedPDFError,
    InvalidPDFPasswordError,
    PDFOpenOptions,
    PDFPasswordRequiredError,
    PDFProbeOptions,
    PDFProbeStatus,
    PDFProviderSettings,
    PDFProviderUnavailableError,
    PDFResourceLimitExceededError,
)
from eixo.providers.pdf.pymupdf import PYMUPDF_PROVIDER_ID, PyMuPDFPDFProvider

PDF_BYTES = b"%PDF-1.7\n% fake\n"


def test_main_package_imports_without_pymupdf_backend() -> None:
    import eixo
    import eixo.pdf
    from eixo.providers.pdf.pymupdf import PyMuPDFPDFProvider as Provider

    assert eixo.DocumentEngine is DocumentEngine
    assert eixo.pdf.PDFOpenOptions is PDFOpenOptions
    assert Provider is PyMuPDFPDFProvider


def test_pymupdf_provider_missing_backend_returns_structured_error(monkeypatch) -> None:
    async def run() -> None:
        provider = PyMuPDFPDFProvider()
        source = DocumentSource.from_bytes(PDF_BYTES, filename="missing-backend.pdf")

        def fake_import(name: str):
            if name == "fitz":
                raise ModuleNotFoundError(name)
            return importlib.import_module(name)

        monkeypatch.setattr(importlib, "import_module", fake_import)

        with pytest.raises(PDFProviderUnavailableError) as exc_info:
            await provider.probe(source)

        assert exc_info.value.code == "pdf.provider_unavailable"

    asyncio.run(run())


def test_pymupdf_provider_probe_open_geometry_and_close_with_fake_backend() -> None:
    async def run() -> None:
        provider = PyMuPDFPDFProvider(_backend=FakePyMuPDFBackend())
        source = DocumentSource.from_bytes(PDF_BYTES, filename="valid.pdf")

        probe = await provider.probe(source, PDFProbeOptions(max_pages=2))
        assert probe.supported is True
        assert probe.status == PDFProbeStatus.VALID
        assert probe.detected_version == "1.7"
        assert probe.provenance is not None
        assert probe.provenance.provider_id == PYMUPDF_PROVIDER_ID

        async with await provider.open(source, PDFOpenOptions(max_pages=2)) as document:
            info = await document.get_basic_info()
            assert info.page_count == 1
            assert info.provider_id == PYMUPDF_PROVIDER_ID
            page = await document.get_page(0)
            geometry = await page.get_basic_geometry()
            assert geometry.width == 612
            assert geometry.height == 792
            assert geometry.media_box == (0.0, 0.0, 612.0, 792.0)

        assert document.closed is True

    asyncio.run(run())


def test_pymupdf_provider_accepts_local_path_without_reading_all_bytes(tmp_path: Path) -> None:
    async def run() -> None:
        provider = PyMuPDFPDFProvider(_backend=FakePyMuPDFBackend())
        path = tmp_path / "path.pdf"
        path.write_bytes(PDF_BYTES)

        async with await provider.open(DocumentSource.from_path(path)) as document:
            assert await document.get_page_count() == 1

    asyncio.run(run())


def test_pymupdf_provider_password_and_limits_with_fake_backend() -> None:
    async def run() -> None:
        provider = PyMuPDFPDFProvider(_backend=FakePyMuPDFBackend())
        encrypted = DocumentSource.from_bytes(
            b"%PDF-1.7\nENCRYPTED\n",
            filename="encrypted.pdf",
        )

        probe = await provider.probe(encrypted)
        assert probe.status == PDFProbeStatus.ENCRYPTED
        assert probe.requires_password is True

        with pytest.raises(PDFPasswordRequiredError):
            await provider.open(encrypted)
        with pytest.raises(InvalidPDFPasswordError):
            await provider.open(encrypted, PDFOpenOptions(password="wrong"))
        async with await provider.open(encrypted, PDFOpenOptions(password="secret")) as document:
            assert await document.get_page_count() == 1

        with pytest.raises(PDFResourceLimitExceededError):
            await provider.open(
                DocumentSource.from_bytes(PDF_BYTES, filename="limit.pdf"),
                PDFOpenOptions(max_file_size_bytes=4),
            )
        with pytest.raises(PDFResourceLimitExceededError):
            await provider.open(
                DocumentSource.from_bytes(b"%PDF-1.7\nPAGES=3\n", filename="pages.pdf"),
                PDFOpenOptions(max_pages=2),
            )

    asyncio.run(run())


def test_pymupdf_provider_invalid_pdf_does_not_leak_backend_exception() -> None:
    async def run() -> None:
        provider = PyMuPDFPDFProvider(_backend=FakePyMuPDFBackend())
        source = DocumentSource.from_bytes(b"not a pdf", filename="fake.pdf")

        probe = await provider.probe(source)
        assert probe.supported is False
        assert probe.status == PDFProbeStatus.NOT_PDF

        with pytest.raises(CorruptedPDFError) as exc_info:
            await provider.open(source)

        assert exc_info.value.code == "pdf.corrupted"
        assert isinstance(exc_info.value.cause, FakeFileDataError)

    asyncio.run(run())


def test_document_engine_resolves_registered_pdf_provider() -> None:
    provider = PyMuPDFPDFProvider(_backend=FakePyMuPDFBackend())
    engine = DocumentEngine.local(
        pdf_providers=(provider,),
        pdf=PDFProviderSettings(default_provider=PYMUPDF_PROVIDER_ID),
    )

    assert engine.pdf_provider is provider


@dataclass(slots=True)
class FakeRect:
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(slots=True)
class FakePage:
    rect: FakeRect = field(default_factory=lambda: FakeRect(0, 0, 612, 792))
    mediabox: FakeRect = field(default_factory=lambda: FakeRect(0, 0, 612, 792))
    cropbox: FakeRect = field(default_factory=lambda: FakeRect(0, 0, 612, 792))
    rotation: int = 0


class FakePyMuPDFBackend:
    VersionBind = "1.24.fake"

    def open(self, filename: str | None = None, **kwargs: object) -> "FakeDocument":
        stream = kwargs.get("stream")
        if filename is not None:
            content = Path(filename).read_bytes()
        elif isinstance(stream, bytes):
            content = stream
        else:
            content = b""
        if not content.startswith(b"%PDF-"):
            raise FakeFileDataError("not a PDF")
        return FakeDocument(content)


class FakeFileDataError(Exception):
    pass


class FakeDocument:
    metadata = {"format": "PDF 1.7", "title": "Fixture"}

    def __init__(self, content: bytes) -> None:
        self.content = content
        self.needs_pass = b"ENCRYPTED" in content
        self.closed = False
        self.page_count = 3 if b"PAGES=3" in content else 1

    def authenticate(self, password: str) -> int:
        return 1 if password == "secret" else 0

    def load_page(self, index: int) -> FakePage:
        if self.closed:
            raise RuntimeError("closed")
        if index < 0 or index >= self.page_count:
            raise IndexError(index)
        return FakePage()

    def close(self) -> None:
        self.closed = True
