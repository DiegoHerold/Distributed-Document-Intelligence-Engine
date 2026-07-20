from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from eixo.application.document_lifecycle import (
    DocumentLifecycle,
    LocalDocumentRepository,
    new_document_record,
)
from eixo.core import (
    ContentHash,
    DetectedDocumentFormat,
    DetectionConfidence,
    DocumentFormat,
    DocumentIdentity,
    DocumentRepositoryError,
    DocumentStatus,
    DocumentVersionConflictError,
)


def identity() -> DocumentIdentity:
    detected = DetectedDocumentFormat(
        format=DocumentFormat.PDF,
        canonical_mime="application/pdf",
        detected_extension=".pdf",
        confidence=DetectionConfidence.EXACT,
        detection_method="signature",
    )
    return DocumentIdentity(
        content_hash=ContentHash("sha256", "a" * 64),
        size_bytes=10,
        detected_format=detected,
    )


def record():
    detected = identity().detected_format
    return new_document_record(
        identity=identity(),
        detected_format=detected,
        source_metadata={"filename": "a.pdf"},
        warnings=(),
    )


def test_document_lifecycle_allows_expected_transitions() -> None:
    lifecycle = DocumentLifecycle.default()
    initial, _ = record()

    validated, transition = lifecycle.transition(
        initial,
        to_status=DocumentStatus.VALIDATED,
        reason="validated",
    )

    assert validated.status == DocumentStatus.VALIDATED
    assert validated.version == initial.version + 1
    assert transition.from_status == DocumentStatus.RECEIVED
    assert transition.to_status == DocumentStatus.VALIDATED


def test_document_lifecycle_rejects_arbitrary_transition() -> None:
    lifecycle = DocumentLifecycle.default()
    initial, _ = record()

    with pytest.raises(DocumentRepositoryError):
        lifecycle.transition(
            initial,
            to_status=DocumentStatus.COMPLETED,
            reason="skip",
        )


@pytest.mark.anyio
async def test_local_document_repository_persists_record_and_transitions(
    tmp_path: Path,
) -> None:
    repository = LocalDocumentRepository(tmp_path)
    initial, received = record()

    await repository.create(initial)
    await repository.append_transition(received)
    loaded = await repository.get(initial.document_id)

    assert loaded.document_id == initial.document_id
    assert loaded.status == DocumentStatus.RECEIVED
    assert await repository.transitions(initial.document_id) == (received,)

    updated = replace(loaded, status=DocumentStatus.VALIDATED, version=loaded.version + 1)
    await repository.update(updated, expected_version=loaded.version)
    with pytest.raises(DocumentVersionConflictError):
        await repository.update(updated, expected_version=loaded.version)
