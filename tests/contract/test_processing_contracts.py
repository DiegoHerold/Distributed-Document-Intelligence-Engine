from __future__ import annotations

from pathlib import Path

from eixo.core import (
    BytesSource,
    ContractVersion,
    DocumentId,
    ErrorCategory,
    ErrorResult,
    InspectionRequest,
    InspectionResult,
    JobId,
    LocalPathSource,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
    ResultStatus,
)


def test_processing_request_serializes_without_transport_objects() -> None:
    request = ProcessingRequest(source=LocalPathSource(path=Path("sample.pdf")))
    data = request.to_dict()

    assert data["source"]["source_type"] == "local_path"
    assert data["profile"] == "balanced"
    assert data["contract_version"] == "1.0.0"


def test_processing_result_and_error_contract() -> None:
    error = ErrorResult(
        code="capability.not_found",
        message="No compatible capability found",
        category=ErrorCategory.CAPABILITY,
        retryable=False,
    )
    result = ProcessingResult(
        job_id=JobId.new(),
        document_id=DocumentId.new(),
        status=ProcessingStatus.FAILED,
        errors=(error,),
    )

    assert result.to_dict()["errors"][0]["category"] == "capability"


def test_json_schema_generation_for_public_contracts() -> None:
    schema = ProcessingRequest.json_schema()
    assert schema["type"] == "object"
    assert "source" in schema["properties"]

    result_schema = InspectionResult.json_schema()
    assert result_schema["title"] == "InspectionResult"


def test_bytes_source_and_inspection_contract() -> None:
    source = BytesSource(content=b"abc", size=3, filename="a.txt")
    request = InspectionRequest(source=source)
    result = InspectionResult(
        document_id=None,
        detected_format="txt",
        declared_media_type="text/plain",
        detected_media_type="text/plain",
        size=3,
        status=ResultStatus.SUCCESS,
    )

    assert request.source.to_dict()["size"] == 3
    assert result.status is ResultStatus.SUCCESS
    assert isinstance(request.to_dict()["correlation_id"], str)
    assert isinstance(ProcessingRequest(source=source).contract_version, ContractVersion)

