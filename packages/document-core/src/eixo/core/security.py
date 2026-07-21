from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from eixo.core.ingestion import DocumentFormat
from eixo.core.serialization import Serializable
from eixo.core.warnings import EixoWarning


DEFAULT_ALLOWED_FORMATS = (
    DocumentFormat.PDF,
    DocumentFormat.XLSX,
    DocumentFormat.CSV,
    DocumentFormat.PNG,
    DocumentFormat.JPEG,
    DocumentFormat.TIFF,
)

DEFAULT_ALLOWED_MIME_TYPES = (
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "application/csv",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
)


class SecurityValidationStatus(StrEnum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_WARNINGS = "accepted_with_warnings"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class IngestionLimits(Serializable):
    max_file_size_bytes: int = 100 * 1024 * 1024
    max_page_count: int | None = 500
    read_timeout_seconds: float = 30.0
    max_archive_entries: int = 1000
    max_archive_uncompressed_bytes: int = 200 * 1024 * 1024
    max_archive_entry_size_bytes: int = 100 * 1024 * 1024
    max_compression_ratio: float = 100.0
    max_archive_nesting_depth: int = 1

    def __post_init__(self) -> None:
        positive_ints = {
            "max_file_size_bytes": self.max_file_size_bytes,
            "max_archive_entries": self.max_archive_entries,
            "max_archive_uncompressed_bytes": self.max_archive_uncompressed_bytes,
            "max_archive_entry_size_bytes": self.max_archive_entry_size_bytes,
            "max_archive_nesting_depth": self.max_archive_nesting_depth,
        }
        for name, value in positive_ints.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_page_count is not None and self.max_page_count <= 0:
            raise ValueError("max_page_count must be positive when set")
        if self.read_timeout_seconds <= 0:
            raise ValueError("read_timeout_seconds must be positive")
        if self.max_compression_ratio <= 0:
            raise ValueError("max_compression_ratio must be positive")


@dataclass(frozen=True, slots=True)
class IngestionSecurityPolicy(Serializable):
    limits: IngestionLimits = field(default_factory=IngestionLimits)
    allowed_formats: tuple[DocumentFormat, ...] = DEFAULT_ALLOWED_FORMATS
    allowed_mime_types: tuple[str, ...] = DEFAULT_ALLOWED_MIME_TYPES
    require_mime_match: bool = False
    allow_extension_mismatch: bool = True
    reject_empty_files: bool = True
    allow_encrypted_archives: bool = False
    max_filename_length: int = 180

    def __post_init__(self) -> None:
        if not self.allowed_formats:
            raise ValueError("allowed_formats cannot be empty")
        if not self.allowed_mime_types:
            raise ValueError("allowed_mime_types cannot be empty")
        if self.max_filename_length <= 0:
            raise ValueError("max_filename_length must be positive")
        normalized_mime_types = tuple(
            media_type.strip().lower() for media_type in self.allowed_mime_types
        )
        if any("/" not in media_type for media_type in normalized_mime_types):
            raise ValueError("allowed_mime_types must contain valid media types")
        object.__setattr__(self, "allowed_mime_types", normalized_mime_types)


@dataclass(frozen=True, slots=True)
class DocumentSecurityOptions(Serializable):
    policy: IngestionSecurityPolicy = field(default_factory=IngestionSecurityPolicy)


@dataclass(frozen=True, slots=True)
class SecurityValidationResult(Serializable):
    status: SecurityValidationStatus
    warnings: tuple[EixoWarning, ...] = ()
    safe_filename: str | None = None
    page_count: int | None = None


__all__ = [
    "DEFAULT_ALLOWED_FORMATS",
    "DEFAULT_ALLOWED_MIME_TYPES",
    "DocumentSecurityOptions",
    "IngestionLimits",
    "IngestionSecurityPolicy",
    "SecurityValidationResult",
    "SecurityValidationStatus",
]
