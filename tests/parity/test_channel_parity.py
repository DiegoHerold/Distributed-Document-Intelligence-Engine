from __future__ import annotations

import json

from fastapi.testclient import TestClient

from eixo import (
    DocumentEngine,
    IngestionLimits,
    IngestionSecurityPolicy,
    InspectionRequest,
    ProcessingRequest,
)
from eixo.core.serialization import to_jsonable
from eixo_api import create_app
from eixo_cli.main import main as cli_main
from tests.parity.comparator import ChannelResult, assert_semantically_equal
from tests.parity.drivers import APIParityDriver, CLIParityDriver, LibraryParityDriver
from tests.parity.drivers import ParityFixture
from tests.parity.fake_capabilities import error_to_result, parity_engine
from tests.parity.normalization import normalize_for_parity


def write_fixture(tmp_path, name: str, content: bytes = b"%PDF-1.7\n") -> ParityFixture:
    path = tmp_path / name
    path.write_bytes(content)
    return ParityFixture(path=path, content=content)


async def channel_results(
    operation: str,
    fixture: ParityFixture,
    *,
    timeout: float = 30.0,
    security: IngestionSecurityPolicy | None = None,
):
    drivers = (
        ("library", LibraryParityDriver(timeout=timeout, security=security)),
        ("api", APIParityDriver(timeout=timeout, security=security)),
        ("cli", CLIParityDriver(timeout=timeout, security=security)),
    )
    return [
        ChannelResult(name, await getattr(driver, operation)(fixture))
        for name, driver in drivers
    ]


def test_inspect_success_parity(tmp_path) -> None:
    async def run() -> None:
        results = await channel_results("inspect", write_fixture(tmp_path, "success.pdf"))
        assert_semantically_equal(*results)

    import asyncio

    asyncio.run(run())


def test_parse_success_parity(tmp_path) -> None:
    async def run() -> None:
        results = await channel_results("parse", write_fixture(tmp_path, "success.pdf"))
        assert_semantically_equal(*results)

    import asyncio

    asyncio.run(run())


def test_process_success_parity(tmp_path) -> None:
    async def run() -> None:
        results = await channel_results("process", write_fixture(tmp_path, "success.pdf"))
        assert_semantically_equal(*results)

    import asyncio

    asyncio.run(run())


def test_warning_parity(tmp_path) -> None:
    async def run() -> None:
        results = await channel_results("process", write_fixture(tmp_path, "warning.pdf"))
        assert_semantically_equal(*results)
        normalized = normalize_for_parity(results[0].value)
        assert normalized["warnings"][0]["code"] == "parity.warning"

    import asyncio

    asyncio.run(run())


def test_invalid_request_parity(tmp_path) -> None:
    async def run() -> None:
        results = await channel_results("inspect", write_fixture(tmp_path, "empty.pdf", b""))
        assert_semantically_equal(*results)
        assert normalize_for_parity(results[0].value)["code"] == "empty_file"

    import asyncio

    asyncio.run(run())


def test_unsupported_format_security_parity(tmp_path) -> None:
    async def run() -> None:
        results = await channel_results(
            "inspect",
            write_fixture(tmp_path, "fake.pdf", b"MZ executable"),
        )
        assert_semantically_equal(*results)
        assert normalize_for_parity(results[0].value)["code"] == "unsupported_format"

    import asyncio

    asyncio.run(run())


def test_file_too_large_security_parity(tmp_path) -> None:
    async def run() -> None:
        security = IngestionSecurityPolicy(
            limits=IngestionLimits(max_file_size_bytes=8)
        )
        results = await channel_results(
            "inspect",
            write_fixture(tmp_path, "too-large.pdf"),
            security=security,
        )
        assert_semantically_equal(*results)
        assert normalize_for_parity(results[0].value)["code"] == "file_too_large"

    import asyncio

    asyncio.run(run())


def test_capability_not_found_parity(tmp_path) -> None:
    fixture = write_fixture(tmp_path, "missing-capability.pdf")

    async def library() -> object:
        try:
            async with DocumentEngine.local() as engine:
                return await engine.inspect(InspectionRequest(source=fixture.source()))
        except Exception as exc:
            return error_to_result(exc)

    with TestClient(create_app(engine=DocumentEngine.local())) as client:
        api = client.post(
            "/v1/documents:inspect",
            files={"file": (fixture.path.name, fixture.content, fixture.media_type)},
        ).json()

    import io
    import asyncio

    stdout = io.StringIO()
    stderr = io.StringIO()
    cli_main(
        ["inspect", str(fixture.path), "--format", "json"],
        engine_factory=DocumentEngine.local,
        stdout=stdout,
        stderr=stderr,
    )
    cli = json.loads(stderr.getvalue())

    assert_semantically_equal(
        ChannelResult("library", asyncio.run(library())),
        ChannelResult("api", api),
        ChannelResult("cli", cli),
    )


def test_execution_failure_parity(tmp_path) -> None:
    async def run() -> None:
        results = await channel_results("process", write_fixture(tmp_path, "failure.pdf"))
        assert_semantically_equal(*results)
        assert normalize_for_parity(results[0].value)["code"] == "execution.error"

    import asyncio

    asyncio.run(run())


def test_timeout_parity(tmp_path) -> None:
    async def run() -> None:
        results = await channel_results(
            "inspect",
            write_fixture(tmp_path, "timeout.pdf"),
            timeout=0.01,
        )
        assert_semantically_equal(*results)
        assert normalize_for_parity(results[0].value)["code"] == "execution.timeout"

    import asyncio

    asyncio.run(run())


def test_cancelled_parity(tmp_path) -> None:
    async def run() -> None:
        fixture = write_fixture(tmp_path, "timeout.pdf")
        results = [
            ChannelResult(
                "library",
                {"cancel": await LibraryParityDriver().cancel(fixture)},
            ),
            ChannelResult("api", {"cancel": await APIParityDriver().cancel(fixture)}),
            ChannelResult("cli", {"cancel": await CLIParityDriver().cancel(fixture)}),
        ]
        assert_semantically_equal(*results)

    import asyncio

    asyncio.run(run())


def test_job_status_result_parity(tmp_path) -> None:
    async def run() -> None:
        fixture = write_fixture(tmp_path, "success.pdf")
        full_results = [
            ChannelResult(
                "library",
                await LibraryParityDriver().submit_status_result(fixture),
            ),
            ChannelResult("api", await APIParityDriver().submit_status_result(fixture)),
            ChannelResult("cli", await CLIParityDriver().submit_status_result(fixture)),
        ]
        comparable = [
            ChannelResult(
                result.channel,
                {
                    "status": result.value["status"],
                    "result": result.value["result"],
                },
            )
            for result in full_results
        ]
        assert_semantically_equal(*comparable)

    import asyncio

    asyncio.run(run())


def test_submit_job_parity(tmp_path) -> None:
    async def run() -> None:
        fixture = write_fixture(tmp_path, "success.pdf")
        results = [
            ChannelResult("library", {"job": await LibraryParityDriver().submit_job(fixture)}),
            ChannelResult("api", {"job": await APIParityDriver().submit_job(fixture)}),
            ChannelResult("cli", {"job": await CLIParityDriver().submit_job(fixture)}),
        ]
        assert_semantically_equal(*results)

    import asyncio

    asyncio.run(run())


def test_default_configuration_parity(tmp_path) -> None:
    fixture = write_fixture(tmp_path, "success.pdf")

    async def library() -> object:
        async with parity_engine() as engine:
            return await engine.process(ProcessingRequest(source=fixture.source()))

    with TestClient(create_app(engine=parity_engine())) as client:
        response = client.post(
            "/v1/extractions",
            files={"file": (fixture.path.name, fixture.content, fixture.media_type)},
        )
        job_id = response.json()["job_id"]
        for _ in range(50):
            status = client.get(f"/v1/extractions/{job_id}").json()
            if status["status"] == "completed":
                break
        api = client.get(f"/v1/extractions/{job_id}/result").json()

    import asyncio
    import io

    stdout = io.StringIO()
    cli_main(
        ["process", str(fixture.path), "--format", "json"],
        engine_factory=parity_engine,
        stdout=stdout,
        stderr=io.StringIO(),
    )
    cli = json.loads(stdout.getvalue())

    assert_semantically_equal(
        ChannelResult("library", asyncio.run(library())),
        ChannelResult("api", api),
        ChannelResult("cli", cli),
    )
    assert cli["data"]["profile"] == "balanced"


def test_serialization_parity(tmp_path) -> None:
    async def run() -> None:
        results = await channel_results("process", write_fixture(tmp_path, "success.pdf"))
        normalized = [normalize_for_parity(result.value) for result in results]
        for item in normalized:
            encoded = json.dumps(item)
            assert "b'parity'" not in encoded
            assert item["status"] == "completed"
            assert item["contract_version"] == "1.0.0"
        assert_semantically_equal(*results)

    import asyncio

    asyncio.run(run())


def test_isolated_execution_parity(tmp_path) -> None:
    async def run() -> None:
        first = await channel_results("process", write_fixture(tmp_path, "first.pdf"))
        second = await channel_results("process", write_fixture(tmp_path, "second.pdf"))
        assert_semantically_equal(*first)
        assert_semantically_equal(*second)
        assert to_jsonable(first[0].value)["data"] == to_jsonable(second[0].value)["data"]

    import asyncio

    asyncio.run(run())
