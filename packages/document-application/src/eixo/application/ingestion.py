from __future__ import annotations

import asyncio
import hashlib
import io
import os
import tempfile
import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import BinaryIO, Protocol

from eixo.core import (
    BytesSource,
    ContentHash,
    ContentMetadata,
    DetectedDocumentFormat,
    DetectionConfidence,
    DocumentFormat,
    DocumentIdentity,
    DocumentSource,
    EixoWarning,
    EmptyFileError,
    FileTooLargeError,
    IdentifiedDocumentContent,
    IngestionSecurityPolicy,
    LocalPathSource,
    ReadTimeoutError,
    SourceNotFileError,
    SourceNotFoundError,
    SourceNotReadableError,
    SourceOwnership,
    SourceResolutionError,
    StreamSource,
    ValidationError,
)
from eixo.core.contracts import normalize_extension

CHUNK_SIZE = 1024 * 1024
SAMPLE_SIZE = 8192

CANONICAL_MIME: dict[DocumentFormat, str | None] = {
    DocumentFormat.PDF: "application/pdf",
    DocumentFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    DocumentFormat.CSV: "text/csv",
    DocumentFormat.PNG: "image/png",
    DocumentFormat.JPEG: "image/jpeg",
    DocumentFormat.TIFF: "image/tiff",
    DocumentFormat.UNKNOWN: None,
}

DETECTED_EXTENSION: dict[DocumentFormat, str | None] = {
    DocumentFormat.PDF: ".pdf",
    DocumentFormat.XLSX: ".xlsx",
    DocumentFormat.CSV: ".csv",
    DocumentFormat.PNG: ".png",
    DocumentFormat.JPEG: ".jpg",
    DocumentFormat.TIFF: ".tiff",
    DocumentFormat.UNKNOWN: None,
}

MIME_ALIASES: dict[str, DocumentFormat] = {
    "application/pdf": DocumentFormat.PDF,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": DocumentFormat.XLSX,
    "text/csv": DocumentFormat.CSV,
    "application/csv": DocumentFormat.CSV,
    "image/png": DocumentFormat.PNG,
    "image/jpeg": DocumentFormat.JPEG,
    "image/jpg": DocumentFormat.JPEG,
    "image/tiff": DocumentFormat.TIFF,
}

EXTENSION_ALIASES: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".xlsx": DocumentFormat.XLSX,
    ".csv": DocumentFormat.CSV,
    ".png": DocumentFormat.PNG,
    ".jpg": DocumentFormat.JPEG,
    ".jpeg": DocumentFormat.JPEG,
    ".tif": DocumentFormat.TIFF,
    ".tiff": DocumentFormat.TIFF,
}


class SourceResolver(Protocol):
    def resolve(self, source: DocumentSource) -> "SourceResolution":
        ...


class DocumentFormatDetector(Protocol):
    async def detect(self, source: "ResolvedDocumentSource") -> DetectedDocumentFormat:
        ...


class ContentHasher(Protocol):
    async def hash(self, source: "ResolvedDocumentSource") -> tuple[ContentHash, int]:
        ...


@dataclass(slots=True)
class ResolvedDocumentSource:
    source: DocumentSource
    stream: BinaryIO
    filename: str | None
    declared_mime: str | None
    declared_extension: str | None
    content_length: int | None
    source_kind: str
    ownership: SourceOwnership
    local_path: Path | None = None
    seekable: bool = True
    source_metadata: dict[str, str] | None = None
    _cleanup_stream: BinaryIO | None = None
    _restore_stream: BinaryIO | None = None
    _restore_position: int | None = None
    _close_external: bool = False
    _closed: bool = False

    async def __aenter__(self) -> "ResolvedDocumentSource":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        if self._restore_stream is not None and self._restore_position is not None:
            try:
                self._restore_stream.seek(self._restore_position)
            except OSError:
                pass
        if self._cleanup_stream is not None:
            self._cleanup_stream.close()
        if self._close_external and self._restore_stream is not None:
            self._restore_stream.close()
        self._closed = True

    def rewind(self) -> None:
        if not self.seekable:
            raise SourceResolutionError("Resolved source is not seekable")
        self.stream.seek(0)

    def read_sample(self, size: int = SAMPLE_SIZE) -> bytes:
        self.rewind()
        sample = self.stream.read(size)
        self.rewind()
        return sample


@dataclass(slots=True)
class SourceResolution:
    resolver: "LocalSourceResolver"
    source: DocumentSource
    _resolved: ResolvedDocumentSource | None = None

    async def __aenter__(self) -> ResolvedDocumentSource:
        resolved = await self.resolver.open(self.source)
        self._resolved = resolved
        return resolved

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        resolved = getattr(self, "_resolved", None)
        if resolved is not None:
            resolved.close()


@dataclass(frozen=True, slots=True)
class LocalSourceResolver:
    security_policy: IngestionSecurityPolicy = field(default_factory=IngestionSecurityPolicy)

    def resolve(self, source: DocumentSource) -> SourceResolution:
        return SourceResolution(self, source)

    async def open(self, source: DocumentSource) -> ResolvedDocumentSource:
        if isinstance(source, LocalPathSource):
            return self._open_path(source)
        if isinstance(source, BytesSource):
            return self._open_bytes(source)
        if isinstance(source, StreamSource):
            return await self._open_stream(source)
        raise SourceResolutionError(
            f"Unsupported source type: {source.source_type}",
            public_context={"source_type": source.source_type},
        )

    def _open_path(self, source: LocalPathSource) -> ResolvedDocumentSource:
        path = Path(source.path).expanduser()
        if not path.exists():
            raise SourceNotFoundError(
                "Document source was not found",
                public_context={"source": str(source.origin_reference or source.path)},
            )
        if not path.is_file():
            raise SourceNotFileError(
                "Document source is not a file",
                public_context={"source": str(source.origin_reference or source.path)},
            )
        try:
            stream = path.open("rb")
        except OSError as exc:
            raise SourceNotReadableError("Document source is not readable", cause=exc) from exc
        stat = path.stat()
        self._validate_known_size(source.size if source.size is not None else stat.st_size)
        filename = source.filename or path.name
        return ResolvedDocumentSource(
            source=source,
            stream=stream,
            filename=filename,
            declared_mime=source.declared_media_type,
            declared_extension=source.declared_extension or normalize_extension(path.suffix),
            content_length=source.size if source.size is not None else stat.st_size,
            source_kind=source.source_type,
            ownership=SourceOwnership.RESOLVER,
            local_path=path,
            seekable=True,
            source_metadata=source.metadata,
            _cleanup_stream=stream,
        )

    def _open_bytes(self, source: BytesSource) -> ResolvedDocumentSource:
        self._validate_known_size(len(source.content))
        stream = io.BytesIO(source.content)
        return ResolvedDocumentSource(
            source=source,
            stream=stream,
            filename=source.filename,
            declared_mime=source.declared_media_type,
            declared_extension=source.declared_extension,
            content_length=len(source.content),
            source_kind=source.source_type,
            ownership=SourceOwnership.RESOLVER,
            seekable=True,
            source_metadata=source.metadata,
            _cleanup_stream=stream,
        )

    async def _open_stream(self, source: StreamSource) -> ResolvedDocumentSource:
        stream = source.stream
        if stream is None:
            raise SourceResolutionError("Stream source is missing a stream")
        if not getattr(stream, "readable", lambda: True)():
            raise SourceNotReadableError("Document stream is not readable")
        if _is_seekable(stream):
            original_position = _tell(stream)
            try:
                stream.seek(0)
            except OSError as exc:
                raise SourceNotReadableError(
                    "Document stream cannot be rewound",
                    cause=exc,
                ) from exc
            content_length = source.size if source.size is not None else _content_length(stream)
            self._validate_known_size(content_length)
            stream.seek(0)
            return ResolvedDocumentSource(
                source=source,
                stream=stream,
                filename=source.filename,
                declared_mime=source.declared_media_type,
                declared_extension=source.declared_extension,
                content_length=content_length,
                source_kind=source.source_type,
                ownership=SourceOwnership.CALLER,
                seekable=True,
                source_metadata=source.metadata,
                _restore_stream=stream,
                _restore_position=original_position,
                _close_external=source.close_on_cleanup,
            )
        if source.size is not None:
            self._validate_known_size(source.size)
        copied, size = await _copy_stream_to_temporary(
            stream,
            max_size=self.security_policy.limits.max_file_size_bytes,
            read_timeout_seconds=self.security_policy.limits.read_timeout_seconds,
        )
        self._validate_known_size(source.size if source.size is not None else size)
        copied.seek(0)
        return ResolvedDocumentSource(
            source=source,
            stream=copied,
            filename=source.filename,
            declared_mime=source.declared_media_type,
            declared_extension=source.declared_extension,
            content_length=source.size if source.size is not None else size,
            source_kind=source.source_type,
            ownership=SourceOwnership.TEMPORARY_COPY,
            seekable=True,
            source_metadata=source.metadata,
            _cleanup_stream=copied,
            _restore_stream=stream,
            _close_external=source.close_on_cleanup,
        )

    def _validate_known_size(self, size: int | None) -> None:
        if size is None:
            return
        if size > self.security_policy.limits.max_file_size_bytes:
            raise FileTooLargeError(
                "Document exceeds the configured maximum size",
                public_context={
                    "limit_bytes": self.security_policy.limits.max_file_size_bytes,
                    "observed_bytes": size,
                    "unit": "bytes",
                },
            )
        if self.security_policy.reject_empty_files and size == 0:
            raise EmptyFileError("Document source is empty")


@dataclass(frozen=True, slots=True)
class MagicBytesDocumentFormatDetector:
    read_timeout_seconds: float | None = None

    async def detect(self, source: ResolvedDocumentSource) -> DetectedDocumentFormat:
        sample = await self._read_sample(source)
        detected_format = self._detect_from_signature(sample, source)
        if detected_format is None:
            detected_format = self._detect_csv(sample, source)
        if detected_format is None:
            detected_format = DocumentFormat.UNKNOWN
            confidence = DetectionConfidence.UNKNOWN
            method = "inconclusive"
        else:
            confidence, method = self._confidence_for(detected_format, sample, source)
        return format_result(
            detected_format,
            confidence=confidence,
            method=method,
            declared_mime=source.declared_mime,
            declared_extension=source.declared_extension,
        )

    async def _read_sample(self, source: ResolvedDocumentSource) -> bytes:
        if self.read_timeout_seconds is None:
            return source.read_sample()
        source.rewind()
        try:
            sample = await asyncio.wait_for(
                asyncio.to_thread(source.stream.read, SAMPLE_SIZE),
                timeout=self.read_timeout_seconds,
            )
        except TimeoutError as exc:
            raise ReadTimeoutError(
                "Document read timed out",
                public_context={"timeout_seconds": self.read_timeout_seconds},
                cause=exc,
            ) from exc
        finally:
            source.rewind()
        return sample

    def _detect_from_signature(
        self,
        sample: bytes,
        source: ResolvedDocumentSource,
    ) -> DocumentFormat | None:
        if sample.startswith(b"%PDF-"):
            return DocumentFormat.PDF
        if sample.startswith(b"\x89PNG\r\n\x1a\n"):
            return DocumentFormat.PNG
        if sample.startswith(b"\xff\xd8\xff"):
            return DocumentFormat.JPEG
        if sample.startswith((b"II*\x00", b"MM\x00*")):
            return DocumentFormat.TIFF
        if sample.startswith(b"PK\x03\x04") and _looks_like_xlsx(source.stream):
            return DocumentFormat.XLSX
        return None

    def _detect_csv(
        self,
        sample: bytes,
        source: ResolvedDocumentSource,
    ) -> DocumentFormat | None:
        if not _looks_textual(sample):
            return None
        text = _decode_text_sample(sample)
        if text is None:
            return None
        has_csv_signal = (
            source.declared_extension == ".csv"
            or source.declared_mime in {"text/csv", "application/csv"}
        )
        if _has_repeated_delimiter(text):
            return DocumentFormat.CSV
        if has_csv_signal and "\n" in text:
            return DocumentFormat.CSV
        return None

    def _confidence_for(
        self,
        value: DocumentFormat,
        sample: bytes,
        source: ResolvedDocumentSource,
    ) -> tuple[DetectionConfidence, str]:
        if value in {
            DocumentFormat.PDF,
            DocumentFormat.PNG,
            DocumentFormat.JPEG,
            DocumentFormat.TIFF,
        }:
            return DetectionConfidence.EXACT, "signature"
        if value == DocumentFormat.XLSX:
            return DetectionConfidence.HIGH, "container-structure"
        if value == DocumentFormat.CSV:
            if _has_repeated_delimiter(_decode_text_sample(sample) or ""):
                return DetectionConfidence.MEDIUM, "text-heuristic"
            return DetectionConfidence.LOW, "declared-text-heuristic"
        return DetectionConfidence.UNKNOWN, "inconclusive"


@dataclass(frozen=True, slots=True)
class Sha256ContentHasher:
    chunk_size: int = CHUNK_SIZE
    max_size_bytes: int | None = None
    read_timeout_seconds: float | None = None

    async def hash(self, source: ResolvedDocumentSource) -> tuple[ContentHash, int]:
        digest = hashlib.sha256()
        size = 0
        source.rewind()
        while True:
            chunk = await _read_chunk(
                source.stream,
                self.chunk_size,
                read_timeout_seconds=self.read_timeout_seconds,
            )
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            if self.max_size_bytes is not None and size > self.max_size_bytes:
                raise FileTooLargeError(
                    "Document exceeds the configured maximum size during read",
                    public_context={
                        "limit_bytes": self.max_size_bytes,
                        "observed_bytes": size,
                        "unit": "bytes",
                    },
                )
        source.rewind()
        return ContentHash("sha256", digest.hexdigest()), size


@dataclass(frozen=True, slots=True)
class ContentIdentityService:
    detector: DocumentFormatDetector = field(default_factory=MagicBytesDocumentFormatDetector)
    hasher: ContentHasher = field(default_factory=Sha256ContentHasher)

    async def identify(self, source: ResolvedDocumentSource) -> IdentifiedDocumentContent:
        detected = await self.detector.detect(source)
        return await self.identify_detected(source, detected)

    async def identify_detected(
        self,
        source: ResolvedDocumentSource,
        detected: DetectedDocumentFormat,
    ) -> IdentifiedDocumentContent:
        content_hash, size = await self.hasher.hash(source)
        metadata = ContentMetadata(
            size_bytes=size,
            content_hash=content_hash,
            detected_format=detected,
            filename=source.filename,
            declared_mime=source.declared_mime,
            resolved_mime=detected.canonical_mime,
            source_kind=source.source_kind,
        )
        identity = DocumentIdentity(
            content_hash=content_hash,
            size_bytes=size,
            detected_format=detected,
        )
        return IdentifiedDocumentContent(metadata=metadata, identity=identity)


def enrich_source_with_identity(
    source: DocumentSource,
    identified: IdentifiedDocumentContent,
) -> DocumentSource:
    metadata = dict(source.metadata)
    metadata.update(
        {
            "content_hash": identified.identity.content_hash.canonical_value,
            "detected_format": identified.identity.detected_format.format.value,
        }
    )
    if isinstance(source, LocalPathSource):
        return replace(
            source,
            filename=source.filename or identified.metadata.filename,
            size=identified.metadata.size_bytes,
            metadata=metadata,
        )
    if isinstance(source, BytesSource):
        return replace(
            source,
            filename=source.filename or identified.metadata.filename,
            size=identified.metadata.size_bytes,
            metadata=metadata,
        )
    if isinstance(source, StreamSource):
        return replace(
            source,
            filename=source.filename or identified.metadata.filename,
            size=identified.metadata.size_bytes,
            metadata=metadata,
        )
    return source


def format_result(
    value: DocumentFormat,
    *,
    confidence: DetectionConfidence,
    method: str,
    declared_mime: str | None,
    declared_extension: str | None,
) -> DetectedDocumentFormat:
    canonical_mime = CANONICAL_MIME[value]
    detected_extension = DETECTED_EXTENSION[value]
    mime_matches = _mime_matches(value, declared_mime)
    extension_matches = _extension_matches(value, declared_extension)
    warnings = tuple(
        warning
        for warning in (
            _mime_warning(value, declared_mime, mime_matches),
            _extension_warning(value, declared_extension, extension_matches),
        )
        if warning is not None
    )
    return DetectedDocumentFormat(
        format=value,
        canonical_mime=canonical_mime,
        detected_extension=detected_extension,
        confidence=confidence,
        detection_method=method,
        declared_mime=declared_mime,
        declared_extension=declared_extension,
        mime_matches=mime_matches,
        extension_matches=extension_matches,
        warnings=warnings,
    )


def _mime_matches(value: DocumentFormat, declared_mime: str | None) -> bool | None:
    if declared_mime is None or value == DocumentFormat.UNKNOWN:
        return None
    return MIME_ALIASES.get(declared_mime.lower()) == value


def _extension_matches(value: DocumentFormat, declared_extension: str | None) -> bool | None:
    if declared_extension is None or value == DocumentFormat.UNKNOWN:
        return None
    return EXTENSION_ALIASES.get(declared_extension.lower()) == value


def _mime_warning(
    value: DocumentFormat,
    declared_mime: str | None,
    matches: bool | None,
) -> EixoWarning | None:
    if matches is not False:
        return None
    return EixoWarning(
        code="format.mime_mismatch",
        message="Declared MIME type does not match detected content format.",
        scope="source",
        details={"declared_mime": declared_mime, "detected_format": value.value},
    )


def _extension_warning(
    value: DocumentFormat,
    declared_extension: str | None,
    matches: bool | None,
) -> EixoWarning | None:
    if matches is not False:
        return None
    return EixoWarning(
        code="format.extension_mismatch",
        message="Declared extension does not match detected content format.",
        scope="source",
        details={"declared_extension": declared_extension, "detected_format": value.value},
    )


def _is_seekable(stream: BinaryIO) -> bool:
    try:
        return bool(stream.seekable())
    except (AttributeError, OSError):
        return False


def _tell(stream: BinaryIO) -> int:
    try:
        return int(stream.tell())
    except OSError:
        return 0


def _content_length(stream: BinaryIO) -> int | None:
    current = _tell(stream)
    try:
        end = stream.seek(0, os.SEEK_END)
        stream.seek(current)
        return int(end)
    except OSError:
        return None


async def _copy_stream_to_temporary(
    stream: BinaryIO,
    *,
    max_size: int,
    read_timeout_seconds: float,
) -> tuple[BinaryIO, int]:
    copied = tempfile.TemporaryFile("w+b")
    size = 0
    try:
        while True:
            chunk = await _read_chunk(
                stream,
                CHUNK_SIZE,
                read_timeout_seconds=read_timeout_seconds,
            )
            if not chunk:
                break
            copied.write(chunk)
            size += len(chunk)
            if size > max_size:
                raise FileTooLargeError(
                    "Document exceeds the configured maximum size during read",
                    public_context={
                        "limit_bytes": max_size,
                        "observed_bytes": size,
                        "unit": "bytes",
                    },
                )
        return copied, size
    except Exception:
        copied.close()
        raise


async def _read_chunk(
    stream: BinaryIO,
    size: int,
    *,
    read_timeout_seconds: float | None,
) -> bytes:
    if read_timeout_seconds is None:
        return stream.read(size)
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(stream.read, size),
            timeout=read_timeout_seconds,
        )
    except TimeoutError as exc:
        raise ReadTimeoutError(
            "Document read timed out",
            public_context={"timeout_seconds": read_timeout_seconds},
            cause=exc,
        ) from exc


def _looks_like_xlsx(stream: BinaryIO) -> bool:
    current = _tell(stream)
    try:
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            names = set(archive.namelist())
        return "[Content_Types].xml" in names and "xl/workbook.xml" in names
    except (OSError, zipfile.BadZipFile):
        return False
    finally:
        try:
            stream.seek(current)
        except OSError:
            pass


def _looks_textual(sample: bytes) -> bool:
    if not sample or b"\x00" in sample:
        return False
    control = sum(1 for byte in sample if byte < 9 or 13 < byte < 32)
    return control / max(len(sample), 1) < 0.05


def _decode_text_sample(sample: bytes) -> str | None:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return sample.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _has_repeated_delimiter(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    for delimiter in (",", ";", "\t", "|"):
        counts = [line.count(delimiter) for line in lines[:5]]
        if counts and min(counts) > 0 and len(set(counts)) <= 2:
            return True
    return False


__all__ = [
    "ContentHasher",
    "ContentIdentityService",
    "DocumentFormatDetector",
    "LocalSourceResolver",
    "MagicBytesDocumentFormatDetector",
    "ResolvedDocumentSource",
    "Sha256ContentHasher",
    "SourceResolution",
    "SourceResolver",
    "enrich_source_with_identity",
]
