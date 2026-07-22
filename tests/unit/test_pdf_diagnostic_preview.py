from __future__ import annotations

from eixo.pdf.diagnostics import (
    PDFDiagnosticPreviewConfig,
    PDFDiagnosticPreviewGenerator,
)
from tests.support.pdf_scene_fixtures import pdf_golden_fixture


def test_diagnostic_preview_generates_png_and_metadata_without_mutating_scene() -> None:
    fixture = pdf_golden_fixture()
    before = fixture.scene.to_dict()

    artifact = PDFDiagnosticPreviewGenerator().generate(fixture.scene)

    assert artifact.png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(artifact.png_sha256) == 64
    assert artifact.media_type == "image/png"
    assert artifact.page_id == fixture.scene.page_id
    assert artifact.legend["overlay_counts"]["text_span"] == 1
    assert artifact.legend["overlay_counts"]["image"] == 1
    assert artifact.legend["overlay_counts"]["vector"] == 1
    assert any(item.clip_path_reference for item in artifact.overlays)
    assert all(item.marker for item in artifact.overlays)
    assert "diagnostic_preview.no_official_pdf_renderer" in artifact.limitations
    assert fixture.scene.to_dict() == before


def test_diagnostic_preview_can_hide_invisible_elements() -> None:
    scene = pdf_golden_fixture().scene_with_hidden_element()

    artifact = PDFDiagnosticPreviewGenerator().generate(
        scene,
        PDFDiagnosticPreviewConfig(show_invisible_elements=False),
    )

    element_ids = {item.element_id for item in artifact.overlays}

    assert "sceneelement:text_span:pdfpage-0:hidden" not in element_ids
