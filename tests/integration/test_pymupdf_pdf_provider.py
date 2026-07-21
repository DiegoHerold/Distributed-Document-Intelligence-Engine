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
    PDFInspectionOptions,
    PDFInspectionState,
    PDFInternalMappingOptions,
    PDFMappingStatus,
    PDFNativeTextExtractionOptions,
    PDFNativeTextVisibility,
    PDFOpenOptions,
    PDFPasswordRequiredError,
    PDFProbeOptions,
    PDFProbeStatus,
    PDFProviderSettings,
    PDFProviderUnavailableError,
    PDFResourceLimitExceededError,
    PDFResourceType,
    PDFSecurityStatus,
    PDFTechnicalProfile,
    PDFTypographyOptions,
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
            assert geometry.canonical_geometry is not None
            assert geometry.canonical_geometry.width == 612
            assert geometry.canonical_geometry.height == 792

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


def test_pymupdf_provider_applies_canonical_page_geometry_with_rotation() -> None:
    async def run() -> None:
        provider = PyMuPDFPDFProvider(_backend=FakePyMuPDFBackend())
        source = DocumentSource.from_bytes(
            b"%PDF-1.7\nROTATE=90\nUSERUNIT=2\n",
            filename="rotated.pdf",
        )

        async with await provider.open(source) as document:
            page = await document.get_page(0)
            geometry = await page.get_basic_geometry()

        assert geometry.width == 1584.0
        assert geometry.height == 1224.0
        assert geometry.rotation == 90
        assert geometry.canonical_geometry is not None
        assert geometry.canonical_geometry.user_unit == 2.0

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


def test_document_engine_runs_pdf_technical_inspection_with_fake_backend() -> None:
    async def run() -> None:
        provider = PyMuPDFPDFProvider(_backend=FakePyMuPDFBackend())
        engine = DocumentEngine.local(
            pdf_providers=(provider,),
            pdf=PDFProviderSettings(default_provider=PYMUPDF_PROVIDER_ID),
        )

        try:
            result = await engine.inspect_pdf(
                DocumentSource.from_bytes(PDF_BYTES, filename="technical.pdf"),
                options=PDFInspectionOptions(),
            )
        finally:
            await engine.shutdown()

        assert result.security.status == PDFSecurityStatus.NOT_ENCRYPTED
        assert result.page_summary.total_pages == 1
        assert result.page_inspections[0].canonical_geometry is not None
        assert result.page_inspections[0].canonical_geometry.page_box.width == 612
        assert result.feature_inventory.native_text.status == PDFInspectionState.PRESENT
        assert result.feature_inventory.images.status == PDFInspectionState.PRESENT
        assert result.feature_inventory.vectors.status == PDFInspectionState.PRESENT
        assert result.resource_summary.images.approximate_count == 1
        assert result.technical_profile is not None
        assert result.technical_profile.profile == PDFTechnicalProfile.INTERACTIVE

    asyncio.run(run())


def test_pymupdf_provider_maps_internal_structure_with_fake_backend() -> None:
    async def run() -> None:
        provider = PyMuPDFPDFProvider(_backend=FakePyMuPDFBackend())
        source = DocumentSource.from_bytes(PDF_BYTES, filename="structure.pdf")

        async with await provider.open(source) as document:
            artifact = await document.get_internal_structure(
                PDFInternalMappingOptions(max_objects=20)
            )

        assert artifact.object_graph.object_by_id("pdfobj:8:0") is not None
        assert artifact.pages[0].content_streams[0].stream_reference.stream_id == (
            "pdfstream:10:0"
        )
        assert artifact.pages[0].content_streams[0].operations_available == (
            PDFMappingStatus.UNSUPPORTED_BY_PROVIDER
        )
        assert len(artifact.resource_catalog.fonts) == 1
        assert artifact.resource_catalog.fonts[0].base_font == "ABCDEE+Arial-BoldMT"
        assert len(artifact.resource_catalog.images) == 1
        assert artifact.resource_catalog.images[0].width == 64
        assert len(artifact.resource_catalog.masks) == 1
        assert len(artifact.resource_catalog.xobjects) == 1
        assert artifact.resource_catalog.xobjects[0].reference.resource_type == (
            PDFResourceType.FORM_XOBJECT
        )
        assert artifact.object_graph.relations_from("pdfstream:10:0")
        assert artifact.capability_matrix
        assert "FakeDocument" not in str(artifact.to_dict())

    asyncio.run(run())


def test_document_engine_maps_pdf_internal_structure_with_fake_backend() -> None:
    async def run() -> None:
        provider = PyMuPDFPDFProvider(_backend=FakePyMuPDFBackend())
        engine = DocumentEngine.local(
            pdf_providers=(provider,),
            pdf=PDFProviderSettings(default_provider=PYMUPDF_PROVIDER_ID),
        )

        try:
            artifact = await engine.map_pdf_internal_structure(
                DocumentSource.from_bytes(PDF_BYTES, filename="engine-structure.pdf")
            )
        finally:
            await engine.shutdown()

        assert artifact.resource_catalog.get("pdffont:pdfobj:8:0") is not None
        assert artifact.pages[0].page_reference.page_number == 1

    asyncio.run(run())


def test_pymupdf_provider_resolves_typography_with_fake_backend() -> None:
    async def run() -> None:
        provider = PyMuPDFPDFProvider(_backend=FakePyMuPDFBackend())
        source = DocumentSource.from_bytes(PDF_BYTES, filename="typography.pdf")

        async with await provider.open(source) as document:
            structure = await document.get_internal_structure()
            typography = await document.get_typography(
                PDFTypographyOptions(),
                structure,
            )

        font = typography.font_catalog.fonts[0]
        assert font.font_id == "pdffont:pdfobj:8:0"
        assert font.subset is True
        assert font.subset_prefix == "ABCDEE"
        assert font.normalized_family == "Arial"
        assert font.encoding is not None
        assert font.encoding.name == "WinAnsiEncoding"
        assert typography.font_catalog.capability_matrix
        assert "FakeDocument" not in str(typography.to_dict())

    asyncio.run(run())


def test_pymupdf_provider_extracts_native_text_with_fake_backend() -> None:
    async def run() -> None:
        provider = PyMuPDFPDFProvider(_backend=FakePyMuPDFBackend())
        source = DocumentSource.from_bytes(PDF_BYTES, filename="native-text.pdf")

        async with await provider.open(source) as document:
            native = await document.get_native_text(PDFNativeTextExtractionOptions())

        assert native.statistics.glyph_count == 6
        assert native.statistics.character_count == 5
        assert native.statistics.word_count == 3
        assert native.statistics.unresolved_unicode_count == 1
        assert native.statistics.invisible_text_count == 1
        page = native.pages[0]
        assert page.blocks[0].line_ids
        assert page.lines[0].span_ids
        assert page.spans[0].glyph_ids
        assert page.words[1].normalized_text == "fi"
        assert page.glyphs[-1].unicode_text is None
        assert page.glyphs[-2].visibility == PDFNativeTextVisibility.INVISIBLE_RENDER_MODE
        assert page.relations
        assert native.text_layer is not None
        assert native.text_layer.text_styles
        assert "FakePage" not in str(native.to_dict())

    asyncio.run(run())


def test_document_engine_extracts_pdf_native_text_with_fake_backend() -> None:
    async def run() -> None:
        provider = PyMuPDFPDFProvider(_backend=FakePyMuPDFBackend())
        engine = DocumentEngine.local(
            pdf_providers=(provider,),
            pdf=PDFProviderSettings(default_provider=PYMUPDF_PROVIDER_ID),
        )

        try:
            typography = await engine.resolve_pdf_typography(
                DocumentSource.from_bytes(PDF_BYTES, filename="engine-typography.pdf")
            )
            native = await engine.extract_pdf_native_text(
                DocumentSource.from_bytes(PDF_BYTES, filename="engine-native-text.pdf")
            )
        finally:
            await engine.shutdown()

        assert typography.font_catalog.fonts[0].normalized_family == "Arial"
        assert native.statistics.line_count == 1
        assert native.statistics.block_count == 1

    asyncio.run(run())


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
    user_unit: float = 1.0

    def get_text(self, mode: str):
        if mode == "text":
            return "hello pdf"
        if mode == "rawdict":
            return {
                "blocks": [
                    {
                        "type": 0,
                        "bbox": (10.0, 20.0, 80.0, 42.0),
                        "lines": [
                            {
                                "bbox": (10.0, 20.0, 80.0, 42.0),
                                "dir": (1.0, 0.0),
                                "spans": [
                                    {
                                        "text": "Hi fi",
                                        "font": "Arial-BoldMT",
                                        "size": 12.0,
                                        "color": 0,
                                        "bbox": (10.0, 20.0, 48.0, 32.0),
                                        "origin": (10.0, 30.0),
                                        "chars": [
                                            {
                                                "c": "H",
                                                "bbox": (10.0, 20.0, 18.0, 32.0),
                                                "origin": (10.0, 30.0),
                                            },
                                            {
                                                "c": "i",
                                                "bbox": (18.0, 20.0, 22.0, 32.0),
                                                "origin": (18.0, 30.0),
                                            },
                                            {
                                                "c": " ",
                                                "bbox": (22.0, 20.0, 26.0, 32.0),
                                                "origin": (22.0, 30.0),
                                            },
                                            {
                                                "c": "\ufb01",
                                                "bbox": (26.0, 20.0, 36.0, 32.0),
                                                "origin": (26.0, 30.0),
                                            },
                                        ],
                                    },
                                    {
                                        "text": "x",
                                        "font": "Arial-BoldMT",
                                        "size": 12.0,
                                        "color": 0,
                                        "render_mode": 3,
                                        "bbox": (50.0, 20.0, 58.0, 32.0),
                                        "chars": [
                                            {
                                                "c": "x",
                                                "bbox": (50.0, 20.0, 58.0, 32.0),
                                                "origin": (50.0, 30.0),
                                            }
                                        ],
                                    },
                                    {
                                        "font": "Arial-BoldMT",
                                        "size": 12.0,
                                        "color": 0,
                                        "bbox": (60.0, 20.0, 68.0, 32.0),
                                        "chars": [
                                            {
                                                "c": "",
                                                "bbox": (60.0, 20.0, 68.0, 32.0),
                                                "origin": (60.0, 30.0),
                                            }
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }
        raise AssertionError(mode)

    def get_images(self, *, full: bool) -> list[tuple[str]]:
        assert full is True
        return [(9, 12, 64, 32, 8, "DeviceRGB", "", "Im0", "DCTDecode", 0)]

    def get_fonts(self, *, full: bool) -> list[tuple[object, ...]]:
        assert full is True
        return [(8, "n/a", "Type1", "ABCDEE+Arial-BoldMT", "F1", "WinAnsiEncoding")]

    def get_xobjects(self) -> list[tuple[object, ...]]:
        return [(11, "Fm0", "Form", 0, 0, 100, 100)]

    def get_contents(self) -> list[int]:
        return [10]

    def get_unknown_resources(self) -> list[tuple[str, str]]:
        return [("ProcSet", "PDF/Text")]

    def get_drawings(self) -> list[dict[str, str]]:
        return [{"type": "path"}]

    def get_links(self) -> list[dict[str, str]]:
        return [{"uri": "https://example.test"}]

    def annots(self) -> list[str]:
        return []

    def widgets(self) -> list[str]:
        return []


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
        self.page_rotation = 90 if b"ROTATE=90" in content else 0
        self.user_unit = 2.0 if b"USERUNIT=2" in content else 1.0

    def authenticate(self, password: str) -> int:
        return 1 if password == "secret" else 0

    def load_page(self, index: int) -> FakePage:
        if self.closed:
            raise RuntimeError("closed")
        if index < 0 or index >= self.page_count:
            raise IndexError(index)
        return FakePage(rotation=self.page_rotation, user_unit=self.user_unit)

    def close(self) -> None:
        self.closed = True

    def xref_length(self) -> int:
        return 13

    def xref_object(self, xref: int, compressed: bool = False) -> str:
        values = {
            1: "<< /Type /Catalog /Pages 2 0 R >>",
            2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: "<< /Type /Page /Resources << /Font << /F1 8 0 R >> >> >>",
            8: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            9: "<< /Type /XObject /Subtype /Image /Width 64 /Height 32 >>",
            10: "<< /Length 24 /Filter /FlateDecode >> stream",
            11: "<< /Type /XObject /Subtype /Form /BBox [0 0 100 100] >> stream",
            12: "<< /Type /XObject /Subtype /Image /ImageMask true >>",
        }
        return values.get(xref, "<< >>")

    def xref_is_stream(self, xref: int) -> bool:
        return xref in {10, 11}

    def xref_get_key(self, xref: int, key: str) -> tuple[str, str]:
        if xref == 10 and key in {"Length", "/Length"}:
            return ("int", "24")
        if xref == 10 and key == "Filter":
            return ("name", "/FlateDecode")
        return ("null", "null")
