from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

from eixo import DocumentEngine
from eixo.core import (
    ArtifactId,
    ArtifactReference,
    CapabilityId,
    CapabilityStatus,
    CapabilityVersion,
    DocumentId,
    ErrorCategory,
    ErrorResult,
    ExecutionError,
    InspectionRequest,
    InspectionResult,
    JobId,
    ParseRequest,
    ParseResult,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
    ProviderId,
    ProviderVersion,
    ResultStatus,
    Severity,
    UnsupportedFormatError,
    ValidationError,
)
from eixo.core.warnings import EixoWarning
from eixo.plugins import CapabilityDescriptor, ExecutionContext, ProviderDescriptor

PROVIDER_ID = ProviderId("prov_parity")
DOCUMENT_ID = DocumentId("doc_parity")
PROCESS_JOB_ID = JobId("job_parity_result")


def parity_engine(*, timeout: float = 30.0) -> DocumentEngine:
    provider = ProviderDescriptor(
        provider_id=PROVIDER_ID,
        name="parity-provider",
        version=ProviderVersion("0.1.0"),
        status=CapabilityStatus.ACTIVE,
    )
    return DocumentEngine.local(
        providers=(provider,),
        capabilities=(
            ParityInspectionCapability(),
            ParityParseCapability(),
            ParityProcessingCapability(),
        ),
        data_directory=Path(tempfile.mkdtemp(prefix="eixo-parity-")),
        default_timeout=timeout,
    )


def scenario_from_filename(filename: str | None) -> str:
    name = filename or ""
    if "warning" in name:
        return "warning"
    if "unsupported" in name:
        return "unsupported"
    if "failure" in name:
        return "failure"
    if "timeout" in name:
        return "timeout"
    return "success"


def validate_source_size(request) -> None:
    if request.source.size == 0:
        raise ValidationError("Uploaded file cannot be empty")


def warnings_for_scenario(scenario: str) -> tuple[EixoWarning, ...]:
    if scenario != "warning":
        return ()
    return (
        EixoWarning(
            code="parity.warning",
            message="Parity warning emitted by deterministic capability.",
            severity=Severity.WARNING,
            scope="document",
            details={"capability_id": "cap_parity"},
        ),
    )


def metadata(operation: str, request) -> dict[str, object]:
    return {
        "operation": operation,
        "capability_id": f"cap_parity_{operation}",
        "provider_id": str(PROVIDER_ID),
        "filename": request.source.filename,
        "source_size": request.source.size,
    }


@dataclass(frozen=True, slots=True)
class ParityInspectionCapability:
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return descriptor("cap_parity_inspect", "inspect", "InspectionRequest", "InspectionResult")

    async def execute(
        self,
        request: InspectionRequest,
        context: ExecutionContext,
    ) -> InspectionResult:
        validate_source_size(request)
        scenario = scenario_from_filename(request.source.filename)
        if scenario == "unsupported":
            raise UnsupportedFormatError("Parity unsupported format")
        if scenario == "failure":
            raise ExecutionError("Parity inspection failed")
        if scenario == "timeout":
            await asyncio.sleep(1)
        return InspectionResult(
            document_id=DOCUMENT_ID,
            detected_format="fixture",
            declared_media_type=request.source.declared_media_type,
            detected_media_type=request.source.declared_media_type,
            size=request.source.size,
            status=ResultStatus.SUCCESS,
            metadata=metadata("inspect", request),
            warnings=warnings_for_scenario(scenario),
        )


@dataclass(frozen=True, slots=True)
class ParityParseCapability:
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return descriptor("cap_parity_parse", "parse", "ParseRequest", "ParseResult")

    async def execute(self, request: ParseRequest, context: ExecutionContext) -> ParseResult:
        validate_source_size(request)
        scenario = scenario_from_filename(request.source.filename)
        if scenario == "unsupported":
            raise UnsupportedFormatError("Parity unsupported format")
        if scenario == "failure":
            raise ExecutionError("Parity parse failed")
        if scenario == "timeout":
            await asyncio.sleep(1)
        return ParseResult(
            document_id=DOCUMENT_ID,
            status=ResultStatus.SUCCESS,
            artifacts=(
                ArtifactReference(
                    artifact_id=ArtifactId("art_parity_parse"),
                    kind="parsed-fixture",
                    media_type="application/json",
                    metadata={"capability_id": "cap_parity_parse"},
                ),
            ),
            warnings=warnings_for_scenario(scenario),
        )


@dataclass(frozen=True, slots=True)
class ParityProcessingCapability:
    @property
    def descriptor(self) -> CapabilityDescriptor:
        return descriptor("cap_parity_process", "process", "ProcessingRequest", "ProcessingResult")

    async def execute(
        self,
        request: ProcessingRequest,
        context: ExecutionContext,
    ) -> ProcessingResult:
        validate_source_size(request)
        scenario = scenario_from_filename(request.source.filename)
        if scenario == "unsupported":
            raise UnsupportedFormatError("Parity unsupported format")
        if scenario == "failure":
            raise ExecutionError("Parity processing failed")
        if scenario == "timeout":
            await asyncio.sleep(1)
        return ProcessingResult(
            job_id=PROCESS_JOB_ID,
            document_id=DOCUMENT_ID,
            status=ProcessingStatus.COMPLETED,
            data={
                "operation": "process",
                "capability_id": "cap_parity_process",
                "provider_id": str(PROVIDER_ID),
                "profile": request.profile,
                "source_size": request.source.size,
            },
            artifacts=(
                ArtifactReference(
                    artifact_id=ArtifactId("art_parity_process"),
                    kind="processed-fixture",
                    media_type="application/json",
                    metadata={"capability_id": "cap_parity_process"},
                ),
            ),
            warnings=warnings_for_scenario(scenario),
        )


def descriptor(
    capability_id: str,
    name: str,
    input_contract: str,
    output_contract: str,
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=CapabilityId(capability_id),
        name=f"parity-{name}",
        description=f"Parity {name} capability",
        version=CapabilityVersion("0.1.0"),
        input_contract=input_contract,
        output_contract=output_contract,
        supported_media_types=("application/pdf",),
        resource_class="test",
        deterministic=True,
        supports_cancellation=True,
        supports_progress=True,
        provider_id=PROVIDER_ID,
        provider_version=ProviderVersion("0.1.0"),
    )


def error_to_result(error: Exception) -> ErrorResult:
    from eixo import EixoError

    if isinstance(error, EixoError):
        payload = error.to_payload()
        return ErrorResult(
            code=payload.code,
            message=payload.message,
            category=payload.category,
            retryable=payload.retryable,
            details=payload.public_context or payload.details,
        )
    return ErrorResult(
        code="internal.error",
        message=str(error),
        category=ErrorCategory.INTERNAL,
        retryable=True,
    )


__all__ = [
    "DOCUMENT_ID",
    "PROCESS_JOB_ID",
    "PROVIDER_ID",
    "error_to_result",
    "parity_engine",
]
