from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.pdf_golden import (
    corpus_metrics,
    discover_corpus_documents,
    load_json,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = ROOT / "tests/corpus/pdf"


def test_pdf_corpus_manifests_hashes_and_expectations_are_valid() -> None:
    manifests = discover_corpus_documents(CORPUS_ROOT)
    errors = [error for manifest in manifests for error in validate_manifest(manifest)]

    assert len(manifests) >= 10
    assert errors == []


def test_pdf_corpus_separates_golden_and_exploratory_documents() -> None:
    manifests = [load_json(path) for path in discover_corpus_documents(CORPUS_ROOT)]
    golden = [item for item in manifests if item["golden_type"] == "golden"]
    exploratory = [item for item in manifests if item["golden_type"] == "exploratory"]

    assert golden
    assert exploratory
    assert all("synthetic" in item["tags"] for item in manifests)
    assert all(item["license"] == "CC0-1.0 synthetic fixture" for item in manifests)


def test_pdf_corpus_metrics_cover_core_block_3_features() -> None:
    metrics = corpus_metrics(CORPUS_ROOT)
    features = set(metrics["feature_coverage"])

    assert metrics["document_count"] >= 10
    assert metrics["golden_test_count"] >= 8
    assert metrics["visual_test_count"] >= 3
    assert {
        "native_text",
        "glyph_order",
        "subset_font",
        "image_resource",
        "image_occurrence",
        "rectangle",
        "clipping_path",
        "external_link",
        "form_widget",
        "rotated_page",
        "crop_box",
        "hybrid_pdf",
        "password_required",
        "malformed_pdf",
    }.issubset(features)


def test_pdf_golden_update_command_is_explicit_and_dry_run_by_default() -> None:
    result = subprocess.run(
        [str(sys.executable), "-m", "tests.update_pdf_goldens"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "dry-run" in result.stdout
    assert "documents=" in result.stdout
