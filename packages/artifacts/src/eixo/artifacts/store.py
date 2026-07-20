from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Protocol

from eixo.core import (
    ArtifactCorruptedError,
    ArtifactHashMismatchError,
    ArtifactId,
    ArtifactMetadata,
    ArtifactMetadataMissingError,
    ArtifactNotFoundError,
    ArtifactReference,
    ArtifactSizeMismatchError,
    ArtifactStorageError,
    ArtifactType,
    ArtifactWriteRequest,
    ContentHash,
    isoformat_utc,
    utc_now,
)
from eixo.core.serialization import to_jsonable

CHUNK_SIZE = 1024 * 1024
LOCAL_BACKEND = "local"


class ArtifactStore(Protocol):
    async def put(self, artifact: ArtifactWriteRequest) -> ArtifactReference:
        ...

    def open(self, reference: ArtifactReference) -> "ArtifactOpenContext":
        ...

    async def exists(self, reference: ArtifactReference) -> bool:
        ...

    async def get_metadata(self, reference: ArtifactReference) -> ArtifactMetadata:
        ...

    async def verify_integrity(self, reference: ArtifactReference) -> None:
        ...

    async def delete(self, reference: ArtifactReference) -> None:
        ...


@dataclass(slots=True)
class ArtifactReader:
    reference: ArtifactReference
    metadata: ArtifactMetadata
    stream: BinaryIO

    async def __aenter__(self) -> "ArtifactReader":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def close(self) -> None:
        self.stream.close()


@dataclass(slots=True)
class ArtifactOpenContext:
    store: "LocalArtifactStore"
    reference: ArtifactReference
    _reader: ArtifactReader | None = field(default=None, init=False)

    async def __aenter__(self) -> ArtifactReader:
        reader = await self.store._open_reader(self.reference)
        self._reader = reader
        return reader

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._reader is not None:
            self._reader.close()


@dataclass(frozen=True, slots=True)
class LocalArtifactStore:
    base_directory: Path
    chunk_size: int = CHUNK_SIZE

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_directory", Path(self.base_directory))
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")

    async def put(self, artifact: ArtifactWriteRequest) -> ArtifactReference:
        self._ensure_layout()
        digest = artifact.content_hash.digest
        storage_key = storage_key_for_hash(artifact.content_hash)
        directory = self._artifact_directory(storage_key)
        content_path = directory / "content"
        metadata_path = directory / "metadata.json"
        artifact_id = ArtifactId(f"art_{digest}")
        if content_path.exists():
            metadata = await self._load_existing_metadata(metadata_path)
            await self._verify_paths(content_path, metadata_path, metadata)
            if metadata.size_bytes != artifact.size_bytes:
                raise ArtifactSizeMismatchError("Stored artifact size does not match request")
            if metadata.content_hash != artifact.content_hash:
                raise ArtifactHashMismatchError("Stored artifact hash does not match request")
            return metadata.to_reference()

        directory.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            temp_path, digest_value, size = self._write_temp(artifact.stream)
            if size != artifact.size_bytes:
                raise ArtifactSizeMismatchError(
                    "Artifact size does not match identified content",
                    public_context={"expected_size": artifact.size_bytes, "actual_size": size},
                )
            if digest_value != artifact.content_hash.digest:
                raise ArtifactHashMismatchError("Artifact hash does not match identified content")
            if not content_path.exists():
                os.replace(temp_path, content_path)
                temp_path = None
            metadata = ArtifactMetadata(
                artifact_id=artifact_id,
                artifact_type=artifact.artifact_type,
                content_hash=artifact.content_hash,
                size_bytes=size,
                media_type=artifact.media_type,
                original_filename=artifact.original_filename,
                storage_backend=LOCAL_BACKEND,
                storage_key=storage_key,
                created_at=isoformat_utc(utc_now()),
                producer=artifact.producer,
                source=artifact.source,
                metadata=artifact.metadata,
            )
            self._write_metadata(metadata_path, metadata)
            return metadata.to_reference()
        except OSError as exc:
            raise ArtifactStorageError("Could not store artifact", cause=exc) from exc
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

    def open(self, reference: ArtifactReference) -> ArtifactOpenContext:
        return ArtifactOpenContext(self, reference)

    async def exists(self, reference: ArtifactReference) -> bool:
        content_path, metadata_path = self._paths_from_reference(reference)
        return content_path.exists() and metadata_path.exists()

    async def get_metadata(self, reference: ArtifactReference) -> ArtifactMetadata:
        _, metadata_path = self._paths_from_reference(reference)
        return await self._load_existing_metadata(metadata_path)

    async def verify_integrity(self, reference: ArtifactReference) -> None:
        content_path, metadata_path = self._paths_from_reference(reference)
        metadata = await self._load_existing_metadata(metadata_path)
        await self._verify_paths(content_path, metadata_path, metadata)

    async def delete(self, reference: ArtifactReference) -> None:
        content_path, metadata_path = self._paths_from_reference(reference)
        if not content_path.exists() and not metadata_path.exists():
            raise ArtifactNotFoundError("Artifact was not found")
        if content_path.exists():
            content_path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()

    async def _open_reader(self, reference: ArtifactReference) -> ArtifactReader:
        content_path, metadata_path = self._paths_from_reference(reference)
        metadata = await self._load_existing_metadata(metadata_path)
        await self._verify_paths(content_path, metadata_path, metadata, full_hash=False)
        try:
            stream = content_path.open("rb")
        except OSError as exc:
            raise ArtifactNotFoundError("Artifact content was not found", cause=exc) from exc
        return ArtifactReader(reference=metadata.to_reference(), metadata=metadata, stream=stream)

    async def _load_existing_metadata(self, metadata_path: Path) -> ArtifactMetadata:
        if not metadata_path.exists():
            raise ArtifactMetadataMissingError("Artifact metadata is missing")
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactCorruptedError("Artifact metadata is invalid", cause=exc) from exc
        return artifact_metadata_from_dict(payload)

    async def _verify_paths(
        self,
        content_path: Path,
        metadata_path: Path,
        metadata: ArtifactMetadata,
        *,
        full_hash: bool = True,
    ) -> None:
        if not content_path.exists():
            raise ArtifactNotFoundError("Artifact content was not found")
        if not metadata_path.exists():
            raise ArtifactMetadataMissingError("Artifact metadata is missing")
        actual_size = content_path.stat().st_size
        if actual_size != metadata.size_bytes:
            raise ArtifactSizeMismatchError("Artifact size does not match metadata")
        if full_hash:
            actual_hash = hash_file(content_path, chunk_size=self.chunk_size)
            if actual_hash != metadata.content_hash.digest:
                raise ArtifactHashMismatchError("Artifact hash does not match metadata")

    def _write_temp(self, stream: BinaryIO) -> tuple[Path, str, int]:
        temporary_directory = self.base_directory / "temporary"
        temporary_directory.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        fd, raw_path = tempfile.mkstemp(prefix="artifact-", suffix=".tmp", dir=temporary_directory)
        temp_path = Path(raw_path)
        try:
            with os.fdopen(fd, "wb") as handle:
                _rewind_if_possible(stream)
                while True:
                    chunk = stream.read(self.chunk_size)
                    if not chunk:
                        break
                    handle.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            _rewind_if_possible(stream)
            return temp_path, digest.hexdigest(), size
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def _write_metadata(self, metadata_path: Path, metadata: ArtifactMetadata) -> None:
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_directory = self.base_directory / "temporary"
        temporary_directory.mkdir(parents=True, exist_ok=True)
        fd, raw_path = tempfile.mkstemp(prefix="metadata-", suffix=".json", dir=temporary_directory)
        temp_path = Path(raw_path)
        try:
            payload = json.dumps(to_jsonable(metadata), sort_keys=True, indent=2)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, metadata_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def _paths_from_reference(self, reference: ArtifactReference) -> tuple[Path, Path]:
        if reference.storage_backend not in {None, LOCAL_BACKEND}:
            raise ArtifactStorageError("Artifact belongs to a different storage backend")
        if reference.storage_key is None:
            if reference.content_hash is None:
                raise ArtifactStorageError("Artifact reference does not include storage key")
            storage_key = storage_key_for_hash(content_hash_from_value(reference.content_hash))
        else:
            storage_key = reference.storage_key
        directory = self._artifact_directory(storage_key)
        return directory / "content", directory / "metadata.json"

    def _artifact_directory(self, storage_key: str) -> Path:
        relative = Path(storage_key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ArtifactStorageError("Invalid artifact storage key")
        return self.base_directory / "artifacts" / relative

    def _ensure_layout(self) -> None:
        for name in ("artifacts", "documents", "metadata", "temporary", "results"):
            (self.base_directory / name).mkdir(parents=True, exist_ok=True)


def storage_key_for_hash(content_hash: ContentHash) -> str:
    digest = content_hash.digest
    return f"{content_hash.algorithm}/{digest[:2]}/{digest[2:4]}/{digest}"


def hash_file(path: Path, *, chunk_size: int = CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def content_hash_from_value(value: str) -> ContentHash:
    if ":" not in value:
        raise ArtifactStorageError("Invalid content hash")
    algorithm, digest = value.split(":", 1)
    return ContentHash(algorithm, digest)


def artifact_metadata_from_dict(payload: dict[str, object]) -> ArtifactMetadata:
    return ArtifactMetadata(
        artifact_id=ArtifactId.parse(str(payload["artifact_id"])),
        artifact_type=ArtifactType(str(payload["artifact_type"])),
        content_hash=content_hash_from_value(str(payload["content_hash"]["canonical_value"])),
        size_bytes=int(payload["size_bytes"]),
        media_type=_optional_str(payload.get("media_type")),
        original_filename=_optional_str(payload.get("original_filename")),
        storage_backend=_optional_str(payload.get("storage_backend")),
        storage_key=_optional_str(payload.get("storage_key")),
        created_at=_optional_str(payload.get("created_at")),
        producer=_optional_str(payload.get("producer")),
        source=_optional_str(payload.get("source")),
        metadata={str(k): str(v) for k, v in dict(payload.get("metadata", {})).items()},
        version=int(payload.get("version", 1)),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _rewind_if_possible(stream: BinaryIO) -> None:
    try:
        if stream.seekable():
            stream.seek(0)
    except (AttributeError, OSError):
        return


__all__ = [
    "ArtifactOpenContext",
    "ArtifactReader",
    "ArtifactStore",
    "LocalArtifactStore",
    "artifact_metadata_from_dict",
    "content_hash_from_value",
    "hash_file",
    "storage_key_for_hash",
]
