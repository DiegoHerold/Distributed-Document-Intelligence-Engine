from __future__ import annotations

import asyncio
import io
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import eixo
from eixo import (
    DocumentEngine,
    IngestionSecurityPolicy,
    InspectionRequest,
    JobId,
    JobStatus,
    ParseRequest,
    ProcessingRequest,
)
from eixo.application import JobTransitionPolicy, new_job_record
from eixo_api import create_app
from eixo_cli.main import main as cli_main
from tests.parity.fake_capabilities import error_to_result, parity_engine


@dataclass(frozen=True, slots=True)
class ParityFixture:
    path: Path
    content: bytes
    media_type: str = "application/pdf"
    profile: str = "balanced"

    def source(self) -> eixo.LocalPathSource:
        return eixo.LocalPathSource(
            path=self.path,
            filename=self.path.name,
            declared_media_type=self.media_type,
            size=len(self.content),
        )


class LibraryParityDriver:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        security: IngestionSecurityPolicy | None = None,
    ) -> None:
        self.timeout = timeout
        self.security = security

    async def inspect(self, fixture: ParityFixture) -> Any:
        try:
            async with parity_engine(
                timeout=self.timeout,
                security=self.security,
            ) as engine:
                return await engine.inspect(InspectionRequest(source=fixture.source()))
        except Exception as exc:
            return error_to_result(exc)

    async def parse(self, fixture: ParityFixture) -> Any:
        try:
            async with parity_engine(
                timeout=self.timeout,
                security=self.security,
            ) as engine:
                return await engine.parse(ParseRequest(source=fixture.source()))
        except Exception as exc:
            return error_to_result(exc)

    async def process(self, fixture: ParityFixture) -> Any:
        try:
            async with parity_engine(
                timeout=self.timeout,
                security=self.security,
            ) as engine:
                return await engine.process(
                    ProcessingRequest(
                        source=fixture.source(),
                        profile=fixture.profile,
                    )
                )
        except Exception as exc:
            return error_to_result(exc)

    async def submit_status_result(self, fixture: ParityFixture) -> dict[str, Any]:
        async with parity_engine(
            timeout=self.timeout,
            security=self.security,
        ) as engine:
            job = await engine.submit(
                ProcessingRequest(source=fixture.source(), profile=fixture.profile)
            )
            status = await wait_library_job(engine, str(job.job_id))
            result = await engine.get_job_result(job.job_id)
            return {"job": job, "status": status, "result": result}

    async def submit_job(self, fixture: ParityFixture) -> Any:
        async with parity_engine(
            timeout=self.timeout,
            security=self.security,
        ) as engine:
            return await engine.submit(
                ProcessingRequest(source=fixture.source(), profile=fixture.profile)
            )

    async def cancel(self, fixture: ParityFixture) -> Any:
        async with parity_engine(
            timeout=self.timeout,
            security=self.security,
        ) as engine:
            job = await engine.submit(
                ProcessingRequest(source=fixture.source(), profile=fixture.profile)
            )
            return await engine.cancel_job(job.job_id)


class APIParityDriver:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        security: IngestionSecurityPolicy | None = None,
    ) -> None:
        self.timeout = timeout
        self.security = security

    async def inspect(self, fixture: ParityFixture) -> Any:
        with TestClient(
            create_app(engine=parity_engine(timeout=self.timeout, security=self.security))
        ) as client:
            response = client.post(
                "/v1/documents:inspect",
                files={"file": (fixture.path.name, fixture.content, fixture.media_type)},
            )
            return response.json()

    async def parse(self, fixture: ParityFixture) -> Any:
        with TestClient(
            create_app(engine=parity_engine(timeout=self.timeout, security=self.security))
        ) as client:
            response = client.post(
                "/v1/documents:parse",
                files={"file": (fixture.path.name, fixture.content, fixture.media_type)},
            )
            return response.json()

    async def process(self, fixture: ParityFixture) -> Any:
        with TestClient(
            create_app(engine=parity_engine(timeout=self.timeout, security=self.security))
        ) as client:
            response = client.post(
                "/v1/extractions",
                files={"file": (fixture.path.name, fixture.content, fixture.media_type)},
                data={"profile": fixture.profile},
            )
            job_id = response.json()["job_id"]
            status = wait_api_job(client, job_id)
            if status["status"] == "failed":
                return status["error"]
            result = client.get(f"/v1/extractions/{job_id}/result")
            return result.json()

    async def submit_status_result(self, fixture: ParityFixture) -> dict[str, Any]:
        with TestClient(
            create_app(engine=parity_engine(timeout=self.timeout, security=self.security))
        ) as client:
            response = client.post(
                "/v1/extractions",
                files={"file": (fixture.path.name, fixture.content, fixture.media_type)},
                data={"profile": fixture.profile},
            )
            job = response.json()
            status = wait_api_job(client, job["job_id"])
            result = client.get(f"/v1/extractions/{job['job_id']}/result").json()
            return {"job": job, "status": status, "result": result}

    async def submit_job(self, fixture: ParityFixture) -> Any:
        with TestClient(
            create_app(engine=parity_engine(timeout=self.timeout, security=self.security))
        ) as client:
            response = client.post(
                "/v1/extractions",
                files={"file": (fixture.path.name, fixture.content, fixture.media_type)},
                data={"profile": fixture.profile},
            )
            return response.json()

    async def cancel(self, fixture: ParityFixture) -> Any:
        with TestClient(
            create_app(engine=parity_engine(timeout=self.timeout, security=self.security))
        ) as client:
            response = client.post(
                "/v1/extractions",
                files={"file": (fixture.path.name, fixture.content, fixture.media_type)},
                data={"profile": fixture.profile},
            )
            job_id = response.json()["job_id"]
            return client.post(f"/v1/extractions/{job_id}/cancel").json()


class CLIParityDriver:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        security: IngestionSecurityPolicy | None = None,
    ) -> None:
        self.timeout = timeout
        self.security = security

    async def inspect(self, fixture: ParityFixture) -> Any:
        return await asyncio.to_thread(
            run_cli_json,
            ["inspect", str(fixture.path), "--format", "json"],
            timeout=self.timeout,
            security=self.security,
        )

    async def parse(self, fixture: ParityFixture) -> Any:
        return await asyncio.to_thread(
            run_cli_json,
            ["parse", str(fixture.path), "--format", "json"],
            timeout=self.timeout,
            security=self.security,
        )

    async def process(self, fixture: ParityFixture) -> Any:
        return await asyncio.to_thread(
            run_cli_json,
            [
                "process",
                str(fixture.path),
                "--profile",
                fixture.profile,
                "--format",
                "json",
            ],
            timeout=self.timeout,
            security=self.security,
        )

    async def submit_status_result(self, fixture: ParityFixture) -> dict[str, Any]:
        return await asyncio.to_thread(self._submit_status_result_sync, fixture)

    async def submit_job(self, fixture: ParityFixture) -> Any:
        return await asyncio.to_thread(
            run_cli_json,
            [
                "process",
                str(fixture.path),
                "--profile",
                fixture.profile,
                "--no-wait",
                "--format",
                "json",
            ],
            timeout=self.timeout,
            security=self.security,
        )

    def _submit_status_result_sync(self, fixture: ParityFixture) -> dict[str, Any]:
        persistent = PersistentCliEngine(
            parity_engine(timeout=self.timeout, security=self.security)
        )
        try:
            job_id = asyncio.run(seed_completed_job(persistent, fixture))
            status = run_cli_json(
                ["jobs", "status", job_id, "--format", "json"],
                timeout=self.timeout,
                engine_factory=lambda: persistent,
            )
            result = run_cli_json(
                ["jobs", "result", job_id, "--format", "json"],
                timeout=self.timeout,
                engine_factory=lambda: persistent,
            )
            return {"status": status, "result": result}
        finally:
            asyncio.run(persistent.shutdown())

    async def cancel(self, fixture: ParityFixture) -> Any:
        return await asyncio.to_thread(self._cancel_sync, fixture)

    def _cancel_sync(self, fixture: ParityFixture) -> Any:
        persistent = PersistentCliEngine(
            parity_engine(timeout=self.timeout, security=self.security)
        )
        try:
            job_id = asyncio.run(seed_queued_job(persistent, fixture))
            return run_cli_json(
                ["jobs", "cancel", job_id, "--format", "json"],
                timeout=self.timeout,
                engine_factory=lambda: persistent,
            )
        finally:
            asyncio.run(persistent.shutdown())


def run_cli_json(
    args: list[str],
    *,
    timeout: float,
    security: IngestionSecurityPolicy | None = None,
    engine_factory=None,
) -> Any:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = cli_main(
        args,
        engine_factory=engine_factory
        or (lambda: parity_engine(timeout=timeout, security=security)),
        stdout=stdout,
        stderr=stderr,
    )
    stream = stdout.getvalue() if code == 0 else stderr.getvalue()
    try:
        return json.loads(stream)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"CLI did not return JSON. code={code}, stdout={stdout.getvalue()!r}, "
            f"stderr={stderr.getvalue()!r}"
        ) from exc


async def wait_library_job(engine: DocumentEngine, job_id: str) -> Any:
    for _ in range(50):
        status = await engine.get_job_status(job_id)
        if status.status.value in {"completed", "failed", "cancelled"}:
            return status
        await asyncio.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish")


def wait_api_job(client: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(50):
        status = client.get(f"/v1/extractions/{job_id}").json()
        if status["status"] in {"completed", "failed", "cancelled"}:
            return status
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish")


def wait_cli_job(engine, job_id: str) -> dict[str, Any]:
    for _ in range(50):
        status = run_cli_json(
            ["jobs", "status", job_id, "--format", "json"],
            timeout=30.0,
            engine_factory=lambda: engine,
        )
        if status["status"] in {"completed", "failed", "cancelled"}:
            return status
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish")


async def seed_completed_job(engine, fixture: ParityFixture) -> str:
    await engine.__aenter__()
    job = await engine.submit(
        ProcessingRequest(source=fixture.source(), profile=fixture.profile)
    )
    await wait_library_job(engine, str(job.job_id))
    return str(job.job_id)


async def seed_queued_job(engine, fixture: ParityFixture) -> str:
    await engine.__aenter__()
    job_id = JobId.new()
    request = ProcessingRequest(source=fixture.source(), profile=fixture.profile)
    policy = JobTransitionPolicy.default()
    created = new_job_record(job_id, request, operation="process")
    queued = policy.transition(created, to_status=JobStatus.QUEUED, stage="queued")
    requested = policy.transition(
        queued,
        to_status=JobStatus.CANCEL_REQUESTED,
        stage="cancelling",
    )
    job_service = engine.submit_processing_job.executor
    await job_service.store.create(requested)
    return str(job_id)


class PersistentCliEngine:
    def __init__(self, engine: DocumentEngine) -> None:
        self._engine = engine

    async def __aenter__(self):
        await self._engine.start()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def __getattr__(self, name: str):
        return getattr(self._engine, name)

    async def shutdown(self) -> None:
        await self._engine.shutdown()


__all__ = [
    "APIParityDriver",
    "CLIParityDriver",
    "LibraryParityDriver",
    "ParityFixture",
]
