from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import pytest

from eixo.application import FilenameSanitizer
from eixo.application.ingestion import LocalSourceResolver
from eixo.core import (
    ArchiveEntryTooLargeError,
    EmptyFileError,
    FileTooLargeError,
    IngestionLimits,
    IngestionSecurityPolicy,
    InvalidDocumentStructureError,
    MimeMismatchError,
    PageLimitExceededError,
    PathTraversalError,
    ProcessingRequest,
    ReadTimeoutError,
    UnsafeArchiveEntryError,
    UnsafeFilenameError,
    UnsupportedFormatError,
)
from eixo.engine import DocumentEngine


PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"


@pytest.mark.anyio
async def test_security_rejects_empty_and_too_large_sources(tmp_path: Path) -> None:
    policy = IngestionSecurityPolicy(
        limits=IngestionLimits(max_file_size_bytes=3),
    )

    with pytest.raises(FileTooLargeError):
        async with DocumentEngine.local(security=policy, data_directory=tmp_path) as engine:
            await engine.ingest(b"abcd")

    with pytest.raises(EmptyFileError):
        async with DocumentEngine.local(data_directory=tmp_path / "empty") as engine:
            await engine.ingest(b"")


@pytest.mark.anyio
async def test_security_limits_streams_without_declared_size() -> None:
    policy = IngestionSecurityPolicy(
        limits=IngestionLimits(max_file_size_bytes=3),
    )
    resolver = LocalSourceResolver(policy)
    source = ProcessingRequest(source=__import__("eixo").DocumentSource.from_stream(
        io.BytesIO(b"abcd"),
        filename="sample.pdf",
        declared_mime="application/pdf",
    )).source

    with pytest.raises(FileTooLargeError):
        async with resolver.resolve(source):
            pass


@pytest.mark.anyio
async def test_security_rejects_unknown_format_and_strict_mime(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedFormatError):
        async with DocumentEngine.local(data_directory=tmp_path / "unknown") as engine:
            await engine.ingest(b"not a supported document")

    policy = IngestionSecurityPolicy(require_mime_match=True)
    source = __import__("eixo").DocumentSource.from_bytes(
        PDF,
        filename="sample.pdf",
        declared_mime="text/csv",
    )

    with pytest.raises(MimeMismatchError):
        async with DocumentEngine.local(
            security=policy,
            data_directory=tmp_path / "mime",
        ) as engine:
            await engine.ingest(source)


@pytest.mark.anyio
async def test_security_accepts_extension_mismatch_with_warning(tmp_path: Path) -> None:
    source = __import__("eixo").DocumentSource.from_bytes(
        PDF,
        filename="sample.bin",
        declared_mime="application/pdf",
    )

    async with DocumentEngine.local(data_directory=tmp_path) as engine:
        result = await engine.ingest(source)

    assert result.detected_format.format.value == "pdf"
    assert any(warning.code == "extension_mismatch" for warning in result.warnings)


@pytest.mark.anyio
async def test_security_sanitizes_filename_metadata(tmp_path: Path) -> None:
    source = __import__("eixo").DocumentSource.from_bytes(
        PDF,
        filename="../../balancete.pdf",
        declared_mime="application/pdf",
    )

    async with DocumentEngine.local(data_directory=tmp_path) as engine:
        result = await engine.ingest(source)

    assert result.original_artifact.original_filename == "balancete.pdf"
    assert any(warning.code == "filename_sanitized" for warning in result.warnings)

    with pytest.raises(UnsafeFilenameError):
        FilenameSanitizer().sanitize("CON.pdf")


@pytest.mark.anyio
async def test_security_validates_xlsx_container_and_zip_limits(tmp_path: Path) -> None:
    small_policy = IngestionSecurityPolicy(
        limits=IngestionLimits(max_archive_entry_size_bytes=5),
    )

    with pytest.raises(ArchiveEntryTooLargeError):
        async with DocumentEngine.local(
            security=small_policy,
            data_directory=tmp_path / "large",
        ) as engine:
            await engine.ingest(xlsx_zip(workbook="123456"))

    with pytest.raises(UnsafeArchiveEntryError):
        async with DocumentEngine.local(data_directory=tmp_path / "unsafe") as engine:
            await engine.ingest(xlsx_zip(extra_entries={"../payload": "x"}))

    with pytest.raises(UnsupportedFormatError):
        async with DocumentEngine.local(data_directory=tmp_path / "bad") as engine:
            await engine.ingest(generic_zip())


@pytest.mark.anyio
async def test_security_applies_known_page_limit(tmp_path: Path) -> None:
    policy = IngestionSecurityPolicy(limits=IngestionLimits(max_page_count=2))
    source = __import__("eixo").DocumentSource.from_bytes(
        PDF,
        filename="sample.pdf",
        declared_mime="application/pdf",
        metadata={"page_count": "3"},
    )

    with pytest.raises(PageLimitExceededError):
        async with DocumentEngine.local(security=policy, data_directory=tmp_path) as engine:
            await engine.ingest(source)


@pytest.mark.anyio
async def test_security_read_timeout_for_stream(tmp_path: Path) -> None:
    policy = IngestionSecurityPolicy(
        limits=IngestionLimits(read_timeout_seconds=0.01),
    )
    source = __import__("eixo").DocumentSource.from_stream(
        SlowStream(PDF, delay=0.05),
        filename="sample.pdf",
        declared_mime="application/pdf",
    )

    with pytest.raises(ReadTimeoutError):
        async with DocumentEngine.local(security=policy, data_directory=tmp_path) as engine:
            await engine.ingest(source)


@pytest.mark.anyio
async def test_rejected_documents_are_not_stored(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedFormatError):
        async with DocumentEngine.local(data_directory=tmp_path) as engine:
            await engine.ingest(b"not a supported document")

    assert not (tmp_path / "artifacts").exists()
    assert not (tmp_path / "documents").exists()


@pytest.mark.anyio
async def test_artifact_store_rejects_traversal_storage_keys(tmp_path: Path) -> None:
    from eixo.artifacts import LocalArtifactStore
    from eixo.core import ArtifactReference, ArtifactId

    store = LocalArtifactStore(tmp_path)
    reference = ArtifactReference(
        artifact_id=ArtifactId.new(),
        kind="original-document",
        storage_backend="local",
        storage_key="../../outside",
    )

    with pytest.raises(PathTraversalError):
        await store.exists(reference)


def xlsx_zip(
    *,
    workbook: str = "<workbook />",
    extra_entries: dict[str, str] | None = None,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("xl/workbook.xml", workbook)
        for name, value in (extra_entries or {}).items():
            archive.writestr(name, value)
    return output.getvalue()


def generic_zip() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
    return output.getvalue()


class SlowStream(io.BytesIO):
    def __init__(self, content: bytes, *, delay: float) -> None:
        super().__init__(content)
        self.delay = delay

    def read(self, size: int = -1) -> bytes:
        time.sleep(self.delay)
        return super().read(size)
