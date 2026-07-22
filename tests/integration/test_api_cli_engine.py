from __future__ import annotations

from fastapi.testclient import TestClient

from eixo.engine import DocumentEngine
from eixo.engine.pdf_public import (
    PDF_INSPECT_CAPABILITY_ID,
    PDF_PARSE_CAPABILITY_ID,
    PDF_PROCESS_CAPABILITY_ID,
)
from eixo.sdk import DocumentEngine as SdkDocumentEngine
from eixo_api import create_app
from eixo_cli.main import main


def test_api_foundation_initializes() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_runtime_lifecycle_uses_single_instance() -> None:
    async def run() -> None:
        app = create_app()
        with TestClient(app) as client:
            assert client.get("/ready").status_code == 200
            engine = app.state.eixo.engine
        assert app.state.eixo.engine is engine

    import asyncio

    asyncio.run(run())


def test_cli_foundation_initializes(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--version"]) == 0
    output = capsys.readouterr().out
    assert "eixo 0.1.0" in output


def test_cli_runtime_info(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["runtime", "info"]) == 0
    output = capsys.readouterr().out
    assert "max_concurrent_tasks=" in output


def test_sdk_exposes_engine_without_duplicate_logic() -> None:
    assert SdkDocumentEngine is DocumentEngine
    capability_ids = {
        capability.capability_id
        for capability in DocumentEngine.local().registry.list_capabilities()
    }
    assert capability_ids == {
        PDF_INSPECT_CAPABILITY_ID,
        PDF_PARSE_CAPABILITY_ID,
        PDF_PROCESS_CAPABILITY_ID,
    }


def test_document_engine_local_owns_runtime_lifecycle() -> None:
    async def run() -> None:
        async with DocumentEngine.local(max_concurrent_tasks=2, default_timeout=1) as engine:
            assert engine.runtime.config.max_concurrent_tasks == 2
        await engine.shutdown()

    import asyncio

    asyncio.run(run())
