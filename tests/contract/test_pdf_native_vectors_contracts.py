from __future__ import annotations

import pytest

from eixo import (
    AffineMatrix,
    BoundingBox,
    PDFClippingMethod,
    PDFClippingPath,
    PDFColorValue,
    PDFEffectiveGraphicsState,
    PDFFillStyle,
    PDFGraphicsStateResolver,
    PDFNativeVectorArtifact,
    PDFNativeVectorOptions,
    PDFPageReference,
    PDFPageVectorLayer,
    PDFPathCommand,
    PDFPathCommandType,
    PDFPathFillRule,
    PDFPaintOrder,
    PDFPaintOrderConfidence,
    PDFProviderCapabilities,
    PDFProviderDescriptor,
    PDFStrokeStyle,
    PDFSupportLevel,
    PDFVectorExtractionMethod,
    PDFVectorPaintIntent,
    PDFVectorPath,
    PDFVectorShapeClassification,
    PDFVectorSignal,
    PDFVectorSubpath,
    PDFVectorSupportStatus,
    PDFVectorVisibility,
    Point,
    classify_vector_shape,
    clipping_path_id,
    effective_graphics_state_id,
    vector_path_id,
    vector_statistics,
    vector_subpath_id,
)
from eixo.core import ContractVersion, EixoWarning, ProviderId, ProviderVersion


def test_vector_commands_preserve_geometry_and_curves() -> None:
    commands = (
        PDFPathCommand(
            command_type=PDFPathCommandType.MOVE_TO,
            command_index=0,
            points=(Point(10, 10),),
        ),
        PDFPathCommand(
            command_type=PDFPathCommandType.CURVE_TO,
            command_index=1,
            points=(Point(10, 10), Point(40, 10)),
            control_points=(Point(20, 0), Point(30, 20)),
        ),
        PDFPathCommand(
            command_type=PDFPathCommandType.CLOSE_PATH,
            command_index=2,
        ),
    )
    subpath = PDFVectorSubpath(
        subpath_id=vector_subpath_id("v", 0),
        commands=commands,
        start_point=Point(10, 10),
        end_point=Point(40, 10),
        closed=True,
        bounding_box=BoundingBox(10, 0, 40, 20),
    )

    assert commands[1].control_points == (Point(20, 0), Point(30, 20))
    assert classify_vector_shape(commands, (subpath,)) == (
        PDFVectorShapeClassification.BEZIER_PATH
    )
    assert subpath.closed is True


def test_fill_stroke_state_and_clipping_are_separate() -> None:
    fill = PDFFillStyle(
        enabled=True,
        color=PDFColorValue(
            original_value=(0.2, 0.3, 0.4),
            color_space="DeviceRGB",
            normalized_rgb=(0.2, 0.3, 0.4),
            conversion_method="provider_passthrough",
            conversion_confidence=1.0,
        ),
        opacity=0.75,
        blend_mode="Multiply",
        fill_rule=PDFPathFillRule.NONZERO,
    )
    stroke = PDFStrokeStyle(
        enabled=True,
        color=PDFColorValue(original_value=(0.0, 0.0, 0.0), color_space="DeviceRGB"),
        declared_width=2.0,
        effective_width=3.0,
        line_cap=1,
        line_join=2,
        dash_array=(3.0, 1.0),
        dash_phase=0.0,
        opacity=0.5,
    )
    state = PDFEffectiveGraphicsState(
        graphics_state_id=effective_graphics_state_id(0, 0),
        current_transform=AffineMatrix.translation(5, 6),
        stroke_width=2.0,
        fill_color=fill.color,
        stroke_color=stroke.color,
        fill_opacity=fill.opacity,
        stroke_opacity=stroke.opacity,
        blend_mode=fill.blend_mode,
    )
    clip = PDFClippingPath(
        clip_path_id=clipping_path_id(0, 0),
        page_id="pdfpage:0",
        fill_rule=PDFPathFillRule.NONZERO,
        bounding_box=BoundingBox(0, 0, 100, 100),
        clip_method=PDFClippingMethod.PROVIDER_CLIP,
        clip_confidence=0.5,
    )

    assert state.current_transform.e == 5
    assert stroke.declared_width == 2.0
    assert stroke.effective_width == 3.0
    assert clip.bounding_box == BoundingBox(0, 0, 100, 100)


def test_graphics_state_resolver_preserves_stack_and_underflow_warning() -> None:
    resolver = PDFGraphicsStateResolver()
    saved = resolver.save("op-save").update("op-width", stroke_width=4.0)
    restored = saved.restore("op-restore")
    underflow = resolver.restore("op-underflow")

    assert saved.current_state.stroke_width == 4.0
    assert restored.current_state.stroke_width == 1.0
    assert underflow.warnings[0].code == "graphics_state_stack_underflow"


def test_vector_artifact_is_serializable_and_counts_shapes() -> None:
    provider = PDFProviderDescriptor(
        provider_id=ProviderId("prov_vector_contract"),
        name="Vector Provider",
        provider_version=ProviderVersion("0.1.0"),
        backend_name="ContractPDF",
        backend_version="0.1.0",
        capabilities=PDFProviderCapabilities(
            supports_vector_extraction=PDFSupportLevel.PARTIAL
        ),
    )
    page = PDFPageReference(page_index=0, page_number=1)
    command = PDFPathCommand(
        command_type=PDFPathCommandType.RECTANGLE,
        command_index=0,
        points=BoundingBox(10, 10, 40, 30).corners,
        bounding_box=BoundingBox(10, 10, 40, 30),
    )
    subpath = PDFVectorSubpath(
        subpath_id=vector_subpath_id(vector_path_id(0, 0), 0),
        commands=(command,),
        bounding_box=BoundingBox(10, 10, 40, 30),
    )
    vector = PDFVectorPath(
        vector_id=vector_path_id(0, 0),
        page_id=page.stable_id,
        subpaths=(subpath,),
        commands=(command,),
        bounding_box=BoundingBox(10, 10, 40, 30),
        fill_style=PDFFillStyle(enabled=True),
        paint_intent=PDFVectorPaintIntent.FILL,
        shape_classification=PDFVectorShapeClassification.RECTANGLE,
        paint_order=PDFPaintOrder(
            global_paint_order=0,
            confidence=PDFPaintOrderConfidence.PROVIDER_APPROXIMATION,
        ),
        visibility=PDFVectorVisibility.VISIBLE,
        fidelity=PDFVectorSupportStatus.PROVIDER_DERIVED,
        signals=(
            PDFVectorSignal(
                signal_type="possible_background_shape",
                method=PDFVectorExtractionMethod.HEURISTIC,
                confidence=0.4,
            ),
        ),
        warnings=(
            EixoWarning(
                code="paint_order_unavailable",
                message="Example warning",
                scope="pdf.vector",
            ),
        ),
    )
    stats = vector_statistics((vector,))
    artifact = PDFNativeVectorArtifact(
        artifact_version=ContractVersion("1.0.0"),
        provider=provider,
        vector_paths=(vector,),
        page_layers=(
            PDFPageVectorLayer(
                page_reference=page,
                vector_ids=(vector.vector_id,),
                ordered_element_ids=(vector.vector_id,),
            ),
        ),
        statistics=stats,
    )

    assert stats.vector_path_count == 1
    assert stats.rectangle_count == 1
    assert artifact.vector_by_id(vector.vector_id) is vector
    assert artifact.to_dict()["vector_paths"][0]["commands"][0]["command_type"] == (
        "rectangle"
    )


def test_vector_options_validate_limits() -> None:
    with pytest.raises(ValueError):
        PDFNativeVectorOptions(page_selection=(-1,))
    with pytest.raises(ValueError):
        PDFNativeVectorOptions(max_paths_per_page=0)
