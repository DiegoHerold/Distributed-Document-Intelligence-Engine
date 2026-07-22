from __future__ import annotations

import importlib
import time
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

import eixo
from eixo import (
    CapabilityNotFoundError,
    DocumentEngine,
    ErrorResult,
    InspectionRequest,
    InspectionResult,
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
    ExecutionMetadata,
    JobId,
    ProviderId,
    ProviderVersion,
    ResultStatus,
)
from eixo.plugins import CapabilityDescriptor, ExecutionContext, ProviderDescriptor
from eixo_api import ApiConfig, create_app

PDF_BYTES = b"%PDF-1.7\n"


def test_application_factory_import_and_openapi() -> None:
    app = create_app(config=ApiConfig(docs_enabled=True))

    assert app.title == "Eixo API"
    assert app.state.eixo.engine is None
    with TestClient(app) as client:
        openapi = client.get("/openapi.json").json()
        paths = openapi["paths"]

    assert "/health" in paths
    assert "/ready" in paths
    assert "/v1/documents:inspect" in paths
    assert "/v1/documents:parse" in paths
    assert "/v1/extractions" in paths


def test_health_and_ready_lifecycle() -> None:
    app = create_app()
    assert TestClient(app).get("/ready").status_code == 503

    with TestClient(app) as client:
        assert client.get("/health").json() == {
            "status": "ok",
            "service": "eixo-api",
            "version": "0.1.0",
        }
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["checks"]["engine"] == "ok"
        assert app.state.eixo.engine is not None


def test_injected_engine_is_started_once_and_shutdown() -> None:
    engine = DocumentEngine.local()
    app = create_app(engine=engine)

    with TestClient(app) as client:
        assert client.get("/ready").status_code == 200
        assert app.state.eixo.engine is engine
        assert engine.state.value == "running"
    assert engine.state.value == "stopped"


def test_startup_failure_blocks_readiness() -> None:
    class BrokenEngine:
        state = "failed"
        runtime = None
        registry = None
        get_job_status_use_case = None
        get_job_result_use_case = None

        async def start(self) -> None:
            raise RuntimeError("boom")

        async def shutdown(self) -> None:
            return None

    app = create_app(engine=BrokenEngine())  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass
    assert app.state.eixo.startup_error == "RuntimeError"


def test_inspect_upload_calls_engine_and_returns_result() -> None:
    engine = engine_with_fake_capabilities()
    with TestClient(create_app(engine=engine)) as client:
        response = client.post(
            "/v1/documents:inspect",
            files={"file": ("sample.pdf", PDF_BYTES, "application/pdf")},
            data={"options": '{"mode":"quick"}'},
            headers={"X-Correlation-ID": "corr_test"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["detected_media_type"] == "application/pdf"
    assert response.headers["X-Correlation-ID"] == "corr_test"


def test_parse_upload_options_and_result() -> None:
    engine = engine_with_fake_capabilities()
    with TestClient(create_app(engine=engine)) as client:
        response = client.post(
            "/v1/documents:parse",
            files={"file": ("sample.pdf", PDF_BYTES, "application/pdf")},
            data={"options": '{"tables":true}', "requested_capability": "native"},
        )

    assert response.status_code == 200
    assert response.json()["artifacts"] == []


def test_missing_pdf_provider_returns_structured_error(  # type: ignore[no-untyped-def]
    monkeypatch,
) -> None:
    real_import = importlib.import_module

    def fake_import(name: str, package: str | None = None):
        if name == "fitz":
            raise ModuleNotFoundError(name)
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    with TestClient(create_app(engine=DocumentEngine.local())) as client:
        response = client.post(
            "/v1/documents:inspect",
            files={"file": ("sample.pdf", PDF_BYTES, "application/pdf")},
            headers={"X-Correlation-ID": "corr_missing"},
        )

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "pdf.provider_unavailable"
    assert payload["category"] == "configuration"
    assert payload["correlation_id"] == "corr_missing"
    assert "traceback" not in response.text.lower()


def test_upload_validation_errors() -> None:
    config = ApiConfig(max_upload_size=3)
    with TestClient(create_app(config=config, engine=engine_with_fake_capabilities())) as client:
        too_large = client.post(
            "/v1/documents:inspect",
            files={"file": ("sample.pdf", b"abcd", "application/pdf")},
        )
        empty = client.post(
            "/v1/documents:inspect",
            files={"file": ("sample.pdf", b"", "application/pdf")},
        )

    assert too_large.status_code == 413
    assert empty.status_code == 422


def test_extraction_job_lifecycle_result_and_completed_cancel_conflict() -> None:
    engine = engine_with_fake_capabilities()
    with TestClient(create_app(engine=engine)) as client:
        submitted = client.post(
            "/v1/extractions",
            files={"file": ("sample.pdf", PDF_BYTES, "application/pdf")},
        )
        assert submitted.status_code == 202
        assert submitted.headers["Location"].startswith("/v1/extractions/job_")
        job_id = submitted.json()["job_id"]

        status_payload = wait_for_status(client, job_id, "completed")
        assert status_payload["status"] == "completed"
        result = client.get(f"/v1/extractions/{job_id}/result")
        assert result.status_code == 200
        assert result.json()["data"] == {"ok": True}
        cancel = client.post(f"/v1/extractions/{job_id}/cancel")

    assert cancel.status_code == 409


def test_extraction_result_before_completion_and_cancel_idempotency() -> None:
    engine = engine_with_fake_capabilities(process_delay=0.2)
    with TestClient(create_app(engine=engine)) as client:
        submitted = client.post(
            "/v1/extractions",
            files={"file": ("sample.pdf", PDF_BYTES, "application/pdf")},
        )
        job_id = submitted.json()["job_id"]
        early_result = client.get(f"/v1/extractions/{job_id}/result")
        first_cancel = client.post(f"/v1/extractions/{job_id}/cancel")
        second_cancel = client.post(f"/v1/extractions/{job_id}/cancel")

    assert early_result.status_code == 409
    assert first_cancel.status_code == 202
    assert second_cancel.status_code == 202
    assert second_cancel.json()["status"] == "cancelled"


def test_job_not_found() -> None:
    with TestClient(create_app(engine=engine_with_fake_capabilities())) as client:
        response = client.get("/v1/extractions/job_missing")

    assert response.status_code == 404
    assert response.json()["code"] == "job.not_found"


def test_correlation_id_generated_and_isolated() -> None:
    with TestClient(create_app(engine=engine_with_fake_capabilities())) as client:
        one = client.get("/health")
        two = client.get("/health")

    assert one.headers["X-Correlation-ID"].startswith("corr_")
    assert two.headers["X-Correlation-ID"].startswith("corr_")
    assert one.headers["X-Correlation-ID"] != two.headers["X-Correlation-ID"]


def test_parallel_submissions_are_independent() -> None:
    with TestClient(create_app(engine=engine_with_fake_capabilities())) as client:
        responses = [
            client.post(
                "/v1/extractions",
                files={"file": (f"sample-{index}.pdf", PDF_BYTES, "application/pdf")},
            )
            for index in range(3)
        ]

    job_ids = {response.json()["job_id"] for response in responses}
    assert all(response.status_code == 202 for response in responses)
    assert len(job_ids) == 3


def test_api_and_library_parity_with_same_capability() -> None:
    source = eixo.BytesSource(
        content=PDF_BYTES,
        filename="sample.pdf",
        declared_media_type="application/pdf",
        size=len(PDF_BYTES),
    )

    async def library_flow() -> ProcessingResult:
        async with engine_with_fake_capabilities() as engine:
            return await engine.process(ProcessingRequest(source=source))

    import asyncio

    library_result = asyncio.run(library_flow())
    with TestClient(create_app(engine=engine_with_fake_capabilities())) as client:
        submitted = client.post(
            "/v1/extractions",
            files={"file": ("sample.pdf", PDF_BYTES, "application/pdf")},
        )
        job_id = submitted.json()["job_id"]
        wait_for_status(client, job_id, "completed")
        api_result = client.get(f"/v1/extractions/{job_id}/result").json()

    assert eixo.ProcessingRequest is ProcessingRequest
    assert api_result["status"] == library_result.status.value
    assert api_result["data"] == library_result.data
    assert api_result["errors"] == list(library_result.errors)


def wait_for_status(client: TestClient, job_id: str, status: str) -> dict[str, Any]:
    for _ in range(50):
        payload = client.get(f"/v1/extractions/{job_id}").json()
        if payload["status"] == status:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not reach {status}")


def engine_with_fake_capabilities(*, process_delay: float = 0.0) -> DocumentEngine:
    provider = ProviderDescriptor(
        provider_id=ProviderId("prov_fake"),
        name="fake-provider",
        version=ProviderVersion("0.1.0"),
    )
    return DocumentEngine.local(
        providers=(provider,),
        capabilities=(
            InspectCapability(provider.provider_id),
            ParseCapability(provider.provider_id),
            ProcessCapability(provider.provider_id, delay=process_delay),
        ),
    )


@dataclass(frozen=True, slots=True)
class InspectCapability:
    provider_id: ProviderId

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return descriptor(
            "cap_fake_inspect",
            "fake-inspect",
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
            metadata={"filename": request.source.filename},
            execution_metadata=ExecutionMetadata.requested(context.correlation_id),
        )


@dataclass(frozen=True, slots=True)
class ParseCapability:
    provider_id: ProviderId

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return descriptor(
            "cap_fake_parse",
            "fake-parse",
            "ParseRequest",
            "ParseResult",
            self.provider_id,
        )

    async def execute(self, request: ParseRequest, context: ExecutionContext) -> ParseResult:
        return ParseResult(document_id=DocumentId("doc_fake"), status=ResultStatus.SUCCESS)


@dataclass(frozen=True, slots=True)
class ProcessCapability:
    provider_id: ProviderId
    delay: float = 0.0

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return descriptor(
            "cap_fake_process",
            "fake-process",
            "ProcessingRequest",
            "ProcessingResult",
            self.provider_id,
        )

    async def execute(
        self,
        request: ProcessingRequest,
        context: ExecutionContext,
    ) -> ProcessingResult:
        if self.delay:
            import asyncio

            await asyncio.sleep(self.delay)
        return ProcessingResult(
            job_id=JobId.new(),
            document_id=DocumentId("doc_fake"),
            status=ProcessingStatus.COMPLETED,
            data={"ok": True},
            execution_metadata=ExecutionMetadata.requested(context.correlation_id),
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
