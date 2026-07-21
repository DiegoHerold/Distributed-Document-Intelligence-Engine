from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from eixo.core import DocumentId, EixoWarning
from eixo.core.serialization import Serializable
from eixo.core.versions import ContractVersion
from eixo.geometry import (
    AffineMatrix,
    BoundingBox,
    NormalizedBoundingBox,
    PageGeometry,
    Polygon,
    Quad,
)
from eixo.pdf.models import PDFProviderDescriptor, PDFProviderProvenance, ProviderLimitation
from eixo.pdf.structure import PDFPaintOrder


class PDFSceneElementType(StrEnum):
    TEXT_GLYPH = "text_glyph"
    TEXT_WORD = "text_word"
    TEXT_SPAN = "text_span"
    TEXT_LINE = "text_line"
    TEXT_BLOCK = "text_block"
    IMAGE = "image"
    VECTOR = "vector"
    CLIPPING_PATH = "clipping_path"
    LINK = "link"
    ANNOTATION = "annotation"
    FORM_WIDGET = "form_widget"
    UNKNOWN = "unknown"


class PDFSceneVisibility(StrEnum):
    VISIBLE = "visible"
    HIDDEN = "hidden"
    PARTIALLY_VISIBLE = "partially_visible"
    INVISIBLE = "invisible"
    NOT_PAINTED = "not_painted"
    UNKNOWN = "unknown"


class PDFSceneOrderMethod(StrEnum):
    GLOBAL_PAINT_ORDER = "global_paint_order"
    LOCAL_PAINT_ORDER = "local_paint_order"
    CONTENT_STREAM_ORDER = "content_stream_order"
    INTERACTIVE_ORDER = "interactive_order"
    ELEMENT_COLLECTION_ORDER = "element_collection_order"
    UNAVAILABLE = "unavailable"


class PDFSceneOrderConfidence(StrEnum):
    EXACT = "exact"
    HIGH = "high"
    PARTIAL = "partial"
    PROVIDER_APPROXIMATION = "provider_approximation"
    DERIVED = "derived"
    UNAVAILABLE = "unavailable"


class PDFSceneFidelity(StrEnum):
    NATIVE_EXACT = "native_exact"
    NATIVE_NORMALIZED = "native_normalized"
    PROVIDER_RECONSTRUCTED = "provider_reconstructed"
    EIXO_DERIVED = "eixo_derived"
    HEURISTIC = "heuristic"
    RASTER_ONLY = "raster_only"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class PDFSceneEditabilityHint(StrEnum):
    NATIVE_EDITABLE = "native_editable"
    PARTIALLY_EDITABLE = "partially_editable"
    RECONSTRUCTION_REQUIRED = "reconstruction_required"
    RASTER_ONLY = "raster_only"
    UNKNOWN = "unknown"


class PDFSceneRelationType(StrEnum):
    CONTAINS = "contains"
    CONTAINED_BY = "contained_by"
    USES_RESOURCE = "uses_resource"
    USES_FONT = "uses_font"
    USES_IMAGE = "uses_image"
    USES_GRAPHICS_STATE = "uses_graphics_state"
    CLIPPED_BY = "clipped_by"
    BELONGS_TO_LAYER = "belongs_to_layer"
    APPEARANCE_OF = "appearance_of"
    WIDGET_OF = "widget_of"
    LINKS_TO = "links_to"
    DERIVED_FROM = "derived_from"
    DEFINED_IN_FORM = "defined_in_form"
    OCCURRENCE_OF = "occurrence_of"
    PAINTED_BEFORE = "painted_before"
    PAINTED_AFTER = "painted_after"


@dataclass(frozen=True, slots=True)
class PDFPageSceneOptions(Serializable):
    page_selection: tuple[int, ...] | None = None
    include_invisible_elements: bool = True
    include_logical_interactive_elements: bool = True
    max_elements_per_page: int | None = 250_000
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        _validate_positive_optional("max_elements_per_page", self.max_elements_per_page)
        _validate_positive_optional("timeout_seconds", self.timeout_seconds)
        if self.page_selection is not None and any(
            page < 0 for page in self.page_selection
        ):
            raise ValueError("page_selection cannot contain negative indexes")

    def safe_options(self) -> dict[str, Any]:
        return {
            "page_selection": list(self.page_selection) if self.page_selection else None,
            "include_invisible_elements": self.include_invisible_elements,
            "include_logical_interactive_elements": self.include_logical_interactive_elements,
            "max_elements_per_page": self.max_elements_per_page,
            "timeout_seconds": self.timeout_seconds,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.safe_options()


@dataclass(frozen=True, slots=True)
class PDFSceneSourceReference(Serializable):
    source_artifact_id: str
    source_element_id: str
    source_element_type: str
    provider: str | None = None
    provider_version: str | None = None
    object_reference: str | None = None
    content_stream_reference: str | None = None
    operation_reference: str | None = None
    resource_reference: str | None = None
    parent_form_reference: str | None = None

    def __post_init__(self) -> None:
        _validate_required_text("source_artifact_id", self.source_artifact_id)
        _validate_required_text("source_element_id", self.source_element_id)
        _validate_required_text("source_element_type", self.source_element_type)


@dataclass(frozen=True, slots=True)
class PDFSceneRelation(Serializable):
    relation_id: str
    source_id: str
    target_id: str
    relation_type: PDFSceneRelationType
    confidence: float = 1.0
    details: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_required_text("relation_id", self.relation_id)
        _validate_required_text("source_id", self.source_id)
        _validate_required_text("target_id", self.target_id)
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class PDFVisualElement(Serializable):
    element_id: str
    element_type: PDFSceneElementType
    page_id: str
    source_references: tuple[PDFSceneSourceReference, ...] = ()
    bounding_box: BoundingBox | None = None
    normalized_bounding_box: NormalizedBoundingBox | None = None
    quad: Quad | None = None
    polygon: Polygon | None = None
    path_reference: str | None = None
    local_transform: AffineMatrix | None = None
    effective_transform: AffineMatrix | None = None
    paint_order: PDFPaintOrder | None = None
    native_order: int | None = None
    scene_order: int | None = None
    order_method: PDFSceneOrderMethod = PDFSceneOrderMethod.UNAVAILABLE
    order_confidence: PDFSceneOrderConfidence = PDFSceneOrderConfidence.UNAVAILABLE
    visibility: PDFSceneVisibility = PDFSceneVisibility.UNKNOWN
    opacity: float | None = None
    blend_mode: str | None = None
    clip_path_reference: str | None = None
    clip_chain: tuple[str, ...] = ()
    layer_reference: str | None = None
    layer_membership_reference: str | None = None
    parent_element_id: str | None = None
    resource_references: tuple[str, ...] = ()
    fidelity: PDFSceneFidelity = PDFSceneFidelity.UNKNOWN
    editability_hint: PDFSceneEditabilityHint = PDFSceneEditabilityHint.UNKNOWN
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("element_id", self.element_id)
        _validate_required_text("page_id", self.page_id)
        _validate_non_negative_optional("native_order", self.native_order)
        _validate_non_negative_optional("scene_order", self.scene_order)
        _validate_opacity_optional("opacity", self.opacity)


@dataclass(frozen=True, slots=True)
class PDFPageSceneStatistics(Serializable):
    element_count: int = 0
    text_element_count: int = 0
    image_element_count: int = 0
    vector_element_count: int = 0
    clipping_path_count: int = 0
    link_count: int = 0
    annotation_count: int = 0
    form_widget_count: int = 0
    layer_count: int = 0
    invisible_element_count: int = 0
    unordered_element_count: int = 0
    unresolved_reference_count: int = 0

    def __post_init__(self) -> None:
        for name in self.to_dict():
            _validate_non_negative_optional(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class PDFPageScene(Serializable):
    scene_id: str
    artifact_version: ContractVersion
    document_id: DocumentId | None
    page_id: str
    page_index: int
    geometry: PageGeometry
    elements: tuple[PDFVisualElement, ...] = ()
    ordered_element_ids: tuple[str, ...] = ()
    text_element_ids: tuple[str, ...] = ()
    image_element_ids: tuple[str, ...] = ()
    vector_element_ids: tuple[str, ...] = ()
    clipping_path_ids: tuple[str, ...] = ()
    link_ids: tuple[str, ...] = ()
    annotation_ids: tuple[str, ...] = ()
    form_widget_ids: tuple[str, ...] = ()
    layer_ids: tuple[str, ...] = ()
    relations: tuple[PDFSceneRelation, ...] = ()
    resource_references: tuple[str, ...] = ()
    statistics: PDFPageSceneStatistics = field(default_factory=PDFPageSceneStatistics)
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("scene_id", self.scene_id)
        _validate_required_text("page_id", self.page_id)
        _validate_non_negative_optional("page_index", self.page_index)

    def element_by_id(self, element_id: str) -> PDFVisualElement | None:
        return next((item for item in self.elements if item.element_id == element_id), None)


@dataclass(frozen=True, slots=True)
class PDFPageScenesStatistics(Serializable):
    page_count: int = 0
    element_count: int = 0
    unresolved_reference_count: int = 0
    partial_page_count: int = 0

    def __post_init__(self) -> None:
        for name in self.to_dict():
            _validate_non_negative_optional(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class PDFPageScenesArtifact(Serializable):
    artifact_version: ContractVersion
    provider: PDFProviderDescriptor | None = None
    document_id: DocumentId | None = None
    source_artifacts: tuple[PDFSceneSourceReference, ...] = ()
    resource_catalog_reference: str | None = None
    pages: tuple[PDFPageScene, ...] = ()
    statistics: PDFPageScenesStatistics = field(default_factory=PDFPageScenesStatistics)
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def scene_for_page(self, page_id: str) -> PDFPageScene | None:
        return next((page for page in self.pages if page.page_id == page_id), None)


def pdf_scene_id(page_id: str) -> str:
    return f"pdfscene:{page_id}"


def pdf_scene_element_id(
    element_type: PDFSceneElementType,
    page_id: str,
    source_element_id: str,
) -> str:
    return f"sceneelement:{element_type.value}:{_slug(page_id)}:{_slug(source_element_id)}"


def pdf_scene_relation_id(
    relation_type: PDFSceneRelationType,
    source_id: str,
    target_id: str,
) -> str:
    return f"scenerel:{relation_type.value}:{_slug(source_id)}:{_slug(target_id)}"


def pdf_page_scene_statistics(scene: PDFPageScene) -> PDFPageSceneStatistics:
    return PDFPageSceneStatistics(
        element_count=len(scene.elements),
        text_element_count=len(scene.text_element_ids),
        image_element_count=len(scene.image_element_ids),
        vector_element_count=len(scene.vector_element_ids),
        clipping_path_count=len(scene.clipping_path_ids),
        link_count=len(scene.link_ids),
        annotation_count=len(scene.annotation_ids),
        form_widget_count=len(scene.form_widget_ids),
        layer_count=len(scene.layer_ids),
        invisible_element_count=sum(
            1 for item in scene.elements if item.visibility != PDFSceneVisibility.VISIBLE
        ),
        unordered_element_count=sum(
            1 for item in scene.elements if item.scene_order is None
        ),
        unresolved_reference_count=sum(
            1
            for warning in scene.warnings
            if "unresolved" in warning.code or "missing" in warning.code
        ),
    )


def pdf_page_scenes_statistics(
    pages: tuple[PDFPageScene, ...],
) -> PDFPageScenesStatistics:
    return PDFPageScenesStatistics(
        page_count=len(pages),
        element_count=sum(page.statistics.element_count for page in pages),
        unresolved_reference_count=sum(
            page.statistics.unresolved_reference_count for page in pages
        ),
        partial_page_count=sum(
            1
            for page in pages
            if any(warning.code == "scene_partial" for warning in page.warnings)
        ),
    )


def _slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in safe.split("-") if part) or "unknown"


def _validate_required_text(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} is required")


def _validate_positive_optional(name: str, value: int | float | None) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{name} must be positive")


def _validate_non_negative_optional(name: str, value: int | float | None) -> None:
    if value is not None and value < 0:
        raise ValueError(f"{name} cannot be negative")


def _validate_opacity_optional(name: str, value: float | None) -> None:
    if value is not None and (value < 0.0 or value > 1.0):
        raise ValueError(f"{name} must be between 0 and 1")


def _validate_confidence(value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise ValueError("confidence must be between 0 and 1")


__all__ = [
    "PDFPageScene",
    "PDFPageSceneOptions",
    "PDFPageSceneStatistics",
    "PDFPageScenesArtifact",
    "PDFPageScenesStatistics",
    "PDFSceneEditabilityHint",
    "PDFSceneElementType",
    "PDFSceneFidelity",
    "PDFSceneOrderConfidence",
    "PDFSceneOrderMethod",
    "PDFSceneRelation",
    "PDFSceneRelationType",
    "PDFSceneSourceReference",
    "PDFSceneVisibility",
    "PDFVisualElement",
    "pdf_page_scene_statistics",
    "pdf_page_scenes_statistics",
    "pdf_scene_element_id",
    "pdf_scene_id",
    "pdf_scene_relation_id",
]
