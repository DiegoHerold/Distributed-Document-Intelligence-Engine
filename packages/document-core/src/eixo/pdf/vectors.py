from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from eixo.core import DocumentId, EixoWarning, ProviderId
from eixo.core.serialization import Serializable
from eixo.core.versions import ContractVersion
from eixo.geometry import AffineMatrix, BoundingBox, NormalizedBoundingBox, Point
from eixo.pdf.models import PDFProviderDescriptor, PDFProviderProvenance, ProviderLimitation
from eixo.pdf.structure import (
    PDFContentStreamReference,
    PDFInternalStructureArtifact,
    PDFOperationReference,
    PDFPageReference,
    PDFPaintOrder,
    PDFPaintOrderConfidence,
    PDFResourceReference,
)


class PDFVectorSupportStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    PROVIDER_DERIVED = "provider_derived"
    HEURISTIC = "heuristic"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"
    EXTRACTION_FAILED = "extraction_failed"


class PDFPathCommandType(StrEnum):
    MOVE_TO = "move_to"
    LINE_TO = "line_to"
    CURVE_TO = "curve_to"
    RECTANGLE = "rectangle"
    CLOSE_PATH = "close_path"
    UNKNOWN = "unknown"


class PDFVectorShapeClassification(StrEnum):
    LINE = "line"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    BEZIER_PATH = "bezier_path"
    COMPOUND_PATH = "compound_path"
    UNKNOWN_PATH = "unknown_path"


class PDFVectorPaintIntent(StrEnum):
    FILL = "fill"
    STROKE = "stroke"
    FILL_AND_STROKE = "fill_and_stroke"
    NONE = "none"
    CLIPPING = "clipping"


class PDFVectorVisibility(StrEnum):
    VISIBLE = "visible"
    PARTIALLY_VISIBLE = "partially_visible"
    FULLY_CLIPPED = "fully_clipped"
    ZERO_OPACITY = "zero_opacity"
    OUTSIDE_CROP_BOX = "outside_crop_box"
    HIDDEN_BY_LAYER = "hidden_by_layer"
    NOT_PAINTED = "not_painted"
    UNKNOWN = "unknown"


class PDFVectorExtractionMethod(StrEnum):
    CONTENT_STREAM_OPERATION = "content_stream_operation"
    PROVIDER_DRAWINGS = "provider_drawings"
    GRAPHICS_STATE_RESOLVER = "graphics_state_resolver"
    HEURISTIC = "heuristic"
    UNSUPPORTED = "unsupported"


class PDFPathFillRule(StrEnum):
    NONZERO = "nonzero"
    EVEN_ODD = "even_odd"
    UNKNOWN = "unknown"


class PDFClippingMethod(StrEnum):
    CONTENT_STREAM_CLIP = "content_stream_clip"
    PROVIDER_CLIP = "provider_clip"
    BOUNDING_BOX_HEURISTIC = "bounding_box_heuristic"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PDFNativeVectorOptions(Serializable):
    include_invisible_vectors: bool = True
    include_clipping_paths: bool = True
    resolve_graphics_state: bool = True
    page_selection: tuple[int, ...] | None = None
    max_paths_per_page: int | None = 100_000
    max_commands_per_path: int | None = 20_000
    max_form_xobject_depth: int | None = 8
    timeout_seconds: float | None = None
    preferred_provider: ProviderId | None = None

    def __post_init__(self) -> None:
        for name in (
            "max_paths_per_page",
            "max_commands_per_path",
            "max_form_xobject_depth",
        ):
            _validate_positive_optional(name, getattr(self, name))
        _validate_positive_optional("timeout_seconds", self.timeout_seconds)
        if self.page_selection is not None and any(page < 0 for page in self.page_selection):
            raise ValueError("page_selection cannot contain negative indexes")

    def safe_options(self) -> dict[str, Any]:
        return {
            "include_invisible_vectors": self.include_invisible_vectors,
            "include_clipping_paths": self.include_clipping_paths,
            "resolve_graphics_state": self.resolve_graphics_state,
            "page_selection": list(self.page_selection) if self.page_selection else None,
            "max_paths_per_page": self.max_paths_per_page,
            "max_commands_per_path": self.max_commands_per_path,
            "max_form_xobject_depth": self.max_form_xobject_depth,
            "timeout_seconds": self.timeout_seconds,
            "preferred_provider": str(self.preferred_provider)
            if self.preferred_provider
            else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.safe_options()


@dataclass(frozen=True, slots=True)
class PDFPathCommand(Serializable):
    command_type: PDFPathCommandType
    command_index: int
    points: tuple[Point, ...] = ()
    control_points: tuple[Point, ...] = ()
    original_points: tuple[Point, ...] = ()
    canonical_points: tuple[Point, ...] = ()
    bounding_box: BoundingBox | None = None
    operation_reference: PDFOperationReference | None = None
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_non_negative_optional("command_index", self.command_index)


@dataclass(frozen=True, slots=True)
class PDFVectorSubpath(Serializable):
    subpath_id: str
    command_ids: tuple[str, ...] = ()
    commands: tuple[PDFPathCommand, ...] = ()
    start_point: Point | None = None
    end_point: Point | None = None
    closed: bool = False
    bounding_box: BoundingBox | None = None
    order: int = 0
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("subpath_id", self.subpath_id)
        _validate_non_negative_optional("order", self.order)


@dataclass(frozen=True, slots=True)
class PDFColorValue(Serializable):
    original_value: tuple[float, ...] = ()
    color_space: str | None = None
    normalized_rgb: tuple[float, float, float] | None = None
    conversion_method: str | None = None
    conversion_confidence: float = 0.0

    def __post_init__(self) -> None:
        _validate_confidence(self.conversion_confidence)


@dataclass(frozen=True, slots=True)
class PDFFillStyle(Serializable):
    enabled: bool = False
    color: PDFColorValue | None = None
    opacity: float | None = None
    blend_mode: str | None = None
    pattern_reference: PDFResourceReference | None = None
    shading_reference: PDFResourceReference | None = None
    fill_rule: PDFPathFillRule = PDFPathFillRule.UNKNOWN
    graphics_state_reference: PDFResourceReference | None = None

    def __post_init__(self) -> None:
        _validate_opacity_optional("opacity", self.opacity)


@dataclass(frozen=True, slots=True)
class PDFStrokeStyle(Serializable):
    enabled: bool = False
    color: PDFColorValue | None = None
    declared_width: float | None = None
    effective_width: float | None = None
    line_cap: int | None = None
    line_join: int | None = None
    miter_limit: float | None = None
    dash_array: tuple[float, ...] = ()
    dash_phase: float | None = None
    opacity: float | None = None
    blend_mode: str | None = None
    pattern_reference: PDFResourceReference | None = None
    shading_reference: PDFResourceReference | None = None
    graphics_state_reference: PDFResourceReference | None = None

    def __post_init__(self) -> None:
        _validate_non_negative_optional("declared_width", self.declared_width)
        _validate_non_negative_optional("effective_width", self.effective_width)
        _validate_non_negative_optional("line_cap", self.line_cap)
        _validate_non_negative_optional("line_join", self.line_join)
        _validate_non_negative_optional("miter_limit", self.miter_limit)
        _validate_non_negative_optional("dash_phase", self.dash_phase)
        _validate_opacity_optional("opacity", self.opacity)
        for value in self.dash_array:
            _validate_non_negative_optional("dash_array", value)


@dataclass(frozen=True, slots=True)
class PDFEffectiveGraphicsState(Serializable):
    graphics_state_id: str
    current_transform: AffineMatrix = field(default_factory=AffineMatrix.identity)
    stroke_width: float | None = 1.0
    line_cap: int | None = None
    line_join: int | None = None
    miter_limit: float | None = None
    dash_array: tuple[float, ...] = ()
    dash_phase: float | None = None
    fill_color: PDFColorValue | None = None
    stroke_color: PDFColorValue | None = None
    fill_opacity: float | None = None
    stroke_opacity: float | None = None
    blend_mode: str | None = None
    soft_mask_reference: PDFResourceReference | None = None
    active_clip_path_id: str | None = None
    resource_reference: PDFResourceReference | None = None
    source_operation_ids: tuple[str, ...] = ()
    partially_resolved: bool = False
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("graphics_state_id", self.graphics_state_id)
        _validate_non_negative_optional("stroke_width", self.stroke_width)
        _validate_opacity_optional("fill_opacity", self.fill_opacity)
        _validate_opacity_optional("stroke_opacity", self.stroke_opacity)


@dataclass(frozen=True, slots=True)
class PDFGraphicsStateResolver(Serializable):
    state_stack: tuple[PDFEffectiveGraphicsState, ...] = field(
        default_factory=lambda: (
            PDFEffectiveGraphicsState(graphics_state_id="pdfgstate:initial"),
        )
    )
    warnings: tuple[EixoWarning, ...] = ()

    @property
    def current_state(self) -> PDFEffectiveGraphicsState:
        return self.state_stack[-1]

    def save(self, operation_id: str | None = None) -> "PDFGraphicsStateResolver":
        return replace(
            self,
            state_stack=self.state_stack + (self.current_state,),
        )._record_operation(operation_id)

    def restore(self, operation_id: str | None = None) -> "PDFGraphicsStateResolver":
        if len(self.state_stack) == 1:
            warning = EixoWarning(
                code="graphics_state_stack_underflow",
                message="Graphics state restore was requested with an empty stack.",
                scope="pdf.vector",
            )
            return replace(self, warnings=self.warnings + (warning,))._record_operation(
                operation_id
            )
        return replace(self, state_stack=self.state_stack[:-1])._record_operation(
            operation_id
        )

    def update(
        self,
        operation_id: str | None = None,
        **changes: object,
    ) -> "PDFGraphicsStateResolver":
        state = replace(self.current_state, **changes)
        return replace(self, state_stack=self.state_stack[:-1] + (state,))._record_operation(
            operation_id
        )

    def _record_operation(
        self,
        operation_id: str | None,
    ) -> "PDFGraphicsStateResolver":
        if operation_id is None:
            return self
        state = replace(
            self.current_state,
            source_operation_ids=self.current_state.source_operation_ids
            + (operation_id,),
        )
        return replace(self, state_stack=self.state_stack[:-1] + (state,))


@dataclass(frozen=True, slots=True)
class PDFClippingPath(Serializable):
    clip_path_id: str
    page_id: str
    subpaths: tuple[PDFVectorSubpath, ...] = ()
    fill_rule: PDFPathFillRule = PDFPathFillRule.UNKNOWN
    transform: AffineMatrix | None = None
    bounding_box: BoundingBox | None = None
    parent_clip_path_id: str | None = None
    clip_chain: tuple[str, ...] = ()
    effective_clip_bounds: BoundingBox | None = None
    content_stream_reference: PDFContentStreamReference | None = None
    operation_references: tuple[PDFOperationReference, ...] = ()
    parent_form_reference: PDFResourceReference | None = None
    form_occurrence_path: tuple[str, ...] = ()
    clip_method: PDFClippingMethod = PDFClippingMethod.UNKNOWN
    clip_confidence: float = 0.0
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("clip_path_id", self.clip_path_id)
        _validate_required_text("page_id", self.page_id)
        _validate_confidence(self.clip_confidence)


@dataclass(frozen=True, slots=True)
class PDFVectorSignal(Serializable):
    signal_type: str
    method: PDFVectorExtractionMethod
    confidence: float = 0.0

    def __post_init__(self) -> None:
        _validate_required_text("signal_type", self.signal_type)
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class PDFVectorPath(Serializable):
    vector_id: str
    page_id: str
    subpaths: tuple[PDFVectorSubpath, ...] = ()
    commands: tuple[PDFPathCommand, ...] = ()
    bounding_box: BoundingBox | None = None
    normalized_bounding_box: NormalizedBoundingBox | None = None
    local_transform: AffineMatrix | None = None
    parent_transform: AffineMatrix | None = None
    effective_transform: AffineMatrix | None = None
    inverse_transform: AffineMatrix | None = None
    fill_style: PDFFillStyle | None = None
    stroke_style: PDFStrokeStyle | None = None
    paint_intent: PDFVectorPaintIntent = PDFVectorPaintIntent.NONE
    shape_classification: PDFVectorShapeClassification = (
        PDFVectorShapeClassification.UNKNOWN_PATH
    )
    graphics_state_reference: PDFResourceReference | None = None
    graphics_state_id: str | None = None
    clip_path_reference: str | None = None
    parent_form_reference: PDFResourceReference | None = None
    form_occurrence_path: tuple[str, ...] = ()
    content_stream_reference: PDFContentStreamReference | None = None
    operation_references: tuple[PDFOperationReference, ...] = ()
    paint_order: PDFPaintOrder | None = None
    visibility: PDFVectorVisibility = PDFVectorVisibility.UNKNOWN
    fidelity: PDFVectorSupportStatus = PDFVectorSupportStatus.UNKNOWN
    signals: tuple[PDFVectorSignal, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("vector_id", self.vector_id)
        _validate_required_text("page_id", self.page_id)


@dataclass(frozen=True, slots=True)
class PDFPageVectorLayer(Serializable):
    page_reference: PDFPageReference
    vector_ids: tuple[str, ...] = ()
    clipping_path_ids: tuple[str, ...] = ()
    ordered_element_ids: tuple[str, ...] = ()
    unresolved_operations: tuple[str, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None


@dataclass(frozen=True, slots=True)
class PDFNativeVectorStatistics(Serializable):
    vector_path_count: int = 0
    line_count: int = 0
    rectangle_count: int = 0
    polygon_count: int = 0
    curve_count: int = 0
    clipping_path_count: int = 0
    unresolved_operation_count: int = 0
    invisible_vector_count: int = 0

    def __post_init__(self) -> None:
        for name in (
            "vector_path_count",
            "line_count",
            "rectangle_count",
            "polygon_count",
            "curve_count",
            "clipping_path_count",
            "unresolved_operation_count",
            "invisible_vector_count",
        ):
            _validate_non_negative_optional(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class PDFVectorCapabilityMatrixEntry(Serializable):
    information: str
    support: PDFVectorSupportStatus
    origin: str
    precision: str | None = None
    limitation: str | None = None

    def __post_init__(self) -> None:
        _validate_required_text("information", self.information)
        _validate_required_text("origin", self.origin)


@dataclass(frozen=True, slots=True)
class PDFNativeVectorArtifact(Serializable):
    artifact_version: ContractVersion
    provider: PDFProviderDescriptor
    document_id: DocumentId | None = None
    source_structure_artifact: PDFInternalStructureArtifact | None = None
    graphics_states: tuple[PDFEffectiveGraphicsState, ...] = ()
    vector_paths: tuple[PDFVectorPath, ...] = ()
    clipping_paths: tuple[PDFClippingPath, ...] = ()
    page_layers: tuple[PDFPageVectorLayer, ...] = ()
    statistics: PDFNativeVectorStatistics = field(
        default_factory=PDFNativeVectorStatistics
    )
    capability_matrix: tuple[PDFVectorCapabilityMatrixEntry, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def vectors_for_page(self, page_id: str) -> tuple[PDFVectorPath, ...]:
        return tuple(vector for vector in self.vector_paths if vector.page_id == page_id)

    def clipping_for_page(self, page_id: str) -> tuple[PDFClippingPath, ...]:
        return tuple(clip for clip in self.clipping_paths if clip.page_id == page_id)

    def vector_by_id(self, vector_id: str) -> PDFVectorPath | None:
        return next(
            (vector for vector in self.vector_paths if vector.vector_id == vector_id),
            None,
        )


def vector_path_id(page_index: int, path_index: int) -> str:
    return f"pdfvector:page-{page_index}:path-{path_index}"


def vector_subpath_id(vector_id: str, subpath_index: int) -> str:
    return f"{vector_id}:subpath-{subpath_index}"


def vector_command_id(vector_id: str, command_index: int) -> str:
    return f"{vector_id}:command-{command_index}"


def clipping_path_id(page_index: int, clip_index: int) -> str:
    return f"pdfclip:page-{page_index}:clip-{clip_index}"


def effective_graphics_state_id(page_index: int, state_index: int) -> str:
    return f"pdfgstate:page-{page_index}:state-{state_index}"


def paint_order_from_provider(index: int) -> PDFPaintOrder:
    return PDFPaintOrder(
        local_paint_order=index,
        global_paint_order=index,
        confidence=PDFPaintOrderConfidence.PROVIDER_APPROXIMATION,
    )


def classify_vector_shape(
    commands: tuple[PDFPathCommand, ...],
    subpaths: tuple[PDFVectorSubpath, ...] = (),
) -> PDFVectorShapeClassification:
    if len(subpaths) > 1:
        return PDFVectorShapeClassification.COMPOUND_PATH
    command_types = tuple(command.command_type for command in commands)
    if not command_types:
        return PDFVectorShapeClassification.UNKNOWN_PATH
    if PDFPathCommandType.CURVE_TO in command_types:
        return PDFVectorShapeClassification.BEZIER_PATH
    if (
        len(commands) == 1
        and commands[0].command_type == PDFPathCommandType.LINE_TO
        and len(commands[0].points) == 2
    ):
        return PDFVectorShapeClassification.LINE
    if command_types == (PDFPathCommandType.MOVE_TO, PDFPathCommandType.LINE_TO):
        return PDFVectorShapeClassification.LINE
    if PDFPathCommandType.RECTANGLE in command_types:
        return PDFVectorShapeClassification.RECTANGLE
    line_count = sum(1 for item in command_types if item == PDFPathCommandType.LINE_TO)
    if line_count >= 2:
        return PDFVectorShapeClassification.POLYGON
    return PDFVectorShapeClassification.UNKNOWN_PATH


def vector_statistics(
    vectors: tuple[PDFVectorPath, ...],
    clipping_paths: tuple[PDFClippingPath, ...] = (),
    unresolved_operation_count: int = 0,
) -> PDFNativeVectorStatistics:
    painted_vectors = tuple(
        vector
        for vector in vectors
        if vector.paint_intent != PDFVectorPaintIntent.CLIPPING
    )
    return PDFNativeVectorStatistics(
        vector_path_count=len(vectors),
        line_count=sum(
            1
            for vector in painted_vectors
            if vector.shape_classification == PDFVectorShapeClassification.LINE
        ),
        rectangle_count=sum(
            1
            for vector in painted_vectors
            if vector.shape_classification == PDFVectorShapeClassification.RECTANGLE
        ),
        polygon_count=sum(
            1
            for vector in painted_vectors
            if vector.shape_classification == PDFVectorShapeClassification.POLYGON
        ),
        curve_count=sum(
            1
            for vector in painted_vectors
            for command in vector.commands
            if command.command_type == PDFPathCommandType.CURVE_TO
        ),
        clipping_path_count=len(clipping_paths),
        unresolved_operation_count=unresolved_operation_count,
        invisible_vector_count=sum(
            1
            for vector in vectors
            if vector.visibility != PDFVectorVisibility.VISIBLE
        ),
    )


def _validate_required_text(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} is required")


def _validate_confidence(value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise ValueError("confidence must be between 0 and 1")


def _validate_positive_optional(name: str, value: int | float | None) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{name} must be positive")


def _validate_non_negative_optional(name: str, value: int | float | None) -> None:
    if value is not None and value < 0:
        raise ValueError(f"{name} cannot be negative")


def _validate_opacity_optional(name: str, value: float | None) -> None:
    if value is not None and (value < 0.0 or value > 1.0):
        raise ValueError(f"{name} must be between 0 and 1")


__all__ = [
    "PDFClippingMethod",
    "PDFClippingPath",
    "PDFColorValue",
    "PDFEffectiveGraphicsState",
    "PDFFillStyle",
    "PDFGraphicsStateResolver",
    "PDFNativeVectorArtifact",
    "PDFNativeVectorOptions",
    "PDFNativeVectorStatistics",
    "PDFPageVectorLayer",
    "PDFPathCommand",
    "PDFPathCommandType",
    "PDFPathFillRule",
    "PDFStrokeStyle",
    "PDFVectorCapabilityMatrixEntry",
    "PDFVectorExtractionMethod",
    "PDFVectorPaintIntent",
    "PDFVectorPath",
    "PDFVectorShapeClassification",
    "PDFVectorSignal",
    "PDFVectorSubpath",
    "PDFVectorSupportStatus",
    "PDFVectorVisibility",
    "classify_vector_shape",
    "clipping_path_id",
    "effective_graphics_state_id",
    "paint_order_from_provider",
    "vector_command_id",
    "vector_path_id",
    "vector_statistics",
    "vector_subpath_id",
]
