from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import replace

from eixo.core import EixoWarning
from eixo.core.versions import ContractVersion
from eixo.geometry import BoundingBox, PageGeometry
from eixo.pdf.images import PDFImageOccurrence, PDFImageVisibility, PDFNativeImageArtifact
from eixo.pdf.interactive import (
    PDFAnnotation,
    PDFFormWidget,
    PDFInteractiveArtifact,
    PDFInteractiveVisibility,
    PDFLayer,
    PDFLink,
)
from eixo.pdf.native_text import (
    NativeGlyph,
    NativeTextBlock,
    NativeTextLine,
    NativeTextSpan,
    NativeWord,
    PDFNativeTextArtifact,
    PDFNativeTextVisibility,
)
from eixo.pdf.scene import (
    PDFPageScene,
    PDFPageSceneOptions,
    PDFPageScenesArtifact,
    PDFSceneEditabilityHint,
    PDFSceneElementType,
    PDFSceneFidelity,
    PDFSceneOrderConfidence,
    PDFSceneOrderMethod,
    PDFSceneRelation,
    PDFSceneRelationType,
    PDFSceneSourceReference,
    PDFSceneVisibility,
    PDFVisualElement,
    pdf_page_scene_statistics,
    pdf_page_scenes_statistics,
    pdf_scene_element_id,
    pdf_scene_id,
    pdf_scene_relation_id,
)
from eixo.pdf.structure import PDFInternalStructureArtifact, PDFPaintOrderConfidence
from eixo.pdf.vectors import (
    PDFClippingPath,
    PDFNativeVectorArtifact,
    PDFVectorPath,
    PDFVectorVisibility,
)


class PDFPageSceneBuilder:
    def build(
        self,
        *,
        structure_artifact: PDFInternalStructureArtifact,
        page_geometries: Mapping[str, PageGeometry],
        text_artifact: PDFNativeTextArtifact | None = None,
        image_artifact: PDFNativeImageArtifact | None = None,
        vector_artifact: PDFNativeVectorArtifact | None = None,
        interactive_artifact: PDFInteractiveArtifact | None = None,
        options: PDFPageSceneOptions | None = None,
    ) -> PDFPageScenesArtifact:
        opts = options or PDFPageSceneOptions()
        started = time.monotonic()
        warnings = _compatibility_warnings(
            structure_artifact,
            text_artifact,
            image_artifact,
            vector_artifact,
            interactive_artifact,
        )
        pages = []
        selected = _selected_pages(len(structure_artifact.pages), opts.page_selection)
        for page_map in structure_artifact.pages:
            page_reference = page_map.page_reference
            if page_reference.page_index not in selected:
                continue
            if opts.timeout_seconds is not None:
                if time.monotonic() - started > opts.timeout_seconds:
                    warnings.append(
                        EixoWarning(
                            code="scene_partial",
                            message="PDF page scene building stopped after timeout.",
                            scope="pdf.scene",
                        )
                    )
                    break
            geometry = page_geometries.get(page_reference.stable_id)
            if geometry is None:
                warnings.append(
                    EixoWarning(
                        code="scene_page_geometry_missing",
                        message="PageGeometry is required to build a page scene.",
                        scope=page_reference.stable_id,
                    )
                )
                continue
            pages.append(
                self._build_page(
                    structure_artifact=structure_artifact,
                    page_id=page_reference.stable_id,
                    page_index=page_reference.page_index,
                    geometry=geometry,
                    text_artifact=text_artifact,
                    image_artifact=image_artifact,
                    vector_artifact=vector_artifact,
                    interactive_artifact=interactive_artifact,
                    options=opts,
                )
            )
        pages_tuple = tuple(pages)
        return PDFPageScenesArtifact(
            artifact_version=ContractVersion("1.0.0"),
            provider=_provider(
                structure_artifact,
                text_artifact,
                image_artifact,
                vector_artifact,
                interactive_artifact,
            ),
            document_id=structure_artifact.document_id,
            source_artifacts=_source_artifact_references(
                structure_artifact,
                text_artifact,
                image_artifact,
                vector_artifact,
                interactive_artifact,
            ),
            resource_catalog_reference="pdfresourcecatalog:document",
            pages=pages_tuple,
            statistics=pdf_page_scenes_statistics(pages_tuple),
            warnings=tuple(warnings),
            limitations=(
                structure_artifact.limitations
                + _limitations(text_artifact, image_artifact, vector_artifact, interactive_artifact)
            ),
            provenance=structure_artifact.provenance,
        )

    def _build_page(
        self,
        *,
        structure_artifact: PDFInternalStructureArtifact,
        page_id: str,
        page_index: int,
        geometry: PageGeometry,
        text_artifact: PDFNativeTextArtifact | None,
        image_artifact: PDFNativeImageArtifact | None,
        vector_artifact: PDFNativeVectorArtifact | None,
        interactive_artifact: PDFInteractiveArtifact | None,
        options: PDFPageSceneOptions,
    ) -> PDFPageScene:
        elements: list[PDFVisualElement] = []
        relations: list[PDFSceneRelation] = []
        warnings: list[EixoWarning] = []
        elements.extend(_text_elements(page_id, geometry, text_artifact))
        elements.extend(_image_elements(page_id, geometry, image_artifact))
        elements.extend(_vector_elements(page_id, geometry, vector_artifact))
        elements.extend(
            _interactive_elements(page_id, geometry, interactive_artifact, options)
        )
        elements, duplicate_warnings = _deduplicate(elements)
        warnings.extend(duplicate_warnings)
        if options.max_elements_per_page is not None:
            if len(elements) > options.max_elements_per_page:
                warnings.append(
                    EixoWarning(
                        code="scene_partial",
                        message="Page exceeded max_elements_per_page.",
                        scope=page_id,
                    )
                )
                elements = elements[: options.max_elements_per_page]
        elements = _apply_scene_order(tuple(elements))
        relations.extend(_relations(elements, interactive_artifact))
        ordered_ids = tuple(
            item.element_id for item in elements if item.scene_order is not None
        )
        text_ids = _ids_for(
            elements,
            {
                PDFSceneElementType.TEXT_GLYPH,
                PDFSceneElementType.TEXT_WORD,
                PDFSceneElementType.TEXT_SPAN,
                PDFSceneElementType.TEXT_LINE,
                PDFSceneElementType.TEXT_BLOCK,
            },
        )
        scene = PDFPageScene(
            scene_id=pdf_scene_id(page_id),
            artifact_version=ContractVersion("1.0.0"),
            document_id=structure_artifact.document_id,
            page_id=page_id,
            page_index=page_index,
            geometry=geometry,
            elements=elements,
            ordered_element_ids=ordered_ids,
            text_element_ids=text_ids,
            image_element_ids=_ids_for(elements, {PDFSceneElementType.IMAGE}),
            vector_element_ids=_ids_for(elements, {PDFSceneElementType.VECTOR}),
            clipping_path_ids=_ids_for(elements, {PDFSceneElementType.CLIPPING_PATH}),
            link_ids=_ids_for(elements, {PDFSceneElementType.LINK}),
            annotation_ids=_ids_for(elements, {PDFSceneElementType.ANNOTATION}),
            form_widget_ids=_ids_for(elements, {PDFSceneElementType.FORM_WIDGET}),
            layer_ids=tuple(layer.layer_id for layer in _layers_for_page(interactive_artifact)),
            relations=tuple(relations),
            resource_references=_resource_references(
                structure_artifact,
                page_id,
                elements,
            ),
            warnings=tuple(warnings),
            limitations=_limitations(
                text_artifact,
                image_artifact,
                vector_artifact,
                interactive_artifact,
            ),
            provenance=structure_artifact.provenance,
        )
        return replace(scene, statistics=pdf_page_scene_statistics(scene))


def _text_elements(
    page_id: str,
    geometry: PageGeometry,
    artifact: PDFNativeTextArtifact | None,
) -> tuple[PDFVisualElement, ...]:
    if artifact is None:
        return ()
    elements: list[PDFVisualElement] = []
    for layer in artifact.pages:
        if layer.page_reference.stable_id != page_id:
            continue
        elements.extend(_text_block_element(item, geometry, artifact) for item in layer.blocks)
        elements.extend(_text_line_element(item, geometry, artifact) for item in layer.lines)
        elements.extend(_text_span_element(item, geometry, artifact) for item in layer.spans)
        elements.extend(_text_word_element(item, geometry, artifact) for item in layer.words)
        elements.extend(_text_glyph_element(item, geometry, artifact) for item in layer.glyphs)
    return tuple(elements)


def _text_block_element(
    block: NativeTextBlock,
    geometry: PageGeometry,
    artifact: PDFNativeTextArtifact,
) -> PDFVisualElement:
    return _visual_element(
        PDFSceneElementType.TEXT_BLOCK,
        block.page_id,
        block.block_id,
        "PDFNativeTextArtifact",
        "text_block",
        geometry,
        bounding_box=block.bounding_box,
        native_order=block.source_order or block.provider_order,
        visibility=PDFSceneVisibility.VISIBLE,
        fidelity=PDFSceneFidelity.PROVIDER_RECONSTRUCTED,
        provenance=block.provenance or artifact.provenance,
    )


def _text_line_element(
    line: NativeTextLine,
    geometry: PageGeometry,
    artifact: PDFNativeTextArtifact,
) -> PDFVisualElement:
    return _visual_element(
        PDFSceneElementType.TEXT_LINE,
        line.page_id,
        line.line_id,
        "PDFNativeTextArtifact",
        "text_line",
        geometry,
        bounding_box=line.bounding_box,
        native_order=line.source_order or line.provider_order,
        visibility=PDFSceneVisibility.VISIBLE,
        fidelity=PDFSceneFidelity.PROVIDER_RECONSTRUCTED,
        provenance=line.provenance or artifact.provenance,
    )


def _text_span_element(
    span: NativeTextSpan,
    geometry: PageGeometry,
    artifact: PDFNativeTextArtifact,
) -> PDFVisualElement:
    resources = tuple(item for item in (span.font_id, span.style_id) if item)
    return _visual_element(
        PDFSceneElementType.TEXT_SPAN,
        span.page_id,
        span.span_id,
        "PDFNativeTextArtifact",
        "text_span",
        geometry,
        bounding_box=span.bounding_box,
        quad=span.quad,
        paint_order=span.paint_order,
        native_order=span.source_order or span.provider_order,
        resource_references=resources,
        visibility=PDFSceneVisibility.VISIBLE,
        fidelity=PDFSceneFidelity.NATIVE_NORMALIZED,
        editability_hint=PDFSceneEditabilityHint.PARTIALLY_EDITABLE,
        provenance=span.provenance or artifact.provenance,
    )


def _text_word_element(
    word: NativeWord,
    geometry: PageGeometry,
    artifact: PDFNativeTextArtifact,
) -> PDFVisualElement:
    return _visual_element(
        PDFSceneElementType.TEXT_WORD,
        word.page_id,
        word.word_id,
        "PDFNativeTextArtifact",
        "text_word",
        geometry,
        bounding_box=word.bounding_box,
        quad=word.quad,
        native_order=word.source_order or word.provider_order,
        visibility=PDFSceneVisibility.VISIBLE,
        fidelity=PDFSceneFidelity.EIXO_DERIVED,
        editability_hint=PDFSceneEditabilityHint.PARTIALLY_EDITABLE,
        provenance=word.provenance or artifact.provenance,
    )


def _text_glyph_element(
    glyph: NativeGlyph,
    geometry: PageGeometry,
    artifact: PDFNativeTextArtifact,
) -> PDFVisualElement:
    visibility = (
        PDFSceneVisibility.VISIBLE
        if glyph.visibility == PDFNativeTextVisibility.VISIBLE
        else PDFSceneVisibility.INVISIBLE
    )
    resources = tuple(item for item in (glyph.font_id, glyph.style_id) if item)
    return _visual_element(
        PDFSceneElementType.TEXT_GLYPH,
        glyph.page_id,
        glyph.glyph_id,
        "PDFNativeTextArtifact",
        "text_glyph",
        geometry,
        bounding_box=glyph.bounding_box,
        quad=glyph.quad,
        local_transform=glyph.text_matrix,
        effective_transform=glyph.effective_transform,
        paint_order=glyph.paint_order,
        native_order=glyph.source_order or glyph.provider_order,
        resource_references=resources,
        visibility=visibility,
        fidelity=PDFSceneFidelity.NATIVE_EXACT,
        editability_hint=PDFSceneEditabilityHint.PARTIALLY_EDITABLE,
        provenance=glyph.provenance or artifact.provenance,
    )


def _image_elements(
    page_id: str,
    geometry: PageGeometry,
    artifact: PDFNativeImageArtifact | None,
) -> tuple[PDFVisualElement, ...]:
    if artifact is None:
        return ()
    return tuple(
        _image_element(item, geometry, artifact)
        for item in artifact.image_catalog.occurrences_for_page(page_id)
    )


def _image_element(
    occurrence: PDFImageOccurrence,
    geometry: PageGeometry,
    artifact: PDFNativeImageArtifact,
) -> PDFVisualElement:
    visibility = (
        PDFSceneVisibility.VISIBLE
        if occurrence.visibility == PDFImageVisibility.VISIBLE
        else PDFSceneVisibility.PARTIALLY_VISIBLE
    )
    resources = (occurrence.image_resource_id,) + tuple(
        item
        for item in (
            occurrence.graphics_state_reference.resource_id
            if occurrence.graphics_state_reference
            else None,
            occurrence.source_reference.resource_id if occurrence.source_reference else None,
        )
        if item
    )
    return _visual_element(
        PDFSceneElementType.IMAGE,
        occurrence.page_id,
        occurrence.occurrence_id,
        "PDFNativeImageArtifact",
        "image_occurrence",
        geometry,
        bounding_box=occurrence.bounding_box,
        normalized_bounding_box=occurrence.normalized_bounding_box,
        quad=occurrence.quad,
        local_transform=occurrence.local_transform,
        effective_transform=occurrence.effective_transform,
        paint_order=occurrence.paint_order,
        native_order=occurrence.operation_order or occurrence.content_stream_order,
        opacity=occurrence.opacity,
        blend_mode=occurrence.blend_mode,
        clip_path_reference=occurrence.clip_path_reference,
        layer_reference=(
            occurrence.layer_reference.resource_id if occurrence.layer_reference else None
        ),
        resource_references=resources,
        visibility=visibility,
        fidelity=PDFSceneFidelity.NATIVE_NORMALIZED,
        editability_hint=PDFSceneEditabilityHint.RASTER_ONLY,
        provenance=occurrence.provenance or artifact.provenance,
    )


def _vector_elements(
    page_id: str,
    geometry: PageGeometry,
    artifact: PDFNativeVectorArtifact | None,
) -> tuple[PDFVisualElement, ...]:
    if artifact is None:
        return ()
    vectors = tuple(
        _vector_element(item, geometry, artifact)
        for item in artifact.vectors_for_page(page_id)
    )
    clips = tuple(
        _clip_element(item, geometry, artifact)
        for item in artifact.clipping_for_page(page_id)
    )
    return vectors + clips


def _vector_element(
    vector: PDFVectorPath,
    geometry: PageGeometry,
    artifact: PDFNativeVectorArtifact,
) -> PDFVisualElement:
    visibility = (
        PDFSceneVisibility.VISIBLE
        if vector.visibility == PDFVectorVisibility.VISIBLE
        else PDFSceneVisibility.NOT_PAINTED
    )
    resources = tuple(
        item
        for item in (
            vector.graphics_state_id,
            vector.graphics_state_reference.resource_id
            if vector.graphics_state_reference
            else None,
        )
        if item
    )
    return _visual_element(
        PDFSceneElementType.VECTOR,
        vector.page_id,
        vector.vector_id,
        "PDFNativeVectorArtifact",
        "vector_path",
        geometry,
        bounding_box=vector.bounding_box,
        normalized_bounding_box=vector.normalized_bounding_box,
        path_reference=vector.vector_id,
        local_transform=vector.local_transform,
        effective_transform=vector.effective_transform,
        paint_order=vector.paint_order,
        clip_path_reference=vector.clip_path_reference,
        layer_reference=(
            vector.parent_form_reference.resource_id if vector.parent_form_reference else None
        ),
        resource_references=resources,
        visibility=visibility,
        fidelity=PDFSceneFidelity.PROVIDER_RECONSTRUCTED,
        editability_hint=PDFSceneEditabilityHint.RECONSTRUCTION_REQUIRED,
        provenance=vector.provenance or artifact.provenance,
    )


def _clip_element(
    clip: PDFClippingPath,
    geometry: PageGeometry,
    artifact: PDFNativeVectorArtifact,
) -> PDFVisualElement:
    return _visual_element(
        PDFSceneElementType.CLIPPING_PATH,
        clip.page_id,
        clip.clip_path_id,
        "PDFNativeVectorArtifact",
        "clipping_path",
        geometry,
        bounding_box=clip.bounding_box or clip.effective_clip_bounds,
        path_reference=clip.clip_path_id,
        effective_transform=clip.transform,
        clip_path_reference=clip.parent_clip_path_id,
        clip_chain=clip.clip_chain,
        visibility=PDFSceneVisibility.NOT_PAINTED,
        fidelity=PDFSceneFidelity.PROVIDER_RECONSTRUCTED,
        editability_hint=PDFSceneEditabilityHint.UNKNOWN,
        provenance=clip.provenance or artifact.provenance,
    )


def _interactive_elements(
    page_id: str,
    geometry: PageGeometry,
    artifact: PDFInteractiveArtifact | None,
    options: PDFPageSceneOptions,
) -> tuple[PDFVisualElement, ...]:
    if artifact is None or not options.include_logical_interactive_elements:
        return ()
    items: list[PDFVisualElement] = []
    items.extend(
        _link_element(link, geometry, artifact)
        for link in artifact.links_for_page(page_id)
    )
    items.extend(
        _annotation_element(annotation, geometry, artifact)
        for annotation in artifact.annotations
        if annotation.page_id == page_id
    )
    items.extend(
        _widget_element(widget, geometry, artifact)
        for widget in artifact.widgets
        if widget.page_id == page_id
    )
    return tuple(items)


def _link_element(
    link: PDFLink,
    geometry: PageGeometry,
    artifact: PDFInteractiveArtifact,
) -> PDFVisualElement:
    return _visual_element(
        PDFSceneElementType.LINK,
        link.page_id,
        link.link_id,
        "PDFInteractiveArtifact",
        "link",
        geometry,
        bounding_box=link.bounding_box,
        normalized_bounding_box=link.normalized_bounding_box,
        layer_reference=link.layer_reference.resource_id if link.layer_reference else None,
        visibility=_interactive_visibility(link.visibility),
        fidelity=PDFSceneFidelity.NATIVE_NORMALIZED,
        provenance=link.provenance or artifact.provenance,
    )


def _annotation_element(
    annotation: PDFAnnotation,
    geometry: PageGeometry,
    artifact: PDFInteractiveArtifact,
) -> PDFVisualElement:
    return _visual_element(
        PDFSceneElementType.ANNOTATION,
        annotation.page_id,
        annotation.annotation_id,
        "PDFInteractiveArtifact",
        "annotation",
        geometry,
        bounding_box=annotation.bounding_box,
        normalized_bounding_box=annotation.normalized_bounding_box,
        layer_reference=(
            annotation.layer_reference.resource_id if annotation.layer_reference else None
        ),
        visibility=_interactive_visibility(annotation.visibility),
        opacity=annotation.opacity,
        fidelity=PDFSceneFidelity.NATIVE_NORMALIZED,
        provenance=annotation.provenance or artifact.provenance,
    )


def _widget_element(
    widget: PDFFormWidget,
    geometry: PageGeometry,
    artifact: PDFInteractiveArtifact,
) -> PDFVisualElement:
    return _visual_element(
        PDFSceneElementType.FORM_WIDGET,
        widget.page_id,
        widget.widget_id,
        "PDFInteractiveArtifact",
        "form_widget",
        geometry,
        bounding_box=widget.bounding_box,
        normalized_bounding_box=widget.normalized_bounding_box,
        layer_reference=widget.layer_reference.resource_id if widget.layer_reference else None,
        visibility=_interactive_visibility(widget.visibility),
        fidelity=PDFSceneFidelity.NATIVE_NORMALIZED,
        editability_hint=PDFSceneEditabilityHint.PARTIALLY_EDITABLE,
        provenance=widget.provenance or artifact.provenance,
    )


def _visual_element(
    element_type: PDFSceneElementType,
    page_id: str,
    source_element_id: str,
    source_artifact_id: str,
    source_element_type: str,
    geometry: PageGeometry,
    *,
    bounding_box: BoundingBox | None = None,
    normalized_bounding_box=None,
    quad=None,
    path_reference: str | None = None,
    local_transform=None,
    effective_transform=None,
    paint_order=None,
    native_order: int | None = None,
    opacity: float | None = None,
    blend_mode: str | None = None,
    clip_path_reference: str | None = None,
    clip_chain: tuple[str, ...] = (),
    layer_reference: str | None = None,
    resource_references: tuple[str, ...] = (),
    visibility: PDFSceneVisibility = PDFSceneVisibility.UNKNOWN,
    fidelity: PDFSceneFidelity = PDFSceneFidelity.UNKNOWN,
    editability_hint: PDFSceneEditabilityHint = PDFSceneEditabilityHint.UNKNOWN,
    provenance=None,
) -> PDFVisualElement:
    return PDFVisualElement(
        element_id=pdf_scene_element_id(element_type, page_id, source_element_id),
        element_type=element_type,
        page_id=page_id,
        source_references=(
            PDFSceneSourceReference(
                source_artifact_id=source_artifact_id,
                source_element_id=source_element_id,
                source_element_type=source_element_type,
                provider=str(provenance.provider_id) if provenance else None,
                provider_version=str(provenance.provider_version) if provenance else None,
            ),
        ),
        bounding_box=bounding_box,
        normalized_bounding_box=normalized_bounding_box
        or _normalized_box(geometry, bounding_box),
        quad=quad,
        path_reference=path_reference,
        local_transform=local_transform,
        effective_transform=effective_transform,
        paint_order=paint_order,
        native_order=native_order,
        order_method=_order_method(paint_order, native_order),
        order_confidence=_order_confidence(paint_order, native_order),
        visibility=visibility,
        opacity=opacity,
        blend_mode=blend_mode,
        clip_path_reference=clip_path_reference,
        clip_chain=clip_chain,
        layer_reference=layer_reference,
        resource_references=tuple(sorted(set(resource_references))),
        fidelity=fidelity,
        editability_hint=editability_hint,
        provenance=provenance,
    )


def _normalized_box(geometry: PageGeometry, box: BoundingBox | None):
    if box is None:
        return None
    try:
        return geometry.normalize_box(box, clamp=True)
    except ValueError:
        return None


def _order_method(paint_order, native_order: int | None) -> PDFSceneOrderMethod:
    if paint_order is not None and paint_order.global_paint_order is not None:
        return PDFSceneOrderMethod.GLOBAL_PAINT_ORDER
    if paint_order is not None and paint_order.local_paint_order is not None:
        return PDFSceneOrderMethod.LOCAL_PAINT_ORDER
    if paint_order is not None and paint_order.operation_index is not None:
        return PDFSceneOrderMethod.CONTENT_STREAM_ORDER
    if native_order is not None:
        return PDFSceneOrderMethod.ELEMENT_COLLECTION_ORDER
    return PDFSceneOrderMethod.UNAVAILABLE


def _order_confidence(paint_order, native_order: int | None) -> PDFSceneOrderConfidence:
    if paint_order is None:
        return PDFSceneOrderConfidence.DERIVED if native_order is not None else (
            PDFSceneOrderConfidence.UNAVAILABLE
        )
    mapping = {
        PDFPaintOrderConfidence.EXACT: PDFSceneOrderConfidence.EXACT,
        PDFPaintOrderConfidence.HIGH: PDFSceneOrderConfidence.HIGH,
        PDFPaintOrderConfidence.PARTIAL: PDFSceneOrderConfidence.PARTIAL,
        PDFPaintOrderConfidence.PROVIDER_APPROXIMATION: (
            PDFSceneOrderConfidence.PROVIDER_APPROXIMATION
        ),
        PDFPaintOrderConfidence.UNAVAILABLE: PDFSceneOrderConfidence.UNAVAILABLE,
    }
    return mapping.get(paint_order.confidence, PDFSceneOrderConfidence.UNAVAILABLE)


def _apply_scene_order(elements: tuple[PDFVisualElement, ...]) -> tuple[PDFVisualElement, ...]:
    ordered = sorted(
        (item for item in elements if _has_order(item)),
        key=_order_key,
    )
    order_by_id = {item.element_id: index for index, item in enumerate(ordered)}
    return tuple(
        replace(item, scene_order=order_by_id.get(item.element_id))
        if item.element_id in order_by_id
        else item
        for item in elements
    )


def _has_order(element: PDFVisualElement) -> bool:
    return (
        element.paint_order is not None
        and (
            element.paint_order.global_paint_order is not None
            or element.paint_order.local_paint_order is not None
            or element.paint_order.operation_index is not None
        )
    ) or element.native_order is not None


def _order_key(element: PDFVisualElement) -> tuple[int, int, int, str]:
    paint_order = element.paint_order
    global_order = paint_order.global_paint_order if paint_order else None
    local_order = paint_order.local_paint_order if paint_order else None
    operation_order = paint_order.operation_index if paint_order else None
    return (
        global_order if global_order is not None else 2_000_000_000,
        local_order if local_order is not None else 2_000_000_000,
        operation_order if operation_order is not None else element.native_order or 0,
        element.element_id,
    )


def _relations(
    elements: tuple[PDFVisualElement, ...],
    interactive_artifact: PDFInteractiveArtifact | None,
) -> tuple[PDFSceneRelation, ...]:
    relations: list[PDFSceneRelation] = []
    for element in elements:
        for source in element.source_references:
            relations.append(
                _relation(
                    PDFSceneRelationType.DERIVED_FROM,
                    element.element_id,
                    source.source_element_id,
                )
            )
        for resource_id in element.resource_references:
            relation_type = _resource_relation_type(element, resource_id)
            relations.append(_relation(relation_type, element.element_id, resource_id))
        if element.clip_path_reference is not None:
            relations.append(
                _relation(
                    PDFSceneRelationType.CLIPPED_BY,
                    element.element_id,
                    element.clip_path_reference,
                )
            )
        if element.layer_reference is not None:
            relations.append(
                _relation(
                    PDFSceneRelationType.BELONGS_TO_LAYER,
                    element.element_id,
                    element.layer_reference,
                )
            )
    if interactive_artifact is not None:
        field_by_widget = {
            widget.widget_id: widget.field_id
            for widget in interactive_artifact.widgets
            if widget.field_id is not None
        }
        link_destinations = {
            link.link_id: link.destination_reference or link.uri
            for link in interactive_artifact.links
            if link.destination_reference is not None or link.uri is not None
        }
        for element in elements:
            source_id = element.source_references[0].source_element_id
            if source_id in field_by_widget:
                relations.append(
                    _relation(
                        PDFSceneRelationType.WIDGET_OF,
                        element.element_id,
                        field_by_widget[source_id],
                    )
                )
            if source_id in link_destinations:
                relations.append(
                    _relation(
                        PDFSceneRelationType.LINKS_TO,
                        element.element_id,
                        link_destinations[source_id] or "unknown",
                    )
                )
    ordered = tuple(item for item in elements if item.scene_order is not None)
    ordered = tuple(sorted(ordered, key=lambda item: item.scene_order or 0))
    for before, after in zip(ordered, ordered[1:]):
        relations.append(
            _relation(
                PDFSceneRelationType.PAINTED_BEFORE,
                before.element_id,
                after.element_id,
            )
        )
    return tuple(_dedupe_relations(relations))


def _resource_relation_type(
    element: PDFVisualElement,
    resource_id: str,
) -> PDFSceneRelationType:
    if resource_id.startswith("pdffont:") or element.element_type.value.startswith("text"):
        return PDFSceneRelationType.USES_FONT
    if resource_id.startswith("pdfimage:") or element.element_type == PDFSceneElementType.IMAGE:
        return PDFSceneRelationType.USES_IMAGE
    if resource_id.startswith("pdfgstate:"):
        return PDFSceneRelationType.USES_GRAPHICS_STATE
    return PDFSceneRelationType.USES_RESOURCE


def _relation(
    relation_type: PDFSceneRelationType,
    source_id: str,
    target_id: str,
) -> PDFSceneRelation:
    return PDFSceneRelation(
        relation_id=pdf_scene_relation_id(relation_type, source_id, target_id),
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
    )


def _dedupe_relations(
    relations: list[PDFSceneRelation],
) -> tuple[PDFSceneRelation, ...]:
    seen: set[str] = set()
    result: list[PDFSceneRelation] = []
    for relation in relations:
        if relation.relation_id in seen:
            continue
        seen.add(relation.relation_id)
        result.append(relation)
    return tuple(result)


def _deduplicate(
    elements: list[PDFVisualElement],
) -> tuple[list[PDFVisualElement], tuple[EixoWarning, ...]]:
    seen: set[str] = set()
    result: list[PDFVisualElement] = []
    warnings: list[EixoWarning] = []
    for element in elements:
        if element.element_id in seen:
            warnings.append(
                EixoWarning(
                    code="scene_duplicate_element_id",
                    message="Duplicate scene element id was ignored.",
                    scope=element.element_id,
                )
            )
            continue
        seen.add(element.element_id)
        result.append(element)
    return result, tuple(warnings)


def _ids_for(
    elements: tuple[PDFVisualElement, ...],
    types: set[PDFSceneElementType],
) -> tuple[str, ...]:
    return tuple(item.element_id for item in elements if item.element_type in types)


def _resource_references(
    structure_artifact: PDFInternalStructureArtifact,
    page_id: str,
    elements: tuple[PDFVisualElement, ...],
) -> tuple[str, ...]:
    resources = {resource for element in elements for resource in element.resource_references}
    for page in structure_artifact.pages:
        if page.page_reference.stable_id != page_id:
            continue
        resources.update(item.resource_id for item in page.own_resources)
        resources.update(item.resource_id for item in page.inherited_resources)
        resources.update(item.resource_id for item in page.layer_references)
    return tuple(sorted(resources))


def _layers_for_page(
    interactive_artifact: PDFInteractiveArtifact | None,
) -> tuple[PDFLayer, ...]:
    return interactive_artifact.layers if interactive_artifact is not None else ()


def _interactive_visibility(
    visibility: PDFInteractiveVisibility,
) -> PDFSceneVisibility:
    if visibility == PDFInteractiveVisibility.VISIBLE:
        return PDFSceneVisibility.VISIBLE
    if visibility in {
        PDFInteractiveVisibility.HIDDEN,
        PDFInteractiveVisibility.HIDDEN_BY_LAYER,
        PDFInteractiveVisibility.NO_VIEW,
    }:
        return PDFSceneVisibility.HIDDEN
    return PDFSceneVisibility.UNKNOWN


def _selected_pages(page_count: int, selection: tuple[int, ...] | None) -> tuple[int, ...]:
    if selection is None:
        return tuple(range(page_count))
    return tuple(page for page in selection if 0 <= page < page_count)


def _compatibility_warnings(
    structure_artifact: PDFInternalStructureArtifact,
    *artifacts: object | None,
) -> list[EixoWarning]:
    warnings: list[EixoWarning] = []
    document_id = structure_artifact.document_id
    for artifact in artifacts:
        if artifact is None or document_id is None:
            continue
        artifact_document_id = getattr(artifact, "document_id", None)
        if artifact_document_id is not None and artifact_document_id != document_id:
            warnings.append(
                EixoWarning(
                    code="scene_source_artifact_document_mismatch",
                    message="Source artifact document_id differs from structure artifact.",
                    scope=artifact.__class__.__name__,
                )
            )
    return warnings


def _source_artifact_references(
    structure_artifact: PDFInternalStructureArtifact,
    *artifacts: object | None,
) -> tuple[PDFSceneSourceReference, ...]:
    references = [
        PDFSceneSourceReference(
            source_artifact_id="PDFInternalStructureArtifact",
            source_element_id="pdfresourcecatalog:document",
            source_element_type="resource_catalog",
            provider=str(structure_artifact.provider.provider_id),
            provider_version=str(structure_artifact.provider.provider_version),
        )
    ]
    for artifact in artifacts:
        if artifact is None:
            continue
        provider = getattr(artifact, "provider", None)
        references.append(
            PDFSceneSourceReference(
                source_artifact_id=artifact.__class__.__name__,
                source_element_id=artifact.__class__.__name__,
                source_element_type="artifact",
                provider=str(provider.provider_id) if provider is not None else None,
                provider_version=str(provider.provider_version)
                if provider is not None
                else None,
            )
        )
    return tuple(references)


def _provider(
    structure_artifact: PDFInternalStructureArtifact,
    *_artifacts: object | None,
):
    return structure_artifact.provider


def _limitations(*artifacts: object | None):
    result = []
    for artifact in artifacts:
        if artifact is None:
            continue
        result.extend(getattr(artifact, "limitations", ()))
    return tuple(result)


__all__ = ["PDFPageSceneBuilder"]
