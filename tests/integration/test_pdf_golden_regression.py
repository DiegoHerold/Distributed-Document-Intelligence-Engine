from __future__ import annotations

from pathlib import Path

import pytest

from tools.pdf_golden import (
    GoldenArtifactComparator,
    GoldenArtifactNormalizer,
    GoldenDifferenceCategory,
    load_json,
)
from tests.support.pdf_scene_fixtures import pdf_golden_fixture

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "tests/golden/pdf/native_scene_basic.expected.json"


@pytest.mark.golden
def test_native_pdf_scene_matches_structural_golden_snapshot() -> None:
    fixture = pdf_golden_fixture()
    expected = load_json(SNAPSHOT)
    actual = _native_scene_snapshot(fixture.native_scene)

    differences = GoldenArtifactComparator().compare(expected, actual)

    assert differences == ()


@pytest.mark.golden
def test_native_pdf_scene_golden_report_pinpoints_geometry_regression() -> None:
    fixture = pdf_golden_fixture()
    expected = _native_scene_snapshot(fixture.native_scene)
    actual = _native_scene_snapshot(
        pdf_golden_fixture().native_scene,
        shifted_bbox=True,
    )

    report = GoldenArtifactComparator().report("doc_golden_scene", expected, actual)
    categories = {item.category for item in report.differences}

    assert report.result == "failed"
    assert GoldenDifferenceCategory.GEOMETRY_CHANGE in categories
    assert "bbox" in report.to_markdown()


def _native_scene_snapshot(  # type: ignore[no-untyped-def]
    native_scene,
    *,
    shifted_bbox: bool = False,
):
    normalized = GoldenArtifactNormalizer().normalize(native_scene)
    scene = normalized["scenes"][0]
    if shifted_bbox:
        scene["elements"][0]["bounding_box"]["x_min"] = 10.5
    return {
        "artifact_type": normalized["artifact_type"],
        "editability": {
            "overall_status": normalized["editability_summary"]["overall_status"],
            "partially_editable_count": normalized["editability_summary"][
                "partially_editable_count"
            ],
            "raster_only_count": normalized["editability_summary"]["raster_only_count"],
            "reconstruction_required_count": normalized["editability_summary"][
                "reconstruction_required_count"
            ],
        },
        "elements": [
            {
                "bbox": item["bounding_box"],
                "clip_path_reference": item["clip_path_reference"],
                "element_id": item["element_id"],
                "element_type": item["element_type"],
                "fidelity": item["fidelity"],
                "resources": item["resource_references"],
                "scene_order": item["scene_order"],
                "source_artifacts": [
                    source["source_artifact_id"]
                    for source in item["source_references"]
                ],
            }
            for item in scene["elements"]
        ],
        "fidelity": {
            "exact_element_count": normalized["fidelity_summary"]["exact_element_count"],
            "normalized_element_count": normalized["fidelity_summary"][
                "normalized_element_count"
            ],
            "overall_level": normalized["fidelity_summary"]["overall_level"],
            "reconstructed_element_count": normalized["fidelity_summary"][
                "reconstructed_element_count"
            ],
        },
        "ordered_element_ids": scene["ordered_element_ids"],
        "page": {
            "element_count": normalized["pages"][0]["element_count"],
            "image_count": normalized["pages"][0]["image_count"],
            "interactive_count": normalized["pages"][0]["interactive_count"],
            "page_id": normalized["pages"][0]["page_id"],
            "text_count": normalized["pages"][0]["text_count"],
            "vector_count": normalized["pages"][0]["vector_count"],
        },
        "statistics": {
            "element_count": normalized["statistics"]["element_count"],
            "image_occurrence_count": normalized["statistics"]["image_occurrence_count"],
            "link_count": normalized["statistics"]["link_count"],
            "native_exact_count": normalized["statistics"]["native_exact_count"],
            "native_normalized_count": normalized["statistics"]["native_normalized_count"],
            "page_count": normalized["statistics"]["page_count"],
            "provider_reconstructed_count": normalized["statistics"][
                "provider_reconstructed_count"
            ],
            "text_element_count": normalized["statistics"]["text_element_count"],
            "vector_element_count": normalized["statistics"]["vector_element_count"],
            "widget_count": normalized["statistics"]["widget_count"],
        },
    }
