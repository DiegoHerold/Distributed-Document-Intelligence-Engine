from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import BinaryIO

from eixo.application.ingestion import (
    CANONICAL_MIME,
    DETECTED_EXTENSION,
    EXTENSION_ALIASES,
    MIME_ALIASES,
    SAMPLE_SIZE,
    ResolvedDocumentSource,
)
from eixo.core import (
    ArchiveEntryTooLargeError,
    ArchiveTooManyEntriesError,
    ArchiveUncompressedSizeExceededError,
    CorruptedFileError,
    DetectedDocumentFormat,
    DocumentFormat,
    EmptyFileError,
    EncryptedArchiveNotAllowedError,
    EixoWarning,
    FileTooLargeError,
    IngestionLimits,
    IngestionSecurityPolicy,
    IngestionSecurityError,
    InvalidContainerError,
    InvalidDocumentStructureError,
    InvalidMimeError,
    MimeMismatchError,
    PageLimitExceededError,
    PathTraversalError,
    ReadTimeoutError,
    SecurityValidationResult,
    SecurityValidationStatus,
    SuspiciousCompressionRatioError,
    TruncatedFileError,
    UnsafeArchiveEntryError,
    UnsafeFilenameError,
    UnsupportedFormatError,
)

logger = logging.getLogger(__name__)

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True, slots=True)
class SafeFilename:
    value: str
    changed: bool = False


@dataclass(frozen=True, slots=True)
class FilenameSanitizer:
    max_length: int = 180

    def sanitize(self, value: str | None) -> SafeFilename:
        if value is None:
            return SafeFilename("document", changed=True)
        original = value
        if "\x00" in value:
            raise UnsafeFilenameError("Filename contains a null byte")
        normalized = unicodedata.normalize("NFKC", value)
        if any(_is_control_character(character) for character in normalized):
            raise UnsafeFilenameError("Filename contains control characters")
        normalized = normalized.replace("\\", "/")
        name = PurePosixPath(normalized).name.strip().strip(". ")
        if not name:
            raise UnsafeFilenameError("Filename is empty after sanitization")
        stem = name.split(".", 1)[0].upper()
        if stem in WINDOWS_RESERVED_NAMES:
            raise UnsafeFilenameError("Filename uses a reserved Windows name")
        if len(name) > self.max_length:
            suffix = PurePosixPath(name).suffix
            keep = max(self.max_length - len(suffix), 1)
            name = f"{name[:keep]}{suffix}"
        changed = name != original
        return SafeFilename(name, changed=changed)


@dataclass(frozen=True, slots=True)
class DocumentSecurityValidator:
    policy: IngestionSecurityPolicy

    async def validate(
        self,
        *,
        source: ResolvedDocumentSource,
        detected_format: DetectedDocumentFormat,
    ) -> SecurityValidationResult:
        logger.info("security.validation_started", extra={"event": "validation_started"})
        try:
            return await self._validate(source=source, detected_format=detected_format)
        except IngestionSecurityError as exc:
            _log_security_rejection(exc)
            raise

    async def _validate(
        self,
        *,
        source: ResolvedDocumentSource,
        detected_format: DetectedDocumentFormat,
    ) -> SecurityValidationResult:
        warnings: list[EixoWarning] = []
        safe_filename = self._validate_filename(source)
        if safe_filename.changed:
            warnings.append(
                EixoWarning(
                    code="filename_sanitized",
                    message="Document filename was sanitized.",
                    scope="source",
                    details={"safe_filename": safe_filename.value},
                )
            )
        self._validate_known_size(source.content_length)
        await self._validate_non_empty(source)
        self._validate_format(detected_format)
        warnings.extend(self._validate_mime_and_extension(detected_format))
        await self._validate_structure(source, detected_format.format)
        page_count = self._known_page_count(source)
        self._validate_page_count(page_count)
        status = (
            SecurityValidationStatus.ACCEPTED_WITH_WARNINGS
            if warnings
            else SecurityValidationStatus.ACCEPTED
        )
        logger.info("security.validation_passed", extra={"event": "validation_passed"})
        return SecurityValidationResult(
            status=status,
            warnings=tuple(warnings),
            safe_filename=safe_filename.value,
            page_count=page_count,
        )

    def _validate_filename(self, source: ResolvedDocumentSource) -> SafeFilename:
        return FilenameSanitizer(self.policy.max_filename_length).sanitize(source.filename)

    def _validate_known_size(self, size: int | None) -> None:
        if size is None:
            return
        if size > self.policy.limits.max_file_size_bytes:
            raise FileTooLargeError(
                "Document exceeds the configured maximum size",
                public_context={
                    "limit_bytes": self.policy.limits.max_file_size_bytes,
                    "observed_bytes": size,
                    "unit": "bytes",
                },
            )
        if self.policy.reject_empty_files and size == 0:
            raise EmptyFileError("Document source is empty")

    async def _validate_non_empty(self, source: ResolvedDocumentSource) -> None:
        if not self.policy.reject_empty_files:
            return
        sample = await read_sample_with_timeout(source, self.policy.limits)
        if not sample:
            raise EmptyFileError("Document source is empty")

    def _validate_format(self, detected_format: DetectedDocumentFormat) -> None:
        if detected_format.format == DocumentFormat.UNKNOWN:
            raise UnsupportedFormatError("Document format is not supported")
        if detected_format.format not in self.policy.allowed_formats:
            raise UnsupportedFormatError(
                "Document format is not allowed",
                public_context={"detected_format": detected_format.format.value},
            )

    def _validate_mime_and_extension(
        self,
        detected_format: DetectedDocumentFormat,
    ) -> tuple[EixoWarning, ...]:
        warnings: list[EixoWarning] = []
        declared_mime = detected_format.declared_mime
        if declared_mime is not None:
            normalized = declared_mime.strip().lower()
            if "/" not in normalized:
                raise InvalidMimeError("Declared MIME type is invalid")
            if normalized not in self.policy.allowed_mime_types:
                raise InvalidMimeError(
                    "Declared MIME type is not allowed",
                    public_context={"declared_mime": normalized},
                )
            if MIME_ALIASES.get(normalized) != detected_format.format:
                if self.policy.require_mime_match:
                    raise MimeMismatchError(
                        "Declared MIME type does not match detected content format",
                        public_context={
                            "declared_mime": normalized,
                            "detected_format": detected_format.format.value,
                        },
                    )
                warnings.append(
                    EixoWarning(
                        code="declared_mime_mismatch",
                        message="Declared MIME type does not match detected content format.",
                        scope="source",
                        details={
                            "declared_mime": normalized,
                            "detected_format": detected_format.format.value,
                        },
                    )
                )
        declared_extension = detected_format.declared_extension
        if declared_extension is not None:
            expected = EXTENSION_ALIASES.get(declared_extension.lower())
            if expected != detected_format.format:
                if not self.policy.allow_extension_mismatch:
                    raise UnsafeFilenameError(
                        "Declared extension does not match detected content format"
                    )
                warnings.append(
                    EixoWarning(
                        code="extension_mismatch",
                        message="Declared extension does not match detected content format.",
                        scope="source",
                        details={
                            "declared_extension": declared_extension,
                            "detected_format": detected_format.format.value,
                        },
                    )
                )
        return tuple(warnings)

    async def _validate_structure(
        self,
        source: ResolvedDocumentSource,
        document_format: DocumentFormat,
    ) -> None:
        sample = await read_sample_with_timeout(source, self.policy.limits)
        if document_format == DocumentFormat.PDF:
            if not sample.startswith(b"%PDF-"):
                raise CorruptedFileError("PDF signature is invalid")
            if len(sample) < len(b"%PDF-1.0\n"):
                raise TruncatedFileError("PDF appears to be truncated")
            return
        if document_format == DocumentFormat.PNG:
            if not sample.startswith(b"\x89PNG\r\n\x1a\n"):
                raise CorruptedFileError("PNG signature is invalid")
            if len(sample) < 16:
                raise TruncatedFileError("PNG appears to be truncated")
            return
        if document_format == DocumentFormat.JPEG:
            if not sample.startswith(b"\xff\xd8\xff"):
                raise CorruptedFileError("JPEG signature is invalid")
            if len(sample) < 4:
                raise TruncatedFileError("JPEG appears to be truncated")
            return
        if document_format == DocumentFormat.TIFF:
            if not sample.startswith((b"II*\x00", b"MM\x00*")):
                raise CorruptedFileError("TIFF signature is invalid")
            return
        if document_format == DocumentFormat.CSV:
            if b"\x00" in sample:
                raise CorruptedFileError("CSV contains binary null bytes")
            return
        if document_format == DocumentFormat.XLSX:
            await ArchiveSecurityValidator(self.policy).validate_xlsx(source.stream)

    def _known_page_count(self, source: ResolvedDocumentSource) -> int | None:
        metadata = source.source_metadata or {}
        raw_value = metadata.get("page_count")
        if raw_value is None:
            return None
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise InvalidDocumentStructureError(
                "Known page count metadata is invalid",
                cause=exc,
            ) from exc
        if value < 0:
            raise InvalidDocumentStructureError("Known page count cannot be negative")
        return value

    def _validate_page_count(self, page_count: int | None) -> None:
        limit = self.policy.limits.max_page_count
        if page_count is None or limit is None:
            return
        if page_count > limit:
            raise PageLimitExceededError(
                "Document exceeds the configured page limit",
                public_context={"limit_pages": limit, "observed_pages": page_count},
            )


@dataclass(frozen=True, slots=True)
class ArchiveSecurityValidator:
    policy: IngestionSecurityPolicy

    async def validate_xlsx(self, stream: BinaryIO) -> None:
        current = _tell(stream)
        try:
            stream.seek(0)
            try:
                archive = zipfile.ZipFile(stream)
            except zipfile.BadZipFile as exc:
                raise InvalidContainerError("XLSX ZIP container is invalid", cause=exc) from exc
            with archive:
                infos = archive.infolist()
                self._validate_metadata(infos)
                names = {info.filename for info in infos}
                if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                    raise InvalidDocumentStructureError("XLSX structure is incomplete")
                for required_name in ("[Content_Types].xml", "xl/workbook.xml"):
                    await self._read_limited_entry(archive, required_name)
        finally:
            stream.seek(current)

    def _validate_metadata(self, infos: list[zipfile.ZipInfo]) -> None:
        limits = self.policy.limits
        if len(infos) > limits.max_archive_entries:
            raise ArchiveTooManyEntriesError(
                "Archive contains too many entries",
                public_context={
                    "limit_entries": limits.max_archive_entries,
                    "observed_entries": len(infos),
                },
            )
        total_uncompressed = 0
        total_compressed = 0
        for info in infos:
            _validate_archive_entry_name(info.filename)
            if info.flag_bits & 0x1 and not self.policy.allow_encrypted_archives:
                raise EncryptedArchiveNotAllowedError("Encrypted archive entries are not allowed")
            total_uncompressed += info.file_size
            total_compressed += info.compress_size
            if info.file_size > limits.max_archive_entry_size_bytes:
                raise ArchiveEntryTooLargeError(
                    "Archive entry exceeds the configured size limit",
                    public_context={
                        "limit_bytes": limits.max_archive_entry_size_bytes,
                        "observed_bytes": info.file_size,
                    },
                )
        if total_uncompressed > limits.max_archive_uncompressed_bytes:
            raise ArchiveUncompressedSizeExceededError(
                "Archive uncompressed size exceeds the configured limit",
                public_context={
                    "limit_bytes": limits.max_archive_uncompressed_bytes,
                    "observed_bytes": total_uncompressed,
                },
            )
        ratio = total_uncompressed / max(total_compressed, 1)
        if ratio > limits.max_compression_ratio:
            raise SuspiciousCompressionRatioError(
                "Archive compression ratio is suspicious",
                public_context={
                    "limit_ratio": limits.max_compression_ratio,
                    "observed_ratio": round(ratio, 2),
                },
            )

    async def _read_limited_entry(self, archive: zipfile.ZipFile, name: str) -> None:
        limits = self.policy.limits
        total = 0
        try:
            with archive.open(name) as handle:
                while True:
                    chunk = await read_with_timeout(handle, 64 * 1024, limits)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limits.max_archive_entry_size_bytes:
                        raise ArchiveEntryTooLargeError(
                            "Archive entry exceeds the configured size limit during read",
                            public_context={
                                "limit_bytes": limits.max_archive_entry_size_bytes,
                                "observed_bytes": total,
                            },
                        )
        except RuntimeError as exc:
            raise InvalidContainerError("Archive entry could not be read", cause=exc) from exc


async def read_sample_with_timeout(
    source: ResolvedDocumentSource,
    limits: IngestionLimits,
    size: int = SAMPLE_SIZE,
) -> bytes:
    source.rewind()
    sample = await read_with_timeout(source.stream, size, limits)
    source.rewind()
    return sample


async def read_with_timeout(
    stream: BinaryIO,
    size: int,
    limits: IngestionLimits,
) -> bytes:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(stream.read, size),
            timeout=limits.read_timeout_seconds,
        )
    except TimeoutError as exc:
        raise ReadTimeoutError(
            "Document read timed out",
            public_context={"timeout_seconds": limits.read_timeout_seconds},
            cause=exc,
        ) from exc


def _validate_archive_entry_name(name: str) -> None:
    if "\x00" in name or "\\" in name:
        raise UnsafeArchiveEntryError("Archive entry name is unsafe")
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    if posix.is_absolute() or windows.is_absolute():
        raise UnsafeArchiveEntryError("Archive entry uses an absolute path")
    if any(part in {"", ".", ".."} for part in posix.parts):
        raise UnsafeArchiveEntryError("Archive entry contains unsafe path segments")


def _tell(stream: BinaryIO) -> int:
    try:
        return int(stream.tell())
    except OSError:
        return 0


def _is_control_character(character: str) -> bool:
    return bool(re.match(r"[\x00-\x1f\x7f]", character))


def _log_security_rejection(error: IngestionSecurityError) -> None:
    event_by_code = {
        "file_too_large": "size_limit_exceeded",
        "mime_mismatch": "mime_mismatch",
        "corrupted_file": "corruption_detected",
        "invalid_container": "archive_rejected",
        "archive_too_many_entries": "archive_rejected",
        "archive_uncompressed_size_exceeded": "archive_rejected",
        "archive_entry_too_large": "archive_rejected",
        "suspicious_compression_ratio": "archive_rejected",
        "zip_bomb_detected": "archive_rejected",
        "path_traversal_detected": "path_traversal_detected",
        "unsafe_storage_key": "path_traversal_detected",
        "read_timeout": "read_timeout",
    }.get(error.code, "validation_rejected")
    fields = {"event": "validation_rejected", "error_code": error.code}
    if event_by_code != "validation_rejected":
        fields["security_event"] = event_by_code
    logger.info("security.validation_rejected", extra=fields)


__all__ = [
    "ArchiveSecurityValidator",
    "DocumentSecurityValidator",
    "FilenameSanitizer",
    "SafeFilename",
    "read_sample_with_timeout",
    "read_with_timeout",
]
