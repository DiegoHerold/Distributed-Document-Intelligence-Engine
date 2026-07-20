from __future__ import annotations

import io
from pathlib import Path

import pytest

from eixo.artifacts import LocalArtifactStore
from eixo.artifacts.store import content_hash_from_value, storage_key_for_hash
from eixo.core import (
    ArtifactHashMismatchError,
    ArtifactType,
    ArtifactWriteRequest,
    ContentHash,
)


@pytest.mark.anyio
async def test_local_artifact_store_writes_opens_and_verifies_content(tmp_path: Path) -> None:
    content = b"%PDF-1.7\n"
    content_hash = sha256(content)
    store = LocalArtifactStore(tmp_path)

    reference = await store.put(
        ArtifactWriteRequest(
            stream=io.BytesIO(content),
            artifact_type=ArtifactType.ORIGINAL_DOCUMENT,
            content_hash=content_hash,
            size_bytes=len(content),
            media_type="application/pdf",
            original_filename="sample.pdf",
        )
    )

    assert reference.storage_backend == "local"
    assert reference.storage_key == storage_key_for_hash(content_hash)
    assert ":\\" not in (reference.storage_key or "")
    assert await store.exists(reference)
    await store.verify_integrity(reference)

    async with store.open(reference) as reader:
        assert reader.stream.read() == content
        assert reader.metadata.original_filename == "sample.pdf"


@pytest.mark.anyio
async def test_local_artifact_store_deduplicates_bytes_by_hash(tmp_path: Path) -> None:
    content = b"a;b\n1;2\n"
    content_hash = sha256(content)
    store = LocalArtifactStore(tmp_path)

    first = await store.put(
        ArtifactWriteRequest(
            stream=io.BytesIO(content),
            artifact_type=ArtifactType.ORIGINAL_DOCUMENT,
            content_hash=content_hash,
            size_bytes=len(content),
            original_filename="first.csv",
        )
    )
    second = await store.put(
        ArtifactWriteRequest(
            stream=io.BytesIO(content),
            artifact_type=ArtifactType.ORIGINAL_DOCUMENT,
            content_hash=content_hash,
            size_bytes=len(content),
            original_filename="second.csv",
        )
    )

    assert second.artifact_id == first.artifact_id
    assert second.storage_key == first.storage_key


@pytest.mark.anyio
async def test_local_artifact_store_detects_hash_mismatch(tmp_path: Path) -> None:
    content = b"real"
    wrong_hash = sha256(b"other")
    store = LocalArtifactStore(tmp_path)

    with pytest.raises(ArtifactHashMismatchError):
        await store.put(
            ArtifactWriteRequest(
                stream=io.BytesIO(content),
                artifact_type=ArtifactType.ORIGINAL_DOCUMENT,
                content_hash=wrong_hash,
                size_bytes=len(content),
            )
        )


def sha256(content: bytes) -> ContentHash:
    import hashlib

    return content_hash_from_value(f"sha256:{hashlib.sha256(content).hexdigest()}")
