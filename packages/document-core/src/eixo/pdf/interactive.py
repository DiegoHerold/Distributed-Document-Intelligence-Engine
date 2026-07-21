from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from eixo.core import DocumentId, EixoWarning, ProviderId
from eixo.core.serialization import Serializable
from eixo.core.versions import ContractVersion
from eixo.geometry import AffineMatrix, BoundingBox, NormalizedBoundingBox, Point, Quad
from eixo.pdf.models import PDFProviderDescriptor, PDFProviderProvenance, ProviderLimitation
from eixo.pdf.structure import (
    PDFInternalStructureArtifact,
    PDFObjectReference,
    PDFOperationReference,
    PDFPageReference,
    PDFResourceReference,
)


class PDFInteractiveSupportStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    PROVIDER_DERIVED = "provider_derived"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class PDFLinkType(StrEnum):
    EXTERNAL_URI = "external_uri"
    INTERNAL_DESTINATION = "internal_destination"
    NAMED_DESTINATION = "named_destination"
    EMAIL = "email"
    FILE_REFERENCE = "file_reference"
    LAUNCH_ACTION = "launch_action"
    JAVASCRIPT_ACTION = "javascript_action"
    UNKNOWN = "unknown"


class PDFDestinationType(StrEnum):
    XYZ = "XYZ"
    FIT = "Fit"
    FITH = "FitH"
    FITV = "FitV"
    FITR = "FitR"
    FITB = "FitB"
    FITBH = "FitBH"
    FITBV = "FitBV"
    UNKNOWN = "Unknown"


class PDFResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class PDFInteractiveVisibility(StrEnum):
    VISIBLE = "visible"
    HIDDEN = "hidden"
    HIDDEN_BY_LAYER = "hidden_by_layer"
    NO_VIEW = "no_view"
    PRINT_ONLY = "print_only"
    UNKNOWN = "unknown"


class PDFAnnotationType(StrEnum):
    TEXT = "text"
    FREE_TEXT = "free_text"
    LINE = "line"
    SQUARE = "square"
    CIRCLE = "circle"
    POLYGON = "polygon"
    POLYLINE = "polyline"
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    SQUIGGLY = "squiggly"
    STRIKEOUT = "strikeout"
    STAMP = "stamp"
    CARET = "caret"
    INK = "ink"
    POPUP = "popup"
    FILE_ATTACHMENT = "file_attachment"
    SOUND = "sound"
    MOVIE = "movie"
    SCREEN = "screen"
    WATERMARK = "watermark"
    REDACTION = "redaction"
    WIDGET = "widget"
    UNKNOWN = "unknown"


class PDFAppearanceType(StrEnum):
    NORMAL = "normal"
    ROLLOVER = "rollover"
    DOWN = "down"
    UNKNOWN = "unknown"


class PDFFormFieldType(StrEnum):
    TEXT = "text"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    PUSH_BUTTON = "push_button"
    COMBO_BOX = "combo_box"
    LIST_BOX = "list_box"
    SIGNATURE = "signature"
    UNKNOWN = "unknown"


class PDFControlState(StrEnum):
    CHECKED = "checked"
    UNCHECKED = "unchecked"
    INDETERMINATE = "indeterminate"
    SELECTED = "selected"
    EMPTY = "empty"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PDFInteractiveExtractionOptions(Serializable):
    include_links: bool = True
    include_annotations: bool = True
    include_forms: bool = True
    include_layers: bool = True
    include_appearances: bool = True
    page_selection: tuple[int, ...] | None = None
    max_links: int | None = 100_000
    max_annotations: int | None = 100_000
    max_fields: int | None = 50_000
    max_widgets: int | None = 100_000
    max_layer_depth: int | None = 16
    timeout_seconds: float | None = None
    preferred_provider: ProviderId | None = None

    def __post_init__(self) -> None:
        for name in (
            "max_links",
            "max_annotations",
            "max_fields",
            "max_widgets",
            "max_layer_depth",
        ):
            _validate_positive_optional(name, getattr(self, name))
        _validate_positive_optional("timeout_seconds", self.timeout_seconds)
        if self.page_selection is not None and any(
            page < 0 for page in self.page_selection
        ):
            raise ValueError("page_selection cannot contain negative indexes")

    def safe_options(self) -> dict[str, Any]:
        return {
            "include_links": self.include_links,
            "include_annotations": self.include_annotations,
            "include_forms": self.include_forms,
            "include_layers": self.include_layers,
            "include_appearances": self.include_appearances,
            "page_selection": list(self.page_selection) if self.page_selection else None,
            "max_links": self.max_links,
            "max_annotations": self.max_annotations,
            "max_fields": self.max_fields,
            "max_widgets": self.max_widgets,
            "max_layer_depth": self.max_layer_depth,
            "timeout_seconds": self.timeout_seconds,
            "preferred_provider": str(self.preferred_provider)
            if self.preferred_provider
            else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.safe_options()


@dataclass(frozen=True, slots=True)
class PDFDestination(Serializable):
    destination_id: str
    destination_type: PDFDestinationType = PDFDestinationType.UNKNOWN
    page_reference: PDFPageReference | None = None
    page_id: str | None = None
    coordinates: Point | None = None
    zoom: float | None = None
    named_destination: str | None = None
    object_reference: PDFObjectReference | None = None
    raw_reference: str | None = None
    resolution_status: PDFResolutionStatus = PDFResolutionStatus.UNKNOWN
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("destination_id", self.destination_id)
        _validate_positive_optional("zoom", self.zoom)


@dataclass(frozen=True, slots=True)
class PDFDestinationResolver(Serializable):
    page_references: tuple[PDFPageReference, ...] = ()

    def resolve_page_destination(
        self,
        *,
        page_index: int | None,
        point: Point | None = None,
        zoom: float | None = None,
        named_destination: str | None = None,
        raw_reference: str | None = None,
        provenance: PDFProviderProvenance | None = None,
    ) -> PDFDestination:
        page = self._page_by_index(page_index)
        status = (
            PDFResolutionStatus.RESOLVED
            if page is not None
            else PDFResolutionStatus.UNRESOLVED
        )
        warning = (
            EixoWarning(
                code="link_destination_unresolved",
                message="Internal link destination page could not be resolved.",
                scope=str(page_index) if page_index is not None else raw_reference,
            )
            if status == PDFResolutionStatus.UNRESOLVED
            else None
        )
        return PDFDestination(
            destination_id=destination_id(page_index, named_destination, raw_reference),
            destination_type=(
                PDFDestinationType.XYZ
                if point is not None
                else PDFDestinationType.FIT
            ),
            page_reference=page,
            page_id=page.stable_id if page else None,
            coordinates=point,
            zoom=zoom,
            named_destination=named_destination,
            raw_reference=raw_reference,
            resolution_status=status,
            warnings=(warning,) if warning else (),
            provenance=provenance,
        )

    def _page_by_index(self, page_index: int | None) -> PDFPageReference | None:
        if page_index is None:
            return None
        return next(
            (page for page in self.page_references if page.page_index == page_index),
            None,
        )


@dataclass(frozen=True, slots=True)
class PDFLink(Serializable):
    link_id: str
    page_id: str
    link_type: PDFLinkType
    bounding_box: BoundingBox | None = None
    normalized_bounding_box: NormalizedBoundingBox | None = None
    quad_points: tuple[Quad, ...] = ()
    uri: str | None = None
    destination_reference: str | None = None
    destination_page_id: str | None = None
    destination_coordinates: Point | None = None
    named_destination: str | None = None
    action_type: str | None = None
    action_summary: str | None = None
    annotation_reference: PDFObjectReference | None = None
    layer_reference: PDFResourceReference | None = None
    visibility: PDFInteractiveVisibility = PDFInteractiveVisibility.UNKNOWN
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("link_id", self.link_id)
        _validate_required_text("page_id", self.page_id)


@dataclass(frozen=True, slots=True)
class PDFAppearanceReference(Serializable):
    appearance_id: str
    appearance_type: PDFAppearanceType = PDFAppearanceType.UNKNOWN
    state_name: str | None = None
    form_xobject_reference: PDFResourceReference | None = None
    object_reference: PDFObjectReference | None = None
    bounding_box: BoundingBox | None = None
    matrix: AffineMatrix | None = None
    resource_scope: str | None = None
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("appearance_id", self.appearance_id)


@dataclass(frozen=True, slots=True)
class PDFAnnotation(Serializable):
    annotation_id: str
    page_id: str
    annotation_type: PDFAnnotationType = PDFAnnotationType.UNKNOWN
    object_reference: PDFObjectReference | None = None
    bounding_box: BoundingBox | None = None
    normalized_bounding_box: NormalizedBoundingBox | None = None
    quad_points: tuple[Quad, ...] = ()
    content: str | None = None
    subject: str | None = None
    author: str | None = None
    created_at: str | None = None
    modified_at: str | None = None
    flags: tuple[str, ...] = ()
    color: tuple[float, ...] = ()
    opacity: float | None = None
    border: dict[str, str] = field(default_factory=dict)
    appearance_references: tuple[str, ...] = ()
    popup_reference: PDFObjectReference | None = None
    parent_reference: PDFObjectReference | None = None
    reply_to_reference: PDFObjectReference | None = None
    layer_reference: PDFResourceReference | None = None
    visibility: PDFInteractiveVisibility = PDFInteractiveVisibility.UNKNOWN
    state: str | None = None
    state_model: str | None = None
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("annotation_id", self.annotation_id)
        _validate_required_text("page_id", self.page_id)
        _validate_opacity_optional("opacity", self.opacity)


@dataclass(frozen=True, slots=True)
class PDFForm(Serializable):
    form_id: str
    field_ids: tuple[str, ...] = ()
    default_resources: tuple[PDFResourceReference, ...] = ()
    default_appearance: str | None = None
    calculation_order: tuple[str, ...] = ()
    need_appearances: bool | None = None
    signature_flags: int | None = None
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("form_id", self.form_id)
        _validate_non_negative_optional("signature_flags", self.signature_flags)


@dataclass(frozen=True, slots=True)
class PDFFormField(Serializable):
    field_id: str
    parent_field_id: str | None = None
    child_field_ids: tuple[str, ...] = ()
    fully_qualified_name: str | None = None
    partial_name: str | None = None
    alternate_name: str | None = None
    mapping_name: str | None = None
    field_type: PDFFormFieldType = PDFFormFieldType.UNKNOWN
    raw_value: str | None = None
    display_value: str | None = None
    default_value: str | None = None
    options: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()
    required: bool | None = None
    read_only: bool | None = None
    no_export: bool | None = None
    widget_ids: tuple[str, ...] = ()
    control_state: PDFControlState = PDFControlState.UNKNOWN
    calculation_order: int | None = None
    actions_summary: tuple[str, ...] = ()
    inherited_properties: dict[str, str] = field(default_factory=dict)
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("field_id", self.field_id)
        _validate_non_negative_optional("calculation_order", self.calculation_order)


@dataclass(frozen=True, slots=True)
class PDFFormWidget(Serializable):
    widget_id: str
    field_id: str | None
    page_id: str
    object_reference: PDFObjectReference | None = None
    bounding_box: BoundingBox | None = None
    normalized_bounding_box: NormalizedBoundingBox | None = None
    quad_points: tuple[Quad, ...] = ()
    appearance_references: tuple[str, ...] = ()
    appearance_state: str | None = None
    highlight_mode: str | None = None
    border: dict[str, str] = field(default_factory=dict)
    background_color: tuple[float, ...] = ()
    rotation: float | None = None
    layer_reference: PDFResourceReference | None = None
    visibility: PDFInteractiveVisibility = PDFInteractiveVisibility.UNKNOWN
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("widget_id", self.widget_id)
        _validate_required_text("page_id", self.page_id)


@dataclass(frozen=True, slots=True)
class PDFLayer(Serializable):
    layer_id: str
    object_reference: PDFObjectReference | None = None
    name: str | None = None
    intent: tuple[str, ...] = ()
    default_visibility: bool | None = None
    current_visibility: bool | None = None
    locked: bool | None = None
    usage: dict[str, str] = field(default_factory=dict)
    parent_layer_id: str | None = None
    child_layer_ids: tuple[str, ...] = ()
    configuration_reference: str | None = None
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("layer_id", self.layer_id)


@dataclass(frozen=True, slots=True)
class PDFLayerConfiguration(Serializable):
    configuration_id: str
    name: str | None = None
    creator: str | None = None
    base_state: str | None = None
    enabled_layer_ids: tuple[str, ...] = ()
    disabled_layer_ids: tuple[str, ...] = ()
    locked_layer_ids: tuple[str, ...] = ()
    radio_button_groups: tuple[tuple[str, ...], ...] = ()
    order: tuple[str, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("configuration_id", self.configuration_id)


@dataclass(frozen=True, slots=True)
class PDFLayerMembership(Serializable):
    membership_id: str
    element_id: str
    element_type: str
    layer_id: str | None = None
    layer_reference: PDFResourceReference | None = None
    operation_reference: PDFOperationReference | None = None
    resolution_status: PDFResolutionStatus = PDFResolutionStatus.UNKNOWN
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("membership_id", self.membership_id)
        _validate_required_text("element_id", self.element_id)
        _validate_required_text("element_type", self.element_type)


@dataclass(frozen=True, slots=True)
class PDFMarkedContentScope(Serializable):
    scope_id: str
    tag: str | None = None
    property_reference: PDFResourceReference | None = None
    start_operation_reference: PDFOperationReference | None = None
    end_operation_reference: PDFOperationReference | None = None
    parent_scope_id: str | None = None
    layer_reference: PDFResourceReference | None = None
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("scope_id", self.scope_id)


@dataclass(frozen=True, slots=True)
class PDFPageInteractiveLayer(Serializable):
    page_reference: PDFPageReference
    link_ids: tuple[str, ...] = ()
    annotation_ids: tuple[str, ...] = ()
    widget_ids: tuple[str, ...] = ()
    layer_memberships: tuple[str, ...] = ()
    ordered_interactive_ids: tuple[str, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None


@dataclass(frozen=True, slots=True)
class PDFInteractiveStatistics(Serializable):
    link_count: int = 0
    external_link_count: int = 0
    internal_link_count: int = 0
    unresolved_destination_count: int = 0
    annotation_count: int = 0
    missing_appearance_count: int = 0
    form_field_count: int = 0
    widget_count: int = 0
    layer_count: int = 0
    unresolved_layer_membership_count: int = 0

    def __post_init__(self) -> None:
        for name in (
            "link_count",
            "external_link_count",
            "internal_link_count",
            "unresolved_destination_count",
            "annotation_count",
            "missing_appearance_count",
            "form_field_count",
            "widget_count",
            "layer_count",
            "unresolved_layer_membership_count",
        ):
            _validate_non_negative_optional(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class PDFInteractiveCapabilityMatrixEntry(Serializable):
    information: str
    support: PDFInteractiveSupportStatus
    origin: str
    precision: str | None = None
    limitation: str | None = None

    def __post_init__(self) -> None:
        _validate_required_text("information", self.information)
        _validate_required_text("origin", self.origin)


@dataclass(frozen=True, slots=True)
class PDFInteractiveArtifact(Serializable):
    artifact_version: ContractVersion
    provider: PDFProviderDescriptor
    document_id: DocumentId | None = None
    source_structure_artifact: PDFInternalStructureArtifact | None = None
    links: tuple[PDFLink, ...] = ()
    destinations: tuple[PDFDestination, ...] = ()
    annotations: tuple[PDFAnnotation, ...] = ()
    appearances: tuple[PDFAppearanceReference, ...] = ()
    form: PDFForm | None = None
    fields: tuple[PDFFormField, ...] = ()
    widgets: tuple[PDFFormWidget, ...] = ()
    layers: tuple[PDFLayer, ...] = ()
    layer_configurations: tuple[PDFLayerConfiguration, ...] = ()
    layer_memberships: tuple[PDFLayerMembership, ...] = ()
    marked_content_scopes: tuple[PDFMarkedContentScope, ...] = ()
    page_layers: tuple[PDFPageInteractiveLayer, ...] = ()
    statistics: PDFInteractiveStatistics = field(default_factory=PDFInteractiveStatistics)
    capability_matrix: tuple[PDFInteractiveCapabilityMatrixEntry, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def links_for_page(self, page_id: str) -> tuple[PDFLink, ...]:
        return tuple(item for item in self.links if item.page_id == page_id)

    def widgets_for_field(self, field_id: str) -> tuple[PDFFormWidget, ...]:
        return tuple(item for item in self.widgets if item.field_id == field_id)

    def field_by_id(self, field_id: str) -> PDFFormField | None:
        return next((item for item in self.fields if item.field_id == field_id), None)


def link_id(page_index: int, link_index: int, native_id: str | None = None) -> str:
    if native_id:
        return f"pdflink:page-{page_index}:{native_id}"
    return f"pdflink:page-{page_index}:link-{link_index}"


def destination_id(
    page_index: int | None = None,
    named_destination: str | None = None,
    raw_reference: str | None = None,
) -> str:
    if named_destination:
        return f"pdfdest:named:{_slug(named_destination)}"
    if raw_reference:
        return f"pdfdest:raw:{_slug(raw_reference)}"
    if page_index is not None:
        return f"pdfdest:page-{page_index}"
    return "pdfdest:unknown"


def annotation_id(page_index: int, annot_index: int, xref: int | None = None) -> str:
    if xref is not None and xref > 0:
        return f"pdfannot:{xref}:0"
    return f"pdfannot:page-{page_index}:annot-{annot_index}"


def appearance_id(owner_id: str, appearance_type: str, state_name: str | None = None) -> str:
    suffix = f":{_slug(state_name)}" if state_name else ""
    return f"pdfappearance:{owner_id}:{appearance_type}{suffix}"


def form_id(document_id: DocumentId | None = None) -> str:
    return f"pdfform:{document_id}" if document_id else "pdfform:document"


def field_id(name: str | None, fallback_index: int) -> str:
    if name and name.strip():
        return f"pdffield:{_slug(name)}"
    return f"pdffield:field-{fallback_index}"


def widget_id(page_index: int, widget_index: int, xref: int | None = None) -> str:
    if xref is not None and xref > 0:
        return f"pdfwidget:{xref}:0"
    return f"pdfwidget:page-{page_index}:widget-{widget_index}"


def layer_id(name: str | None, xref: int | None = None, index: int = 0) -> str:
    if xref is not None and xref > 0:
        return f"pdflayer:{xref}:0"
    if name:
        return f"pdflayer:{_slug(name)}"
    return f"pdflayer:{index}"


def interactive_statistics(
    artifact: PDFInteractiveArtifact,
) -> PDFInteractiveStatistics:
    return PDFInteractiveStatistics(
        link_count=len(artifact.links),
        external_link_count=sum(
            1 for item in artifact.links if item.link_type == PDFLinkType.EXTERNAL_URI
        ),
        internal_link_count=sum(
            1
            for item in artifact.links
            if item.link_type == PDFLinkType.INTERNAL_DESTINATION
        ),
        unresolved_destination_count=sum(
            1
            for item in artifact.destinations
            if item.resolution_status == PDFResolutionStatus.UNRESOLVED
        ),
        annotation_count=len(artifact.annotations),
        missing_appearance_count=sum(
            1 for item in artifact.annotations if not item.appearance_references
        ),
        form_field_count=len(artifact.fields),
        widget_count=len(artifact.widgets),
        layer_count=len(artifact.layers),
        unresolved_layer_membership_count=sum(
            1
            for item in artifact.layer_memberships
            if item.resolution_status == PDFResolutionStatus.UNRESOLVED
        ),
    )


def _slug(value: str | None) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in (value or "unknown"))
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


__all__ = [
    "PDFAppearanceReference",
    "PDFAppearanceType",
    "PDFAnnotation",
    "PDFAnnotationType",
    "PDFControlState",
    "PDFDestination",
    "PDFDestinationResolver",
    "PDFDestinationType",
    "PDFForm",
    "PDFFormField",
    "PDFFormFieldType",
    "PDFFormWidget",
    "PDFInteractiveArtifact",
    "PDFInteractiveCapabilityMatrixEntry",
    "PDFInteractiveExtractionOptions",
    "PDFInteractiveStatistics",
    "PDFInteractiveSupportStatus",
    "PDFInteractiveVisibility",
    "PDFLayer",
    "PDFLayerConfiguration",
    "PDFLayerMembership",
    "PDFLink",
    "PDFLinkType",
    "PDFMarkedContentScope",
    "PDFPageInteractiveLayer",
    "PDFResolutionStatus",
    "annotation_id",
    "appearance_id",
    "destination_id",
    "field_id",
    "form_id",
    "interactive_statistics",
    "layer_id",
    "link_id",
    "widget_id",
]
