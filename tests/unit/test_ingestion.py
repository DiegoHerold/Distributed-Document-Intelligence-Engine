from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from eixo.application.ingestion import (
    ContentIdentityService,
    LocalSourceResolver,
    MagicBytesDocumentFormatDetector,
)
from eixo.core import (
    BytesSource,
    DetectionConfidence,
    DocumentFormat,
    DocumentSource,
    SourceNotFileError,
    SourceNotFoundError,
    SourceOwnership,
    StreamSource,
)


@pytest.mark.anyio
async def test_path_bytes_and_stream_sources_share_content_identity(tmp_path: Path) -> None:
    content = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"
    path = tmp_path / "document.bin"
    path.write_bytes(content)
    resolver = LocalSourceResolver()
    identifier = ContentIdentityService()
    identities = []

    sources = (
        DocumentSource.from_path(
            path,
            declared_media_type="application/octet-stream",
        ),
        DocumentSource.from_bytes(
            content,
            filename="document.pdf",
            declared_mime="application/pdf",
        ),
        DocumentSource.from_stream(
            io.BytesIO(content),
            filename="document.pdf",
            declared_mime="application/pdf",
        ),
    )
    for source in sources:
        async with resolver.resolve(source) as resolved:
            identities.append(await identifier.identify(resolved))

    hashes = {item.identity.content_hash.canonical_value for item in identities}
    assert len(hashes) == 1
    assert identities[0].identity.detected_format.format == DocumentFormat.PDF
    assert identities[0].identity.detected_format.warnings[0].code == "format.mime_mismatch"


@pytest.mark.anyio
async def test_stream_source_preserves_external_position_and_ownership() -> None:
    stream = io.BytesIO(b"prefix%PDF-1.7\n")
    stream.seek(6)
    source = StreamSource(
        stream=stream,
        filename="document.pdf",
        declared_media_type="application/pdf",
    )

    assert "stream" not in source.to_dict()

    async with LocalSourceResolver().resolve(source) as resolved:
        assert resolved.ownership == SourceOwnership.CALLER
        assert stream.tell() == 0

    assert stream.tell() == 6
    assert not stream.closed


@pytest.mark.anyio
async def test_source_resolver_reports_missing_and_directory_sources(tmp_path: Path) -> None:
    resolver = LocalSourceResolver()

    with pytest.raises(SourceNotFoundError):
        async with resolver.resolve(DocumentSource.from_path(tmp_path / "missing.pdf")):
            pass

    with pytest.raises(SourceNotFileError):
        async with resolver.resolve(DocumentSource.from_path(tmp_path)):
            pass


@pytest.mark.anyio
async def test_detector_distinguishes_xlsx_from_generic_zip() -> None:
    detector = MagicBytesDocumentFormatDetector()
    resolver = LocalSourceResolver()

    generic_source = DocumentSource.from_bytes(generic_zip(), filename="a.zip")
    xlsx_source = DocumentSource.from_bytes(xlsx_zip(), filename="a.xlsx")

    async with resolver.resolve(generic_source) as source:
        generic = await detector.detect(source)
    async with resolver.resolve(xlsx_source) as source:
        xlsx = await detector.detect(source)

    assert generic.format == DocumentFormat.UNKNOWN
    assert xlsx.format == DocumentFormat.XLSX
    assert xlsx.confidence == DetectionConfidence.HIGH


@pytest.mark.anyio
async def test_csv_detection_is_conservative() -> None:
    detector = MagicBytesDocumentFormatDetector()
    resolver = LocalSourceResolver()

    plain = BytesSource(content=b"abc", filename="a.txt", size=3)
    csv = DocumentSource.from_bytes(b"a;b\n1;2\n", filename="a.csv", declared_mime="text/csv")

    async with resolver.resolve(plain) as source:
        plain_detected = await detector.detect(source)
    async with resolver.resolve(csv) as source:
        csv_detected = await detector.detect(source)

    assert plain_detected.format == DocumentFormat.UNKNOWN
    assert csv_detected.format == DocumentFormat.CSV
    assert csv_detected.confidence == DetectionConfidence.MEDIUM


def generic_zip() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("readme.txt", "not an xlsx")
    return output.getvalue()


def xlsx_zip() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("xl/workbook.xml", "<workbook />")
    return output.getvalue()
