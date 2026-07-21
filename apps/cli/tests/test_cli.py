from __future__ import annotations

import asyncio
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from eixo import (
    DocumentEngine,
    InspectionRequest,
    InspectionResult,
    JobResult,
    JobStatus,
    ParseRequest,
    ParseResult,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
)
from eixo.core import (
    CapabilityId,
    CapabilityVersion,
    DocumentId,
    JobId,
    ProviderId,
    ProviderVersion,
    ResultStatus,
)
from eixo.plugins import CapabilityDescriptor, ExecutionContext, ProviderDescriptor
from eixo_cli.exit_codes import ExitCode
from eixo_cli.main import main

PDF_BYTES = b"%PDF-1.7\n"


def test_root_help_and_version() -> None:
    out = io.StringIO()

    assert main(["--help"], stdout=out, stderr=io.StringIO()) == 0
    assert "Eixo - Distributed Document Intelligence Engine" in out.getvalue()
    assert "inspect" in out.getvalue()

    version = io.StringIO()
    assert main(["--version"], stdout=version, stderr=io.StringIO()) == 0
    assert version.getvalue() == "eixo 0.1.0\n"


def test_command_help() -> None:
    for args in (
        ["inspect", "--help"],
        ["parse", "--help"],
        ["process", "--help"],
        ["jobs", "--help"],
        ["jobs", "status", "--help"],
        ["jobs", "result", "--help"],
    ):
        out = io.StringIO()
        assert main(args, stdout=out, stderr=io.StringIO()) == 0
        assert "usage:" in out.getvalue()


def test_inspect_console_json_and_output_file(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(PDF_BYTES)
    output = tmp_path / "inspection.json"

    console = io.StringIO()
    code = main(
        ["inspect", str(document)],
        engine_factory=engine_with_fake_capabilities,
        stdout=console,
        stderr=io.StringIO(),
    )
    assert code == 0
    assert "Status: success" in console.getvalue()

    json_out = io.StringIO()
    code = main(
        ["inspect", str(document), "--format", "json", "--pretty"],
        engine_factory=engine_with_fake_capabilities,
        stdout=json_out,
        stderr=io.StringIO(),
    )
    assert code == 0
    payload = json.loads(json_out.getvalue())
    assert payload["status"] == "success"
    assert payload["detected_media_type"] == "application/pdf"

    code = main(
        ["inspect", str(document), "--output", str(output)],
        engine_factory=engine_with_fake_capabilities,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    assert code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "success"


def test_output_does_not_overwrite_without_force(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(PDF_BYTES)
    output = tmp_path / "inspection.json"
    output.write_text("{}", encoding="utf-8")
    err = io.StringIO()

    code = main(
        ["inspect", str(document), "--output", str(output)],
        engine_factory=engine_with_fake_capabilities,
        stdout=io.StringIO(),
        stderr=err,
    )

    assert code == int(ExitCode.INVALID_ARGUMENTS)
    assert "Use --force" in err.getvalue()


def test_inspect_missing_file_and_debug(tmp_path: Path) -> None:
    err = io.StringIO()
    code = main(
        ["inspect", str(tmp_path / "missing.pdf"), "--debug"],
        engine_factory=engine_with_fake_capabilities,
        stdout=io.StringIO(),
        stderr=err,
    )

    assert code == int(ExitCode.SOURCE_NOT_FOUND)
    assert "nao foi possivel localizar" in err.getvalue()
    assert "Traceback" in err.getvalue()


def test_missing_capability_exit_code(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(PDF_BYTES)

    code = main(["parse", str(document)], stdout=io.StringIO(), stderr=io.StringIO())

    assert code == int(ExitCode.CAPABILITY_UNAVAILABLE)


def test_parse_and_process_json(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(PDF_BYTES)

    parse_out = io.StringIO()
    assert (
        main(
            ["parse", str(document), "--format", "json"],
            engine_factory=engine_with_fake_capabilities,
            stdout=parse_out,
            stderr=io.StringIO(),
        )
        == 0
    )
    assert json.loads(parse_out.getvalue())["document_id"] == "doc_fake"

    process_out = io.StringIO()
    assert (
        main(
            ["process", str(document), "--profile", "balanced", "--format", "json"],
            engine_factory=engine_with_fake_capabilities,
            stdout=process_out,
            stderr=io.StringIO(),
        )
        == 0
    )
    payload = json.loads(process_out.getvalue())
    assert payload["status"] == "completed"
    assert payload["data"] == {"ok": True}


def test_process_invalid_profile(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(PDF_BYTES)

    code = main(
        ["process", str(document), "--profile", "slow"],
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )

    assert code == int(ExitCode.INVALID_ARGUMENTS)


def test_process_no_wait_returns_job(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(PDF_BYTES)
    out = io.StringIO()

    code = main(
        ["process", str(document), "--no-wait", "--format", "json"],
        engine_factory=engine_with_fake_capabilities,
        stdout=out,
        stderr=io.StringIO(),
    )

    assert code == 0
    assert json.loads(out.getvalue())["status"] in {"queued", "running", "completed"}


def test_jobs_status_result_cancel_and_errors() -> None:
    engine = FakeJobEngine()

    status_out = io.StringIO()
    assert (
        main(
            ["jobs", "status", "job_ready", "--format", "json"],
            engine_factory=lambda: engine,
            stdout=status_out,
            stderr=io.StringIO(),
        )
        == 0
    )
    assert json.loads(status_out.getvalue())["status"] == "completed"

    result_out = io.StringIO()
    assert (
        main(
            ["jobs", "result", "job_ready", "--format", "json"],
            engine_factory=lambda: engine,
            stdout=result_out,
            stderr=io.StringIO(),
        )
        == 0
    )
    assert json.loads(result_out.getvalue())["data"] == {"ready": True}

    cancel_out = io.StringIO()
    assert (
        main(
            ["jobs", "cancel", "job_running"],
            engine_factory=lambda: engine,
            stdout=cancel_out,
            stderr=io.StringIO(),
        )
        == 0
    )
    assert "Status: cancelled" in cancel_out.getvalue()

    missing = main(
        ["jobs", "status", "job_missing"],
        engine_factory=lambda: engine,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    assert missing == int(ExitCode.JOB_NOT_FOUND)

    unavailable = main(
        ["jobs", "result", "job_running"],
        engine_factory=lambda: engine,
        stdout=io.StringIO(),
        stderr=io.StringIO(),
    )
    assert unavailable == int(ExitCode.PROCESSING_FAILED)


def test_cli_library_parity_with_fake_capability(tmp_path: Path) -> None:
    document = tmp_path / "sample.pdf"
    document.write_bytes(PDF_BYTES)

    async def library_flow() -> ProcessingResult:
        async with engine_with_fake_capabilities() as engine:
            request = ProcessingRequest(
                source=__import__("eixo").LocalPathSource(
                    path=document,
                    filename=document.name,
                    declared_media_type="application/pdf",
                    size=len(PDF_BYTES),
                )
            )
            return await engine.process(request)

    library_result = asyncio.run(library_flow())
    cli_out = io.StringIO()
    assert (
        main(
            ["process", str(document), "--format", "json"],
            engine_factory=engine_with_fake_capabilities,
            stdout=cli_out,
            stderr=io.StringIO(),
        )
        == 0
    )
    cli_result = json.loads(cli_out.getvalue())

    assert cli_result["status"] == library_result.status.value
    assert cli_result["data"] == library_result.data


def engine_with_fake_capabilities() -> DocumentEngine:
    provider = ProviderDescriptor(
        provider_id=ProviderId("prov_cli_fake"),
        name="cli-fake-provider",
        version=ProviderVersion("0.1.0"),
    )
    return DocumentEngine.local(
        providers=(provider,),
        capabilities=(
            InspectCapability(provider.provider_id),
            ParseCapability(provider.provider_id),
            ProcessCapability(provider.provider_id),
        ),
    )


@dataclass(frozen=True, slots=True)
class InspectCapability:
    provider_id: ProviderId

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return descriptor(
            "cap_cli_inspect",
            "cli-inspect",
            "InspectionRequest",
            "InspectionResult",
            self.provider_id,
        )

    async def execute(
        self,
        request: InspectionRequest,
        context: ExecutionContext,
    ) -> InspectionResult:
        return InspectionResult(
            document_id=DocumentId("doc_fake"),
            detected_format="pdf",
            declared_media_type=request.source.declared_media_type,
            detected_media_type=request.source.declared_media_type,
            size=request.source.size,
            status=ResultStatus.SUCCESS,
        )


@dataclass(frozen=True, slots=True)
class ParseCapability:
    provider_id: ProviderId

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return descriptor(
            "cap_cli_parse",
            "cli-parse",
            "ParseRequest",
            "ParseResult",
            self.provider_id,
        )

    async def execute(self, request: ParseRequest, context: ExecutionContext) -> ParseResult:
        return ParseResult(document_id=DocumentId("doc_fake"), status=ResultStatus.SUCCESS)


@dataclass(frozen=True, slots=True)
class ProcessCapability:
    provider_id: ProviderId

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return descriptor(
            "cap_cli_process",
            "cli-process",
            "ProcessingRequest",
            "ProcessingResult",
            self.provider_id,
        )

    async def execute(
        self,
        request: ProcessingRequest,
        context: ExecutionContext,
    ) -> ProcessingResult:
        return ProcessingResult(
            job_id=JobId("job_cli"),
            document_id=DocumentId("doc_fake"),
            status=ProcessingStatus.COMPLETED,
            data={"ok": True},
        )


def descriptor(
    capability_id: str,
    name: str,
    input_contract: str,
    output_contract: str,
    provider_id: ProviderId,
) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=CapabilityId(capability_id),
        name=name,
        description=name,
        version=CapabilityVersion("0.1.0"),
        input_contract=input_contract,
        output_contract=output_contract,
        supported_formats=("pdf",),
        supported_media_types=("application/pdf",),
        provider_id=provider_id,
    )


class FakeJobEngine:
    async def __aenter__(self) -> "FakeJobEngine":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def get_job_status(self, job_id: str) -> JobResult:
        if job_id == "job_missing":
            from eixo import JobNotFoundError

            raise JobNotFoundError("Job not found")
        status = JobStatus.COMPLETED if job_id == "job_ready" else JobStatus.RUNNING
        return JobResult(job_id=JobId(job_id), status=status, progress=1.0)

    async def get_job_result(self, job_id: str) -> ProcessingResult:
        if job_id != "job_ready":
            from eixo import InvalidStateTransitionError

            raise InvalidStateTransitionError("Job result is not available yet")
        return ProcessingResult(
            job_id=JobId(job_id),
            document_id=DocumentId("doc_fake"),
            status=ProcessingStatus.COMPLETED,
            data={"ready": True},
        )

    async def cancel_job(self, job_id: str) -> JobResult:
        return JobResult(job_id=JobId(job_id), status=JobStatus.CANCELLED)
