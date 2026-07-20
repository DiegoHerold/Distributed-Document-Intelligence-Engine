from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eixo.core import (
    ContractVersion,
    CorrelationId,
    DocumentId,
    ExecutionMetadata,
    JobStatus,
    PageRequest,
    SemanticVersion,
    ensure_utc,
    isoformat_utc,
    utc_now,
)


def test_typed_ids_are_distinct_and_serializable() -> None:
    document_id = DocumentId.new()
    parsed = DocumentId.parse(str(document_id))

    assert parsed == document_id
    assert str(document_id).startswith("doc_")
    assert hash(parsed) == hash(document_id)
    with pytest.raises(ValueError):
        DocumentId.parse("job_wrong")


def test_timestamps_require_timezone_and_serialize_utc() -> None:
    now = utc_now()
    assert now.tzinfo is not None
    with pytest.raises(ValueError):
        ensure_utc(datetime(2026, 1, 1))
    assert isoformat_utc(datetime(2026, 1, 1, tzinfo=timezone.utc)).endswith("Z")


def test_versions_and_statuses_are_validated() -> None:
    assert str(SemanticVersion("1.2.3")) == "1.2.3"
    assert str(ContractVersion("1.0.0")) == "1.0.0"
    assert JobStatus.CREATED.value == "created"
    with pytest.raises(ValueError):
        SemanticVersion("1")


def test_pagination_and_execution_metadata() -> None:
    with pytest.raises(ValueError):
        PageRequest(limit=0)
    metadata = ExecutionMetadata.requested(CorrelationId.new())
    assert metadata.requested_at is not None
    assert metadata.to_dict()["correlation_id"].startswith("corr_")

