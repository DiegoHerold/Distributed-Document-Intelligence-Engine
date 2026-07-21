from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from eixo.core import ArtifactReference, DocumentId, EixoWarning, ProviderId
from eixo.core.serialization import Serializable
from eixo.core.versions import ContractVersion
from eixo.geometry import AffineMatrix, BoundingBox
from eixo.pdf.models import (
    PDFProviderDescriptor,
    PDFProviderProvenance,
    ProviderLimitation,
)


class PDFMappingStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    UNKNOWN = "unknown"
    NOT_PRESENT = "not_present"
    UNSUPPORTED_BY_PROVIDER = "unsupported_by_provider"
    EXTRACTION_FAILED = "extraction_failed"
    PARTIALLY_RECOVERED = "partially_recovered"


class PDFResourceType(StrEnum):
    FONT = "font"
    IMAGE = "image"
    IMAGE_MASK = "image_mask"
    XOBJECT = "xobject"
    FORM_XOBJECT = "form_xobject"
    IMAGE_XOBJECT = "image_xobject"
    GRAPHICS_STATE = "graphics_state"
    COLOR_SPACE = "color_space"
    PATTERN = "pattern"
    SHADING = "shading"
    LAYER = "layer"
    MASK = "mask"
    CONTENT_STREAM = "content_stream"
    UNKNOWN = "unknown"


class PDFResourceScope(StrEnum):
    DOCUMENT = "document"
    PAGE = "page"
    INHERITED = "inherited"
    FORM_XOBJECT = "form_xobject"
    CONTENT_STREAM = "content_stream"
    INLINE = "inline"


class PDFObjectRelationType(StrEnum):
    REFERENCES = "references"
    CONTAINS = "contains"
    USED_BY = "used_by"
    DEFINED_IN = "defined_in"
    INHERITS_FROM = "inherits_from"
    DRAWS = "draws"
    USES_RESOURCE = "uses_resource"
    MASKED_BY = "masked_by"
    BELONGS_TO_LAYER = "belongs_to_layer"
    PARENT_FORM = "parent_form"


class PDFContentOperationCategory(StrEnum):
    GRAPHICS_STATE = "graphics_state"
    TEXT = "text"
    PATH_CONSTRUCTION = "path_construction"
    PATH_PAINTING = "path_painting"
    IMAGE = "image"
    XOBJECT = "xobject"
    CLIPPING = "clipping"
    COLOR = "color"
    MARKED_CONTENT = "marked_content"
    COMPATIBILITY = "compatibility"
    UNKNOWN = "unknown"


class PDFPaintOrderConfidence(StrEnum):
    EXACT = "exact"
    HIGH = "high"
    PARTIAL = "partial"
    PROVIDER_APPROXIMATION = "provider_approximation"
    UNAVAILABLE = "unavailable"


class PDFProviderSupportStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PDFInternalMappingOptions(Serializable):
    include_indirect_objects: bool = True
    include_content_streams: bool = True
    include_content_operations: bool = True
    include_resources: bool = True
    include_unknown_resources: bool = True
    include_raw_dictionary_summaries: bool = True
    max_object_depth: int = 16
    max_objects: int | None = 10_000
    max_operations_per_stream: int | None = 50_000
    max_raw_summary_size: int = 2048
    timeout_seconds: float | None = None
    preferred_provider: ProviderId | None = None

    def __post_init__(self) -> None:
        for name in (
            "max_object_depth",
            "max_objects",
            "max_operations_per_stream",
            "max_raw_summary_size",
        ):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def safe_options(self) -> dict[str, Any]:
        return {
            "include_indirect_objects": self.include_indirect_objects,
            "include_content_streams": self.include_content_streams,
            "include_content_operations": self.include_content_operations,
            "include_resources": self.include_resources,
            "include_unknown_resources": self.include_unknown_resources,
            "include_raw_dictionary_summaries": self.include_raw_dictionary_summaries,
            "max_object_depth": self.max_object_depth,
            "max_objects": self.max_objects,
            "max_operations_per_stream": self.max_operations_per_stream,
            "max_raw_summary_size": self.max_raw_summary_size,
            "timeout_seconds": self.timeout_seconds,
            "preferred_provider": str(self.preferred_provider)
            if self.preferred_provider
            else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.safe_options()


@dataclass(frozen=True, slots=True)
class PDFObjectReference(Serializable):
    document_id: DocumentId | None = None
    object_number: int | None = None
    generation_number: int | None = 0
    xref: int | None = None
    provider_reference: str | None = None

    def __post_init__(self) -> None:
        _validate_optional_non_negative("object_number", self.object_number)
        _validate_optional_non_negative("generation_number", self.generation_number)
        _validate_optional_non_negative("xref", self.xref)
        if (
            self.object_number is None
            and self.xref is None
            and self.provider_reference is None
        ):
            raise ValueError("object reference needs object_number, xref or provider_reference")

    @property
    def stable_id(self) -> str:
        if self.object_number is not None:
            generation = self.generation_number if self.generation_number is not None else 0
            return f"pdfobj:{self.object_number}:{generation}"
        if self.xref is not None:
            return f"pdfxref:{self.xref}"
        assert self.provider_reference is not None
        return f"pdfprovider:{self.provider_reference}"


@dataclass(frozen=True, slots=True)
class PDFPageReference(Serializable):
    page_index: int
    page_number: int
    page_id: str | None = None
    object_reference: PDFObjectReference | None = None
    provider_reference: str | None = None

    def __post_init__(self) -> None:
        if self.page_index < 0:
            raise ValueError("page_index cannot be negative")
        if self.page_number <= 0:
            raise ValueError("page_number must be positive")

    @property
    def stable_id(self) -> str:
        return self.page_id or f"pdfpage:{self.page_index}"


@dataclass(frozen=True, slots=True)
class PDFResourceReference(Serializable):
    resource_id: str
    resource_type: PDFResourceType
    scope: PDFResourceScope
    resource_name: str | None = None
    page_reference: PDFPageReference | None = None
    object_reference: PDFObjectReference | None = None
    parent_reference: str | None = None
    provider_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.resource_id.strip():
            raise ValueError("resource_id is required")
        if self.resource_name is not None and not self.resource_name.strip():
            raise ValueError("resource_name cannot be empty")


@dataclass(frozen=True, slots=True)
class PDFContentStreamReference(Serializable):
    stream_id: str
    page_reference: PDFPageReference | None = None
    object_reference: PDFObjectReference | None = None
    parent_form_reference: PDFResourceReference | None = None
    stream_index: int = 0
    provider_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.stream_id.strip():
            raise ValueError("stream_id is required")
        if self.stream_index < 0:
            raise ValueError("stream_index cannot be negative")


@dataclass(frozen=True, slots=True)
class PDFOperationReference(Serializable):
    operation_id: str
    stream_reference: PDFContentStreamReference
    operation_index: int

    def __post_init__(self) -> None:
        if not self.operation_id.strip():
            raise ValueError("operation_id is required")
        if self.operation_index < 0:
            raise ValueError("operation_index cannot be negative")


@dataclass(frozen=True, slots=True)
class PDFObjectRelation(Serializable):
    source_id: str
    target_id: str
    relation_type: PDFObjectRelationType
    status: PDFMappingStatus = PDFMappingStatus.RESOLVED
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.target_id.strip():
            raise ValueError("relation endpoints are required")


@dataclass(frozen=True, slots=True)
class PDFIndirectObject(Serializable):
    reference: PDFObjectReference
    object_id: str
    object_type: str | None = None
    subtype: str | None = None
    dictionary_summary: dict[str, str] = field(default_factory=dict)
    has_stream: bool = False
    stream_reference: PDFContentStreamReference | None = None
    referenced_objects: tuple[PDFObjectReference, ...] = ()
    status: PDFMappingStatus = PDFMappingStatus.UNKNOWN
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        if not self.object_id.strip():
            raise ValueError("object_id is required")


@dataclass(frozen=True, slots=True)
class PDFObjectGraph(Serializable):
    objects: tuple[PDFIndirectObject, ...] = ()
    relations: tuple[PDFObjectRelation, ...] = ()
    unresolved_references: tuple[PDFObjectReference, ...] = ()
    cyclic_references: tuple[tuple[str, ...], ...] = ()

    def object_by_id(self, object_id: str) -> PDFIndirectObject | None:
        return next((item for item in self.objects if item.object_id == object_id), None)

    def relations_from(self, source_id: str) -> tuple[PDFObjectRelation, ...]:
        return tuple(item for item in self.relations if item.source_id == source_id)

    def relations_to(self, target_id: str) -> tuple[PDFObjectRelation, ...]:
        return tuple(item for item in self.relations if item.target_id == target_id)


@dataclass(frozen=True, slots=True)
class PDFPaintOrder(Serializable):
    content_stream_index: int | None = None
    operation_index: int | None = None
    local_paint_order: int | None = None
    global_paint_order: int | None = None
    parent_form_order: int | None = None
    confidence: PDFPaintOrderConfidence = PDFPaintOrderConfidence.UNAVAILABLE


@dataclass(frozen=True, slots=True)
class PDFContentOperation(Serializable):
    operation_reference: PDFOperationReference
    operator: str
    category: PDFContentOperationCategory = PDFContentOperationCategory.UNKNOWN
    operands_summary: tuple[str, ...] = ()
    graphics_state_reference: PDFResourceReference | None = None
    resource_references: tuple[PDFResourceReference, ...] = ()
    parent_form_reference: PDFResourceReference | None = None
    layer_reference: PDFResourceReference | None = None
    paint_order: PDFPaintOrder = field(default_factory=PDFPaintOrder)
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        if not self.operator.strip():
            raise ValueError("operator is required")


@dataclass(frozen=True, slots=True)
class PDFContentStream(Serializable):
    stream_reference: PDFContentStreamReference
    byte_length: int | None = None
    filter_chain: tuple[str, ...] = ()
    decoded_available: PDFMappingStatus = PDFMappingStatus.UNKNOWN
    operations_available: PDFMappingStatus = PDFMappingStatus.UNKNOWN
    operation_count: int | None = None
    operations: tuple[PDFContentOperation, ...] = ()
    resource_scope: PDFResourceScope = PDFResourceScope.PAGE
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_optional_non_negative("byte_length", self.byte_length)
        _validate_optional_non_negative("operation_count", self.operation_count)


@dataclass(frozen=True, slots=True)
class PDFResourceDescriptor(Serializable):
    reference: PDFResourceReference
    status: PDFMappingStatus = PDFMappingStatus.UNKNOWN
    subtype: str | None = None
    object_reference: PDFObjectReference | None = None
    pages_using_resource: tuple[PDFPageReference, ...] = ()
    forms_using_resource: tuple[PDFResourceReference, ...] = ()
    dictionary_summary: dict[str, str] = field(default_factory=dict)
    provenance: PDFProviderProvenance | None = None


@dataclass(frozen=True, slots=True)
class PDFFontResourceDescriptor(PDFResourceDescriptor):
    font_subtype: str | None = None
    base_font: str | None = None
    encoding_reference: PDFObjectReference | None = None
    to_unicode_reference: PDFObjectReference | None = None
    font_descriptor_reference: PDFObjectReference | None = None
    embedded_font_reference: PDFObjectReference | None = None
    descendant_font_references: tuple[PDFObjectReference, ...] = ()


@dataclass(frozen=True, slots=True)
class PDFImageResourceDescriptor(PDFResourceDescriptor):
    width: int | None = None
    height: int | None = None
    bits_per_component: int | None = None
    color_space_reference: PDFResourceReference | None = None
    filter_chain: tuple[str, ...] = ()
    mask_reference: PDFResourceReference | None = None
    soft_mask_reference: PDFResourceReference | None = None
    content_hash: str | None = None


@dataclass(frozen=True, slots=True)
class PDFXObjectResource(PDFResourceDescriptor):
    xobject_type: str | None = None
    bounding_box: BoundingBox | None = None
    matrix: AffineMatrix | None = None
    content_streams: tuple[PDFContentStreamReference, ...] = ()
    nested_xobjects: tuple[PDFResourceReference, ...] = ()
    group_summary: dict[str, str] = field(default_factory=dict)
    layer_reference: PDFResourceReference | None = None


@dataclass(frozen=True, slots=True)
class PDFGraphicsStateResource(PDFResourceDescriptor):
    line_width: float | None = None
    line_cap: int | None = None
    line_join: int | None = None
    stroke_alpha: float | None = None
    fill_alpha: float | None = None
    blend_mode: str | None = None
    soft_mask_reference: PDFResourceReference | None = None
    font_reference: PDFResourceReference | None = None


@dataclass(frozen=True, slots=True)
class PDFColorSpaceResource(PDFResourceDescriptor):
    color_space_type: str | None = None
    base_color_space: str | None = None
    icc_profile_reference: PDFObjectReference | None = None
    alternate_color_space: str | None = None
    components: int | None = None
    lookup_reference: PDFObjectReference | None = None


@dataclass(frozen=True, slots=True)
class PDFPatternResource(PDFResourceDescriptor):
    pattern_type: str | None = None
    matrix: AffineMatrix | None = None
    bounding_box: BoundingBox | None = None
    resources: tuple[PDFResourceReference, ...] = ()
    color_space_reference: PDFResourceReference | None = None


@dataclass(frozen=True, slots=True)
class PDFShadingResource(PDFResourceDescriptor):
    shading_type: str | None = None
    color_space_reference: PDFResourceReference | None = None
    function_reference: PDFObjectReference | None = None


@dataclass(frozen=True, slots=True)
class PDFLayerResource(PDFResourceDescriptor):
    name: str | None = None
    default_visible: bool | None = None
    intent: tuple[str, ...] = ()
    membership_references: tuple[PDFObjectReference, ...] = ()


@dataclass(frozen=True, slots=True)
class PDFUnknownResource(PDFResourceDescriptor):
    declared_type: str | None = None
    reason: str = "unknown_resource_type"


@dataclass(frozen=True, slots=True)
class PDFResourceCatalog(Serializable):
    fonts: tuple[PDFFontResourceDescriptor, ...] = ()
    images: tuple[PDFImageResourceDescriptor, ...] = ()
    xobjects: tuple[PDFXObjectResource, ...] = ()
    graphic_states: tuple[PDFGraphicsStateResource, ...] = ()
    color_spaces: tuple[PDFColorSpaceResource, ...] = ()
    patterns: tuple[PDFPatternResource, ...] = ()
    shadings: tuple[PDFShadingResource, ...] = ()
    layers: tuple[PDFLayerResource, ...] = ()
    masks: tuple[PDFImageResourceDescriptor, ...] = ()
    unknown_resources: tuple[PDFUnknownResource, ...] = ()

    def all_resources(self) -> tuple[PDFResourceDescriptor, ...]:
        return (
            self.fonts
            + self.images
            + self.xobjects
            + self.graphic_states
            + self.color_spaces
            + self.patterns
            + self.shadings
            + self.layers
            + self.masks
            + self.unknown_resources
        )

    def get(self, resource_id: str) -> PDFResourceDescriptor | None:
        return next(
            (
                item
                for item in self.all_resources()
                if item.reference.resource_id == resource_id
            ),
            None,
        )

    def pages_using(self, resource_id: str) -> tuple[PDFPageReference, ...]:
        resource = self.get(resource_id)
        return resource.pages_using_resource if resource is not None else ()


@dataclass(frozen=True, slots=True)
class PDFInternalPageMap(Serializable):
    page_reference: PDFPageReference
    own_resources: tuple[PDFResourceReference, ...] = ()
    inherited_resources: tuple[PDFResourceReference, ...] = ()
    content_streams: tuple[PDFContentStream, ...] = ()
    operation_references: tuple[PDFOperationReference, ...] = ()
    annotations_reference: PDFObjectReference | None = None
    layer_references: tuple[PDFResourceReference, ...] = ()
    provenance: PDFProviderProvenance | None = None


@dataclass(frozen=True, slots=True)
class PDFProviderCapabilityMatrixEntry(Serializable):
    feature: str
    support: PDFProviderSupportStatus
    strategy: str
    limitation: str | None = None


@dataclass(frozen=True, slots=True)
class PDFInternalStructureArtifact(Serializable):
    artifact_version: ContractVersion
    provider: PDFProviderDescriptor
    object_graph: PDFObjectGraph
    resource_catalog: PDFResourceCatalog
    pages: tuple[PDFInternalPageMap, ...]
    document_id: DocumentId | None = None
    source_artifact: ArtifactReference | None = None
    unresolved_objects: tuple[PDFObjectReference, ...] = ()
    capability_matrix: tuple[PDFProviderCapabilityMatrixEntry, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    provenance: PDFProviderProvenance | None = None


def object_reference_id(
    object_number: int | None = None,
    generation_number: int | None = 0,
    *,
    xref: int | None = None,
    provider_reference: str | None = None,
) -> str:
    return PDFObjectReference(
        object_number=object_number,
        generation_number=generation_number,
        xref=xref,
        provider_reference=provider_reference,
    ).stable_id


def resource_id(
    resource_type: PDFResourceType,
    scope: PDFResourceScope,
    *,
    resource_name: str | None = None,
    object_reference: PDFObjectReference | None = None,
    page_index: int | None = None,
    parent_reference: str | None = None,
) -> str:
    if object_reference is not None:
        return f"pdf{resource_type.value}:{object_reference.stable_id}"
    parts = ["pdfres", resource_type.value, scope.value]
    if page_index is not None:
        parts.append(f"page-{page_index}")
    if parent_reference:
        parts.append(parent_reference)
    if resource_name:
        parts.append(resource_name.strip("/"))
    return ":".join(parts)


def _validate_optional_non_negative(name: str, value: int | None) -> None:
    if value is not None and value < 0:
        raise ValueError(f"{name} cannot be negative")


__all__ = [
    "PDFColorSpaceResource",
    "PDFContentOperation",
    "PDFContentOperationCategory",
    "PDFContentStream",
    "PDFContentStreamReference",
    "PDFFontResourceDescriptor",
    "PDFGraphicsStateResource",
    "PDFImageResourceDescriptor",
    "PDFIndirectObject",
    "PDFInternalMappingOptions",
    "PDFInternalPageMap",
    "PDFInternalStructureArtifact",
    "PDFLayerResource",
    "PDFMappingStatus",
    "PDFObjectGraph",
    "PDFObjectReference",
    "PDFObjectRelation",
    "PDFObjectRelationType",
    "PDFOperationReference",
    "PDFPaintOrder",
    "PDFPaintOrderConfidence",
    "PDFPageReference",
    "PDFPatternResource",
    "PDFProviderCapabilityMatrixEntry",
    "PDFProviderSupportStatus",
    "PDFResourceCatalog",
    "PDFResourceDescriptor",
    "PDFResourceReference",
    "PDFResourceScope",
    "PDFResourceType",
    "PDFShadingResource",
    "PDFUnknownResource",
    "PDFXObjectResource",
    "object_reference_id",
    "resource_id",
]
