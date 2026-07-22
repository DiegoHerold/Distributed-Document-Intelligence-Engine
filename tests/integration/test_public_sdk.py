from __future__ import annotations

import asyncio
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

import eixo
from eixo import (
    BytesSource,
    CapabilityNotFoundError,
    ConfigurationError,
    DocumentEngine,
    EixoError,
    ExecutionCancelledError,
    ExecutionTimeoutError,
    InspectionRequest,
    JobResult,
    LocalEngineConfig,
    LocalPathSource,
    LocalRuntimeConfig,
    ParseRequest,
    PDFProviderUnavailableError,
    ProcessingRequest,
    ProcessingResult,
    ValidationError,
    __version__,
)
from eixo_api.errors import ErrorResult as ApiErrorResult

ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path(sys.executable)


def test_public_import_surface_and_all() -> None:
    expected = {
        "__version__",
        "BytesSource",
        "CapabilityNotFoundError",
        "DocumentEngine",
        "EixoError",
        "ErrorResult",
        "InspectionRequest",
        "InspectionResult",
        "JobResult",
        "LocalEngineConfig",
        "LocalPathSource",
        "LocalRuntimeConfig",
        "ParseRequest",
        "ParseResult",
        "ProcessingRequest",
        "ProcessingResult",
    }

    assert expected.issubset(set(eixo.__all__))
    assert __version__ == "0.1.0"
    assert DocumentEngine.local().state.value == "created"


def test_public_models_and_errors_are_reexports() -> None:
    assert ProcessingRequest.json_schema()["title"] == "ProcessingRequest"
    assert ProcessingResult.json_schema()["title"] == "ProcessingResult"
    assert ApiErrorResult is eixo.ErrorResult
    assert issubclass(CapabilityNotFoundError, EixoError)
    assert issubclass(ConfigurationError, EixoError)
    assert issubclass(ValidationError, EixoError)
    assert issubclass(ExecutionTimeoutError, EixoError)
    assert issubclass(ExecutionCancelledError, EixoError)
    assert JobResult.__name__ == "JobResult"


def test_public_configuration_defaults_validation_and_immutability() -> None:
    runtime = LocalRuntimeConfig(max_concurrent_tasks=2, default_timeout=5)
    config = LocalEngineConfig(runtime=runtime, auto_start=False)

    assert config.runtime.max_concurrent_tasks == 2
    with pytest.raises(Exception):
        config.auto_start = True  # type: ignore[misc]
    with pytest.raises(ValueError):
        LocalRuntimeConfig(max_concurrent_tasks=0)


def test_public_lifecycle_and_capability_absent() -> None:
    async def run() -> None:
        content = b"%PDF-1.7\n"
        source = BytesSource(
            content=content,
            size=len(content),
            filename="x.pdf",
            declared_media_type="application/pdf",
        )
        async with DocumentEngine.local() as engine:
            with pytest.raises(PDFProviderUnavailableError):
                await engine.inspect(InspectionRequest(source=source))

    asyncio.run(run())


def test_examples_execute_with_workspace_imports() -> None:
    examples = [
        "basic_local_engine.py",
        "inspect_document.py",
        "process_document.py",
        "submit_job.py",
        "custom_capability.py",
    ]
    env = _env_with_workspace_paths()
    for example in examples:
        result = subprocess.run(
            [str(PYTHON), str(ROOT / "examples/python-library" / example)],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


def test_sdk_build_wheel_sdist_and_clean_install(tmp_path: Path) -> None:
    subprocess.run(
        [str(PYTHON), "-m", "tools.build_sdk", "--clean"],
        cwd=ROOT,
        check=True,
    )
    dist = ROOT / "dist/sdk"
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    sdk_wheel = next(path for path in wheels if "eixo_document_sdk_python" in path.name)

    assert wheels
    assert sdists
    with zipfile.ZipFile(sdk_wheel) as wheel:
        names = set(wheel.namelist())
        assert "eixo/py.typed" in names

    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    python = _venv_python(venv_dir)
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(dist),
            "eixo-document-sdk-python",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    code = (
        "from eixo import DocumentEngine, ProcessingRequest, __version__;"
        "print(__version__);"
        "engine = DocumentEngine.local();"
        "print(engine.state.value);"
        "print(ProcessingRequest.__name__)"
    )
    result = subprocess.run(
        [str(python), "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "0.1.0" in result.stdout
    assert "created" in result.stdout


def test_public_import_has_no_runtime_side_effects() -> None:
    assert DocumentEngine.local().runtime._started is False


def test_public_source_contracts() -> None:
    source = BytesSource(content=b"abc", filename="a.bin", size=3)
    assert source.to_dict()["filename"] == "a.bin"
    path_source = LocalPathSource(path=Path("document.pdf"))
    assert path_source.to_dict()["source_type"] == "local_path"


def _venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts/python.exe"
    return venv_dir / "bin/python"


def _env_with_workspace_paths() -> dict[str, str]:
    import os

    paths = [
        ROOT / "packages/document-core/src",
        ROOT / "packages/document-model/src",
        ROOT / "packages/plugins/src",
        ROOT / "packages/artifacts/src",
        ROOT / "packages/document-application/src",
        ROOT / "packages/runtime-local/src",
        ROOT / "packages/document-engine/src",
        ROOT / "packages/document-sdk-python/src",
        ROOT / "apps/api/src",
        ROOT / "apps/cli/src",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(paths[0]))
    env["PYTHONPATH"] = os.pathsep.join(str(path) for path in paths)
    return env
