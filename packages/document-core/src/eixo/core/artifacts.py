from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import BinaryIO

from eixo.core.contracts import ArtifactReference
from eixo.core.ids import ArtifactId
from eixo.core.ingestion import ContentHash
from eixo.core.serialization import Serializable


class ArtifactType(StrEnum):
    ORIGINAL_DOCUMENT = "original_document"
    DERIVED = "derived"
    RESULT = "result"


@dataclass(frozen=True, slots=True)
class ArtifactMetadata(Serializable):
    artifact_id: ArtifactId
    artifact_type: ArtifactType
    content_hash: ContentHash
    size_bytes: int
    media_type: str | None = None
    original_filename: str | None = None
    storage_backend: str | None = None
    storage_key: str | None = None
    created_at: str | None = None
    producer: str | None = None
    source: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    version: int = 1

    def __post_init__(self) -> None:
        if self.size_bytes < 0:
            raise ValueError("size_bytes cannot be negative")
        if self.version <= 0:
            raise ValueError("version must be positive")

    def to_reference(self) -> ArtifactReference:
        return ArtifactReference(
            artifact_id=self.artifact_id,
            kind=self.artifact_type.value,
            media_type=self.media_type,
            storage_backend=self.storage_backend,
            storage_key=self.storage_key,
            content_hash=self.content_hash.canonical_value,
            size_bytes=self.size_bytes,
            original_filename=self.original_filename,
            created_at=self.created_at,
            version=self.version,
            metadata=self.metadata,
        )


@dataclass(frozen=True, slots=True)
class ArtifactWriteRequest:
    stream: BinaryIO
    artifact_type: ArtifactType
    content_hash: ContentHash
    size_bytes: int
    media_type: str | None = None
    original_filename: str | None = None
    producer: str | None = None
    source: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.size_bytes < 0:
            raise ValueError("size_bytes cannot be negative")
        if not hasattr(self.stream, "read"):
            raise ValueError("stream must be readable")


@dataclass(frozen=True, slots=True)
class StoredArtifact(Serializable):
    reference: ArtifactReference
    metadata: ArtifactMetadata


@dataclass(frozen=True, slots=True)
class OriginalDocumentArtifact(Serializable):
    reference: ArtifactReference
    metadata: ArtifactMetadata


__all__ = [
    "ArtifactMetadata",
    "ArtifactType",
    "ArtifactWriteRequest",
    "OriginalDocumentArtifact",
    "StoredArtifact",
]
