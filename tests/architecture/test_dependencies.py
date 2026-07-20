from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def imports_under(path: Path) -> set[str]:
    imports: set[str] = set()
    for file in path.rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0].lower() for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0].lower())
    return imports


def test_application_has_no_transport_or_infrastructure_imports() -> None:
    forbidden = {
        "fastapi",
        "starlette",
        "click",
        "typer",
        "temporalio",
        "sqlalchemy",
        "redis",
        "boto3",
        "minio",
    }
    imports = imports_under(ROOT / "packages/document-application/src")

    assert imports.isdisjoint(forbidden)


def test_core_does_not_import_adapters_or_apps() -> None:
    imports = imports_under(ROOT / "packages/document-core/src")

    assert "eixo_api" not in imports
    assert "eixo_cli" not in imports


def test_http_upload_types_stay_outside_kernel_and_application() -> None:
    forbidden_names = {"UploadFile", "Request", "FormData"}
    for base in (
        ROOT / "packages/document-core/src",
        ROOT / "packages/document-application/src",
        ROOT / "packages/document-engine/src",
    ):
        for file in base.rglob("*.py"):
            tree = ast.parse(file.read_text(encoding="utf-8"))
            names = {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name)
            }
            assert names.isdisjoint(forbidden_names)


def test_document_engine_has_no_transport_or_infrastructure_imports() -> None:
    forbidden = {
        "fastapi",
        "starlette",
        "click",
        "typer",
        "temporalio",
        "sqlalchemy",
        "redis",
        "boto3",
        "minio",
    }
    imports = imports_under(ROOT / "packages/document-engine/src")

    assert imports.isdisjoint(forbidden)


def test_api_is_http_adapter_only() -> None:
    imports = imports_under(ROOT / "apps/api/src")

    assert "eixo.application" not in imports
    assert "eixo.runtime" not in imports
    assert "eixo.plugins" not in imports
    assert "sqlalchemy" not in imports
    assert "redis" not in imports
    assert "boto3" not in imports
    assert "minio" not in imports


def test_api_routers_do_not_access_stores_or_runtime_directly() -> None:
    imports = imports_under(ROOT / "apps/api/src/eixo_api/routers")

    assert "eixo.application" not in imports
    assert "eixo.runtime" not in imports
    assert "eixo.plugins" not in imports


def test_api_does_not_duplicate_domain_contract_classes() -> None:
    forbidden_names = {
        "ApiProcessingRequest",
        "ApiProcessingResult",
        "ApiInspectionResult",
        "ApiParseResult",
    }
    for file in (ROOT / "apps/api/src").rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        class_names = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        }
        assert class_names.isdisjoint(forbidden_names)


def test_cli_has_no_transport_infrastructure_or_parser_imports() -> None:
    forbidden = {
        "fastapi",
        "starlette",
        "fitz",
        "pymupdf",
        "openpyxl",
        "pandas",
        "sqlalchemy",
        "redis",
        "boto3",
        "minio",
    }
    imports = imports_under(ROOT / "apps/cli/src")

    assert imports.isdisjoint(forbidden)
    assert "eixo.application" not in imports
    assert "eixo.runtime" not in imports


def test_core_application_runtime_and_sdk_do_not_import_cli_framework() -> None:
    forbidden = {"typer", "click", "argparse", "eixo_cli"}
    for path in (
        ROOT / "packages/document-core/src",
        ROOT / "packages/document-application/src",
        ROOT / "packages/runtime-local/src",
        ROOT / "packages/document-sdk-python/src",
    ):
        assert imports_under(path).isdisjoint(forbidden)


def test_application_does_not_depend_on_document_engine() -> None:
    imports = imports_under(ROOT / "packages/document-application/src")

    assert "eixo.engine" not in imports
    assert "eixo_engine" not in imports


def test_sdk_does_not_implement_internals_or_transport() -> None:
    forbidden = {
        "fastapi",
        "starlette",
        "click",
        "typer",
        "sqlalchemy",
        "redis",
        "boto3",
        "minio",
    }
    imports = imports_under(ROOT / "packages/document-sdk-python/src")

    assert imports.isdisjoint(forbidden)
    assert "eixo.application" not in imports
