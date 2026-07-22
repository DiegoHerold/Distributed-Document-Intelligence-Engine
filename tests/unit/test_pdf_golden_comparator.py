from __future__ import annotations

from tools.pdf_golden import GoldenArtifactComparator, GoldenDifferenceCategory


def test_comparator_accepts_geometry_inside_documented_tolerance() -> None:
    comparator = GoldenArtifactComparator()

    differences = comparator.compare(
        {"bounding_box": {"x": 10.0, "y": 20.0}},
        {"bounding_box": {"x": 10.005, "y": 20.0}},
    )

    assert differences == ()


def test_comparator_reports_geometry_outside_tolerance() -> None:
    comparator = GoldenArtifactComparator()

    differences = comparator.compare(
        {"bounding_box": {"x": 10.0}},
        {"bounding_box": {"x": 10.8}},
    )

    assert len(differences) == 1
    assert differences[0].category is GoldenDifferenceCategory.GEOMETRY_CHANGE
    assert differences[0].tolerance == 0.01


def test_comparator_classifies_structural_regressions() -> None:
    comparator = GoldenArtifactComparator()

    expected = {
        "ordered_element_ids": ["text-1", "image-1"],
        "resources": {"image_hash": "old"},
        "warnings": ["old-warning"],
        "fidelity_summary": {"overall_level": "native_exact"},
    }
    actual = {
        "ordered_element_ids": ["image-1", "text-1"],
        "resources": {"image_hash": "new"},
        "warnings": ["new-warning"],
        "fidelity_summary": {"overall_level": "heuristic"},
        "relations": ["new-relation"],
    }

    categories = {item.category for item in comparator.compare(expected, actual)}

    assert GoldenDifferenceCategory.ORDER_CHANGE in categories
    assert GoldenDifferenceCategory.RESOURCE_CHANGE in categories
    assert GoldenDifferenceCategory.WARNING_CHANGE in categories
    assert GoldenDifferenceCategory.FIDELITY_CHANGE in categories
    assert GoldenDifferenceCategory.NEW_ELEMENT in categories


def test_comparator_report_is_actionable_markdown() -> None:
    comparator = GoldenArtifactComparator()

    report = comparator.report(
        "doc",
        {"raw_text": "A"},
        {"raw_text": "B"},
        diagnostic_artifacts=("preview.png",),
    )

    assert report.result == "failed"
    assert report.diagnostic_artifacts == ("preview.png",)
    assert "content_change" in report.to_markdown()
    assert "raw_text" in report.to_markdown()
