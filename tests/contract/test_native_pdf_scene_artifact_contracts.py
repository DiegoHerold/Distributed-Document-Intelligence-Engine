from __future__ import annotations

from dataclasses import replace

from eixo import (
    DocumentId,
    NativePDFSceneArtifactBuilder,
    PDFArtifactLimitationCategory,
    PDFNativeSceneEditabilityStatus,
    PDFPageSceneBuilder,
    PDFSceneFidelity,
    ProviderLimitation,
)
from eixo.core import ArtifactId, ArtifactReference
from tests.contract.test_pdf_page_scene_contracts import _scene_fixture


def test_native_pdf_scene_artifact_consolidates_references_and_statistics() -> None:
    fixture = _scene_fixture()
    scenes = _page_scenes(fixture)
    source_reference = ArtifactReference(
        artifact_id=ArtifactId.parse("art_original_pdf"),
        kind="original_document",
        content_hash="sha256:abc123",
        size_bytes=42,
    )

    artifact = NativePDFSceneArtifactBuilder().build(
        page_scenes_artifact=scenes,
        structure_artifact=fixture.structure,
        typography_artifact=None,
        text_artifact=fixture.text,
        image_artifact=fixture.images,
        vector_artifact=fixture.vectors,
        interactive_artifact=fixture.interactive,
        source_document_reference=source_reference,
    )

    assert artifact.artifact_id.value == "art_native_pdf_scene_doc_scene"
    assert artifact.artifact_type == "native_pdf_scene"
    assert str(artifact.schema_version) == "1.0.0"
    assert artifact.source_hash == "sha256:abc123"
    assert artifact.resource_catalog_reference == "PDFInternalStructureArtifact.resource_catalog"
    assert artifact.page_scene_references == ("pdfscene:pdfpage:0",)
    assert artifact.statistics.page_count == 1
    assert artifact.statistics.element_count == 6
    assert artifact.statistics.image_occurrence_count == 1
    assert artifact.statistics.vector_element_count == 1
    assert artifact.statistics.link_count == 1
    assert artifact.statistics.form_field_count == 1
    assert artifact.fidelity_summary.normalized_element_count >= 1
    assert artifact.editability_summary.image_status == (
        PDFNativeSceneEditabilityStatus.RASTER_ONLY
    )
    assert artifact.text_artifact_reference is not None
    assert artifact.image_artifact_reference is not None
    assert artifact.vector_artifact_reference is not None
    assert artifact.interactive_artifact_reference is not None


def test_native_pdf_scene_artifact_serialization_is_stable_and_provider_safe() -> None:
    fixture = _scene_fixture()
    scenes = _page_scenes(fixture)
    builder = NativePDFSceneArtifactBuilder()

    first = builder.build(
        page_scenes_artifact=scenes,
        structure_artifact=fixture.structure,
        text_artifact=fixture.text,
        image_artifact=fixture.images,
        vector_artifact=fixture.vectors,
        interactive_artifact=fixture.interactive,
        source_hash="sha256:abc123",
    )
    second = builder.build(
        page_scenes_artifact=scenes,
        structure_artifact=fixture.structure,
        text_artifact=fixture.text,
        image_artifact=fixture.images,
        vector_artifact=fixture.vectors,
        interactive_artifact=fixture.interactive,
        source_hash="sha256:abc123",
    )

    first_payload = first.to_dict()
    second_payload = second.to_dict()
    first_payload["created_at"] = "<stable>"
    second_payload["created_at"] = "<stable>"
    first_payload["provenance"]["created_at"] = "<stable>"
    second_payload["provenance"]["created_at"] = "<stable>"
    assert first_payload == second_payload
    assert "FakeDocument" not in str(first_payload)
    assert "jpeg-bytes" not in str(first_payload)


def test_native_pdf_scene_artifact_records_document_mismatch_warning() -> None:
    fixture = _scene_fixture()
    scenes = _page_scenes(fixture)
    mismatched_text = replace(fixture.text, document_id=DocumentId("doc_other"))

    artifact = NativePDFSceneArtifactBuilder().build(
        page_scenes_artifact=scenes,
        structure_artifact=fixture.structure,
        text_artifact=mismatched_text,
    )

    assert artifact.warnings
    assert artifact.warnings[0].code == "native_scene_document_mismatch"
    assert artifact.warnings[0].source_artifact_id == "compatibility"


def test_native_pdf_scene_artifact_consolidates_limitations_by_category() -> None:
    fixture = _scene_fixture()
    scenes = _page_scenes(fixture)
    images = replace(
        fixture.images,
        limitations=(
            ProviderLimitation(
                code="image_bytes_unavailable",
                message="Image bytes are referenced externally.",
                scope="image",
            ),
        ),
    )

    artifact = NativePDFSceneArtifactBuilder().build(
        page_scenes_artifact=scenes,
        structure_artifact=fixture.structure,
        image_artifact=images,
    )

    assert artifact.limitations[0].category == PDFArtifactLimitationCategory.IMAGE_LIMITATION
    assert artifact.limitations[0].fallback == (
        "Preserve references and continue with partial fidelity."
    )
    assert artifact.fidelity_summary.overall_level in {
        PDFSceneFidelity.NATIVE_NORMALIZED,
        PDFSceneFidelity.PROVIDER_RECONSTRUCTED,
        PDFSceneFidelity.UNKNOWN,
    }


def _page_scenes(fixture):
    return PDFPageSceneBuilder().build(
        structure_artifact=fixture.structure,
        page_geometries={fixture.page_reference.stable_id: fixture.geometry},
        text_artifact=fixture.text,
        image_artifact=fixture.images,
        vector_artifact=fixture.vectors,
        interactive_artifact=fixture.interactive,
    )
