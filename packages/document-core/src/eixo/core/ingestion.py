from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from eixo.core.serialization import Serializable
from eixo.core.warnings import EixoWarning


class DocumentFormat(StrEnum):
    PDF = "pdf"
    XLSX = "xlsx"
    CSV = "csv"
    PNG = "png"
    JPEG = "jpeg"
    TIFF = "tiff"
    UNKNOWN = "unknown"


class DetectionConfidence(StrEnum):
    EXACT = "exact"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class SourceOwnership(StrEnum):
    CALLER = "caller"
    RESOLVER = "resolver"
    TEMPORARY_COPY = "temporary_copy"


@dataclass(frozen=True, slots=True)
class DetectedDocumentFormat(Serializable):
    format: DocumentFormat
    canonical_mime: str | None = None
    detected_extension: str | None = None
    confidence: DetectionConfidence = DetectionConfidence.UNKNOWN
    detection_method: str = "unknown"
    declared_mime: str | None = None
    declared_extension: str | None = None
    mime_matches: bool | None = None
    extension_matches: bool | None = None
    warnings: tuple[EixoWarning, ...] = ()


@dataclass(frozen=True, slots=True)
class ContentHash(Serializable):
    algorithm: str
    digest: str
    canonical_value: str = field(init=False)

    def __post_init__(self) -> None:
        algorithm = self.algorithm.strip().lower()
        digest = self.digest.strip().lower()
        if not algorithm:
            raise ValueError("algorithm is required")
        if not digest:
            raise ValueError("digest is required")
        object.__setattr__(self, "algorithm", algorithm)
        object.__setattr__(self, "digest", digest)
        object.__setattr__(self, "canonical_value", f"{algorithm}:{digest}")


@dataclass(frozen=True, slots=True)
class ContentMetadata(Serializable):
    size_bytes: int
    content_hash: ContentHash
    detected_format: DetectedDocumentFormat
    filename: str | None = None
    declared_mime: str | None = None
    resolved_mime: str | None = None
    source_kind: str | None = None

    def __post_init__(self) -> None:
        if self.size_bytes < 0:
            raise ValueError("size_bytes cannot be negative")


@dataclass(frozen=True, slots=True)
class DocumentIdentity(Serializable):
    content_hash: ContentHash
    size_bytes: int
    detected_format: DetectedDocumentFormat
    identity_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.size_bytes < 0:
            raise ValueError("size_bytes cannot be negative")


@dataclass(frozen=True, slots=True)
class IdentifiedDocumentContent(Serializable):
    metadata: ContentMetadata
    identity: DocumentIdentity


__all__ = [
    "ContentHash",
    "ContentMetadata",
    "DetectedDocumentFormat",
    "DetectionConfidence",
    "DocumentFormat",
    "DocumentIdentity",
    "IdentifiedDocumentContent",
    "SourceOwnership",
]
