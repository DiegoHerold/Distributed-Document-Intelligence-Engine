from __future__ import annotations

from tools.pdf_golden import GoldenArtifactNormalizer


def test_golden_normalizer_removes_only_explicit_unstable_fields() -> None:
    artifact = {
        "created_at": "2026-07-22T12:00:00Z",
        "job_id": "job-runtime",
        "element_id": "sceneelement:text:1",
        "raw_text": "Acentos: \u00e7\u00e3",
        "bounding_box": {"x": 10.0, "y": 11.0, "width": 12.0, "height": 13.0},
        "encoded_hash": "abc123",
        "provenance": {
            "provider": "test-provider",
            "operation_reference": "op-1",
            "storage_key": "local/runtime/key",
        },
    }

    normalized = GoldenArtifactNormalizer().normalize(artifact)

    assert "created_at" not in normalized
    assert "job_id" not in normalized
    assert normalized["element_id"] == "sceneelement:text:1"
    assert normalized["raw_text"] == "Acentos: \u00e7\u00e3"
    assert normalized["bounding_box"]["x"] == 10.0
    assert normalized["encoded_hash"] == "abc123"
    assert normalized["provenance"]["operation_reference"] == "op-1"
    assert "storage_key" not in normalized["provenance"]


def test_golden_normalizer_marks_temporary_paths_without_touching_geometry() -> None:
    artifact = {
        "source_path": "C:\\tmp\\eixo\\document.pdf",
        "bounding_box": {"x": 1.25, "y": 2.5},
    }

    normalized = GoldenArtifactNormalizer().normalize(artifact)

    assert normalized["source_path"] == "<temporary-path>"
    assert normalized["bounding_box"] == {"x": 1.25, "y": 2.5}
