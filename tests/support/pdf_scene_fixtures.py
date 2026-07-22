from __future__ import annotations

from dataclasses import replace

from eixo import PageGeometry, Size
from eixo.core import ArtifactId, ContractVersion, DocumentId, ProviderId, ProviderVersion
from eixo.core.versions import SchemaVersion
from eixo.geometry import BoundingBox
from eixo.pdf import (
    NativeGlyph,
    NativePDFSceneArtifactBuilder,
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
    PDFPageScene,
    PDFPageSceneBuilder,
    PDFPageScenesArtifact,
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
    PDFSceneFidelity,
    PDFSceneVisibility,
    PDFVectorPaintIntent,
    PDFVectorPath,
    PDFVectorVisibility,
    PDFVisualElement,
    PDFInternalPageMap,
    PDFInternalStructureArtifact,
)


class PDFGoldenFixture:
    def __init__(self) -> None:
        self.provider = PDFProviderDescriptor(
            provider_id=ProviderId("prov_golden_pdf"),
            name="Golden PDF Provider",
            provider_version=ProviderVersion("0.0.1"),
            backend_name="golden-fixture",
            backend_version="0.0.1",
            capabilities=PDFProviderCapabilities(),
        )
        self.document_id = DocumentId("doc_golden_scene")
        self.page_reference = PDFPageReference(page_index=0, page_number=1)
        self.geometry = PageGeometry(size=Size(200, 160))
        self.provenance = PDFProviderProvenance(
            provider_id=self.provider.provider_id,
            provider_version=self.provider.provider_version,
            backend_name=self.provider.backend_name,
            backend_version=self.provider.backend_version,
            operation="golden_fixture",
            page_index=0,
        )
        self.font_ref = PDFResourceReference(
            resource_id="pdffont:subset-f1",
            resource_type=PDFResourceType.FONT,
            scope=PDFResourceScope.PAGE,
            page_reference=self.page_reference,
        )
        self.image_ref = PDFResourceReference(
            resource_id="pdfimage:logo",
            resource_type=PDFResourceType.IMAGE,
            scope=PDFResourceScope.PAGE,
            page_reference=self.page_reference,
        )
        self.structure = PDFInternalStructureArtifact(
            artifact_version=ContractVersion("1.0.0"),
            provider=self.provider,
            object_graph=PDFObjectGraph(),
            resource_catalog=PDFResourceCatalog(
                fonts=(self.font_ref,),
                images=(self.image_ref,),
            ),
            pages=(
                PDFInternalPageMap(
                    page_reference=self.page_reference,
                    own_resources=(self.font_ref, self.image_ref),
                ),
            ),
            document_id=self.document_id,
            provenance=self.provenance,
        )
        self.text = self._text_artifact()
        self.images = self._image_artifact()
        self.vectors = self._vector_artifact()
        self.interactive = self._interactive_artifact()
        self.scenes_artifact = self._scenes_artifact()
        self.scene = self.scenes_artifact.pages[0]
        self.native_scene = NativePDFSceneArtifactBuilder().build(
            page_scenes_artifact=self.scenes_artifact,
            structure_artifact=self.structure,
            inspection=None,
            typography_artifact=None,
            text_artifact=self.text,
            image_artifact=self.images,
            vector_artifact=self.vectors,
            interactive_artifact=self.interactive,
            source_hash="sha256:golden-fixture",
        )

    def scene_with_shifted_first_element(self) -> PDFPageScene:
        first = self.scene.elements[0]
        shifted = replace(first, bounding_box=BoundingBox(10.5, 10, 42, 22))
        return replace(
            self.scene,
            elements=(shifted,) + self.scene.elements[1:],
        )

    def scene_with_hidden_element(self) -> PDFPageScene:
        hidden = PDFVisualElement(
            element_id="sceneelement:text_span:pdfpage-0:hidden",
            element_type=PDFSceneElementType.TEXT_SPAN,
            page_id=self.page_reference.stable_id,
            bounding_box=BoundingBox(5, 130, 30, 140),
            scene_order=99,
            visibility=PDFSceneVisibility.INVISIBLE,
            fidelity=PDFSceneFidelity.NATIVE_NORMALIZED,
            provenance=self.provenance,
        )
        return replace(
            self.scene,
            elements=self.scene.elements + (hidden,),
            ordered_element_ids=self.scene.ordered_element_ids + (hidden.element_id,),
        )

    def _text_artifact(self) -> PDFNativeTextArtifact:
        glyphs = (
            NativeGlyph(
                glyph_id="pdfglyph:page-0:span-0:glyph-0",
                page_id=self.page_reference.stable_id,
                font_id="pdffont:subset-f1",
                unicode_text="A",
                bounding_box=BoundingBox(10, 10, 18, 22),
                paint_order=PDFPaintOrder(
                    global_paint_order=0,
                    confidence=PDFPaintOrderConfidence.EXACT,
                ),
                provenance=self.provenance,
            ),
            NativeGlyph(
                glyph_id="pdfglyph:page-0:span-0:glyph-1",
                page_id=self.page_reference.stable_id,
                font_id="pdffont:subset-f1",
                unicode_text="B",
                bounding_box=BoundingBox(20, 10, 28, 22),
                paint_order=PDFPaintOrder(
                    global_paint_order=1,
                    confidence=PDFPaintOrderConfidence.EXACT,
                ),
                provenance=self.provenance,
            ),
        )
        span = NativeTextSpan(
            span_id="pdfspan:page-0:block-0:line-0:span-0",
            page_id=self.page_reference.stable_id,
            glyph_ids=tuple(glyph.glyph_id for glyph in glyphs),
            font_id="pdffont:subset-f1",
            raw_text="AB",
            bounding_box=BoundingBox(10, 10, 42, 22),
            paint_order=PDFPaintOrder(
                global_paint_order=2,
                confidence=PDFPaintOrderConfidence.EXACT,
            ),
            provenance=self.provenance,
        )
        page = PDFPageNativeTextLayer(
            page_reference=self.page_reference,
            glyphs=glyphs,
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
            occurrence_id="pdfimageocc:page-0:logo-0",
            image_resource_id="pdfimage:logo",
            page_id=self.page_reference.stable_id,
            bounding_box=BoundingBox(70, 20, 130, 70),
            clip_path_reference="pdfclip:page-0:clip-0",
            paint_order=PDFPaintOrder(global_paint_order=3),
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
            vector_id="pdfvector:page-0:table-border-0",
            page_id=self.page_reference.stable_id,
            bounding_box=BoundingBox(8, 80, 180, 120),
            clip_path_reference="pdfclip:page-0:clip-0",
            paint_intent=PDFVectorPaintIntent.STROKE,
            paint_order=PDFPaintOrder(
                global_paint_order=4,
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
            link_id="pdflink:page-0:external",
            page_id=self.page_reference.stable_id,
            link_type=PDFLinkType.EXTERNAL_URI,
            bounding_box=BoundingBox(10, 128, 60, 145),
            uri="https://example.test",
            visibility=PDFInteractiveVisibility.VISIBLE,
            provenance=self.provenance,
        )
        field = PDFFormField(
            field_id="pdffield:accepted",
            field_type=PDFFormFieldType.CHECKBOX,
            widget_ids=("pdfwidget:page-0:accepted",),
        )
        widget = PDFFormWidget(
            widget_id="pdfwidget:page-0:accepted",
            field_id=field.field_id,
            page_id=self.page_reference.stable_id,
            bounding_box=BoundingBox(70, 128, 86, 145),
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

    def _scenes_artifact(self) -> PDFPageScenesArtifact:
        return PDFPageSceneBuilder().build(
            structure_artifact=self.structure,
            page_geometries={self.page_reference.stable_id: self.geometry},
            text_artifact=self.text,
            image_artifact=self.images,
            vector_artifact=self.vectors,
            interactive_artifact=self.interactive,
        )


def pdf_golden_fixture() -> PDFGoldenFixture:
    return PDFGoldenFixture()
