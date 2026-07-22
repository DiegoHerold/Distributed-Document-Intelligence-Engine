from __future__ import annotations

from pathlib import Path

import pytest

from eixo.pdf.diagnostics import PDFDiagnosticPreviewGenerator
from tools.pdf_golden import GoldenArtifactComparator, load_json
from tests.support.pdf_scene_fixtures import pdf_golden_fixture

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "tests/golden/pdf/diagnostic_preview_basic.expected.json"


@pytest.mark.visual
def test_diagnostic_preview_matches_reduced_visual_golden_snapshot() -> None:
    preview = PDFDiagnosticPreviewGenerator().generate(pdf_golden_fixture().scene)
    expected = load_json(SNAPSHOT)
    actual = {
        "height": preview.height,
        "limitations": list(preview.limitations),
        "overlay_counts": preview.legend["overlay_counts"],
        "overlay_ids": [overlay.element_id for overlay in preview.overlays],
        "page_id": preview.page_id,
        "png_sha256": preview.png_sha256,
        "width": preview.width,
    }

    differences = GoldenArtifactComparator().compare(expected, actual)

    assert preview.png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert differences == ()


@pytest.mark.visual
def test_visual_difference_metrics_are_stable_for_identical_preview() -> None:
    first = PDFDiagnosticPreviewGenerator().generate(pdf_golden_fixture().scene)
    second = PDFDiagnosticPreviewGenerator().generate(pdf_golden_fixture().scene)

    assert first.png_sha256 == second.png_sha256
    assert _byte_difference_ratio(first.png_bytes, second.png_bytes) == 0.0


def _byte_difference_ratio(first: bytes, second: bytes) -> float:
    length = max(len(first), len(second))
    if length == 0:
        return 0.0
    differences = abs(len(first) - len(second))
    differences += sum(
        1 for left, right in zip(first, second, strict=False) if left != right
    )
    return differences / length
