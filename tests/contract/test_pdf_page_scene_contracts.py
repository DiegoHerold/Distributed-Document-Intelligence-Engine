from __future__ import annotations

from eixo import (
    PageGeometry,
    Point,
    Size,
)
from eixo.core import ContractVersion, DocumentId, ProviderId, ProviderVersion
from eixo.geometry import BoundingBox
from eixo.pdf import (
    NativeGlyph,
    NativeTextSpan,
    PDFFormField,
    PDFFormFieldType,
    PDFFormWidget,
    PDFImageCatalog,
    PDFImageOccurrence,
    PDFInteractiveArtifact,
    PDFInteractiveVisibility,
    PDFLink,
    PDFLinkType,
    PDFNativeImageArtifact,
    PDFNativeTextArtifact,
    PDFNativeTextLayer,
    PDFNativeVectorArtifact,
    PDFObjectGraph,
    PDFPageImageLayer,
    PDFPageNativeTextLayer,
    PDFPageReference,
    PDFPageSceneBuilder,
    PDFPageSceneOptions,
    PDFPageVectorLayer,
    PDFPaintOrder,
    PDFPaintOrderConfidence,
    PDFProviderCapabilities,
    PDFProviderDescriptor,
    PDFProviderProvenance,
    PDFResourceCatalog,
    PDFResourceReference,
    PDFResourceScope,
    PDFResourceType,
    PDFSceneElementType,
    PDFSceneOrderConfidence,
    PDFSceneRelationType,
    PDFVectorPaintIntent,
    PDFVectorPath,
    PDFVectorVisibility,
    PDFInternalPageMap,
    PDFInternalStructureArtifact,
)


def test_page_scene_builder_consolidates_visual_elements_without_reextracting() -> None:
    fixture = _scene_fixture()

    artifact = PDFPageSceneBuilder().build(
        structure_artifact=fixture.structure,
        page_geometries={fixture.page_reference.stable_id: fixture.geometry},
        text_artifact=fixture.text,
        image_artifact=fixture.images,
        vector_artifact=fixture.vectors,
        interactive_artifact=fixture.interactive,
    )

    scene = artifact.pages[0]
    assert scene.scene_id == "pdfscene:pdfpage:0"
    assert scene.geometry.width == 200
    assert len(scene.elements) == 6
    assert scene.statistics.text_element_count == 2
    assert scene.statistics.image_element_count == 1
    assert scene.statistics.vector_element_count == 1
    assert scene.statistics.link_count == 1
    assert scene.statistics.form_widget_count == 1
    assert scene.ordered_element_ids == (
        "sceneelement:text_span:pdfpage-0:pdfspan-page-0-block-0-line-0-span-0",
        "sceneelement:text_glyph:pdfpage-0:pdfglyph-page-0-span-0-glyph-0",
        "sceneelement:image:pdfpage-0:pdfimageocc-page-0-occurrence-0",
        "sceneelement:vector:pdfpage-0:pdfvector-page-0-path-0",
    )
    image = scene.element_by_id(
        "sceneelement:image:pdfpage-0:pdfimageocc-page-0-occurrence-0"
    )
    assert image is not None
    assert image.normalized_bounding_box is not None
    assert image.resource_references == ("pdfimage:resource-1",)


def test_page_scene_builder_preserves_relations_and_stable_serialization() -> None:
    fixture = _scene_fixture()
    builder = PDFPageSceneBuilder()

    first = builder.build(
        structure_artifact=fixture.structure,
        page_geometries={fixture.page_reference.stable_id: fixture.geometry},
        text_artifact=fixture.text,
        image_artifact=fixture.images,
        vector_artifact=fixture.vectors,
        interactive_artifact=fixture.interactive,
    )
    second = builder.build(
        structure_artifact=fixture.structure,
        page_geometries={fixture.page_reference.stable_id: fixture.geometry},
        text_artifact=fixture.text,
        image_artifact=fixture.images,
        vector_artifact=fixture.vectors,
        interactive_artifact=fixture.interactive,
    )

    scene = first.pages[0]
    assert first.to_dict() == second.to_dict()
    relation_types = {relation.relation_type for relation in scene.relations}
    assert PDFSceneRelationType.USES_FONT in relation_types
    assert PDFSceneRelationType.USES_IMAGE in relation_types
    assert PDFSceneRelationType.CLIPPED_BY in relation_types
    assert PDFSceneRelationType.LINKS_TO in relation_types
    assert PDFSceneRelationType.PAINTED_BEFORE in relation_types
    assert "ProviderObject" not in str(first.to_dict())
    assert all(
        element.order_confidence
        in {
            PDFSceneOrderConfidence.EXACT,
            PDFSceneOrderConfidence.PROVIDER_APPROXIMATION,
            PDFSceneOrderConfidence.UNAVAILABLE,
        }
        for element in scene.elements
    )


def test_page_scene_builder_warns_when_geometry_is_missing() -> None:
    fixture = _scene_fixture()

    artifact = PDFPageSceneBuilder().build(
        structure_artifact=fixture.structure,
        page_geometries={},
        text_artifact=fixture.text,
        options=PDFPageSceneOptions(),
    )

    assert artifact.pages == ()
    assert artifact.warnings[0].code == "scene_page_geometry_missing"


class _Fixture:
    def __init__(self) -> None:
        self.provider = PDFProviderDescriptor(
            provider_id=ProviderId("prov_test_pdf"),
            name="Test PDF Provider",
            provider_version=ProviderVersion("0.0.1"),
            backend_name="test",
            backend_version="0.0.1",
            capabilities=PDFProviderCapabilities(),
        )
        self.document_id = DocumentId("doc_scene")
        self.page_reference = PDFPageReference(page_index=0, page_number=1)
        self.geometry = PageGeometry(size=Size(200, 200))
        self.provenance = PDFProviderProvenance(
            provider_id=self.provider.provider_id,
            provider_version=self.provider.provider_version,
            backend_name=self.provider.backend_name,
            backend_version=self.provider.backend_version,
            operation="test",
        )
        self.font_ref = PDFResourceReference(
            resource_id="pdffont:test",
            resource_type=PDFResourceType.FONT,
            scope=PDFResourceScope.PAGE,
            page_reference=self.page_reference,
        )
        self.structure = PDFInternalStructureArtifact(
            artifact_version=ContractVersion("1.0.0"),
            provider=self.provider,
            object_graph=PDFObjectGraph(),
            resource_catalog=PDFResourceCatalog(),
            pages=(
                PDFInternalPageMap(
                    page_reference=self.page_reference,
                    own_resources=(self.font_ref,),
                ),
            ),
            document_id=self.document_id,
            provenance=self.provenance,
        )
        self.text = self._text_artifact()
        self.images = self._image_artifact()
        self.vectors = self._vector_artifact()
        self.interactive = self._interactive_artifact()

    def _text_artifact(self) -> PDFNativeTextArtifact:
        glyph = NativeGlyph(
            glyph_id="pdfglyph:page-0:span-0:glyph-0",
            page_id=self.page_reference.stable_id,
            font_id="pdffont:test",
            unicode_text="A",
            bounding_box=BoundingBox(10, 10, 18, 22),
            paint_order=PDFPaintOrder(
                global_paint_order=0,
                confidence=PDFPaintOrderConfidence.EXACT,
            ),
            provenance=self.provenance,
        )
        span = NativeTextSpan(
            span_id="pdfspan:page-0:block-0:line-0:span-0",
            page_id=self.page_reference.stable_id,
            glyph_ids=(glyph.glyph_id,),
            font_id="pdffont:test",
            raw_text="A",
            bounding_box=BoundingBox(10, 10, 18, 22),
            paint_order=PDFPaintOrder(
                global_paint_order=1,
                confidence=PDFPaintOrderConfidence.EXACT,
            ),
            provenance=self.provenance,
        )
        page = PDFPageNativeTextLayer(
            page_reference=self.page_reference,
            glyphs=(glyph,),
            spans=(span,),
        )
        return PDFNativeTextArtifact(
            artifact_version=ContractVersion("1.0.0"),
            provider=self.provider,
            document_id=self.document_id,
            source_structure_artifact=self.structure,
            pages=(page,),
            text_layer=PDFNativeTextLayer(page_text_layers=(page,)),
            provenance=self.provenance,
        )

    def _image_artifact(self) -> PDFNativeImageArtifact:
        occurrence = PDFImageOccurrence(
            occurrence_id="pdfimageocc:page-0:occurrence-0",
            image_resource_id="pdfimage:resource-1",
            page_id=self.page_reference.stable_id,
            bounding_box=BoundingBox(20, 20, 80, 80),
            clip_path_reference="pdfclip:page-0:clip-0",
            paint_order=PDFPaintOrder(global_paint_order=2),
            provenance=self.provenance,
        )
        return PDFNativeImageArtifact(
            artifact_version=ContractVersion("1.0.0"),
            provider=self.provider,
            image_catalog=PDFImageCatalog(occurrences=(occurrence,)),
            pages=(
                PDFPageImageLayer(
                    page_reference=self.page_reference,
                    occurrence_ids=(occurrence.occurrence_id,),
                    ordered_occurrence_ids=(occurrence.occurrence_id,),
                ),
            ),
            document_id=self.document_id,
            source_structure_artifact=self.structure,
            provenance=self.provenance,
        )

    def _vector_artifact(self) -> PDFNativeVectorArtifact:
        vector = PDFVectorPath(
            vector_id="pdfvector:page-0:path-0",
            page_id=self.page_reference.stable_id,
            bounding_box=BoundingBox(0, 0, 100, 100),
            clip_path_reference="pdfclip:page-0:clip-0",
            paint_intent=PDFVectorPaintIntent.STROKE,
            paint_order=PDFPaintOrder(
                global_paint_order=3,
                confidence=PDFPaintOrderConfidence.PROVIDER_APPROXIMATION,
            ),
            visibility=PDFVectorVisibility.VISIBLE,
            provenance=self.provenance,
        )
        return PDFNativeVectorArtifact(
            artifact_version=ContractVersion("1.0.0"),
            provider=self.provider,
            document_id=self.document_id,
            source_structure_artifact=self.structure,
            vector_paths=(vector,),
            page_layers=(
                PDFPageVectorLayer(
                    page_reference=self.page_reference,
                    vector_ids=(vector.vector_id,),
                    ordered_element_ids=(vector.vector_id,),
                ),
            ),
            provenance=self.provenance,
        )

    def _interactive_artifact(self) -> PDFInteractiveArtifact:
        link = PDFLink(
            link_id="pdflink:page-0:link-0",
            page_id=self.page_reference.stable_id,
            link_type=PDFLinkType.EXTERNAL_URI,
            bounding_box=BoundingBox(10, 30, 80, 45),
            uri="https://example.test",
            visibility=PDFInteractiveVisibility.VISIBLE,
            provenance=self.provenance,
        )
        field = PDFFormField(
            field_id="pdffield:accepted",
            field_type=PDFFormFieldType.CHECKBOX,
            widget_ids=("pdfwidget:page-0:widget-0",),
        )
        widget = PDFFormWidget(
            widget_id="pdfwidget:page-0:widget-0",
            field_id=field.field_id,
            page_id=self.page_reference.stable_id,
            bounding_box=BoundingBox(90, 30, 105, 45),
            visibility=PDFInteractiveVisibility.VISIBLE,
            provenance=self.provenance,
        )
        return PDFInteractiveArtifact(
            artifact_version=ContractVersion("1.0.0"),
            provider=self.provider,
            document_id=self.document_id,
            source_structure_artifact=self.structure,
            links=(link,),
            fields=(field,),
            widgets=(widget,),
            provenance=self.provenance,
        )


def _scene_fixture() -> _Fixture:
    return _Fixture()
