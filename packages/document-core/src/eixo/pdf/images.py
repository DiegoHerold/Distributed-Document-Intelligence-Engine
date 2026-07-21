from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from eixo.core import ArtifactReference, DocumentId, EixoWarning, ProviderId
from eixo.core.serialization import Serializable
from eixo.core.versions import ContractVersion
from eixo.geometry import AffineMatrix, BoundingBox, NormalizedBoundingBox, Quad
from eixo.pdf.models import PDFProviderDescriptor, PDFProviderProvenance, ProviderLimitation
from eixo.pdf.structure import (
    PDFContentStreamReference,
    PDFImageResourceDescriptor,
    PDFInternalStructureArtifact,
    PDFObjectReference,
    PDFOperationReference,
    PDFPageReference,
    PDFPaintOrder,
    PDFResourceReference,
    PDFResourceScope,
)


class PDFImageSupportStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    PROVIDER_DERIVED = "provider_derived"
    HEURISTIC = "heuristic"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"
    EXTRACTION_FAILED = "extraction_failed"


class PDFImageKind(StrEnum):
    IMAGE_XOBJECT = "image_xobject"
    INLINE_IMAGE = "inline_image"
    IMAGE_MASK = "image_mask"
    SOFT_MASK = "soft_mask"
    STENCIL_MASK = "stencil_mask"
    EMBEDDED_RASTER = "embedded_raster"
    UNKNOWN_IMAGE_RESOURCE = "unknown_image_resource"


class PDFImageBinaryRepresentation(StrEnum):
    ORIGINAL_ENCODED_STREAM = "original_encoded_stream"
    PROVIDER_EXTRACTED_ORIGINAL = "provider_extracted_original"
    DECODED_PIXELS = "decoded_pixels"
    NORMALIZED_EXPORT = "normalized_export"


class PDFImageBinaryFidelity(StrEnum):
    ORIGINAL = "original"
    LOSSLESS_NORMALIZED = "lossless_normalized"
    LOSSY_NORMALIZED = "lossy_normalized"
    PROVIDER_RECONSTRUCTED = "provider_reconstructed"
    UNKNOWN = "unknown"


class PDFImageMaskType(StrEnum):
    EXPLICIT_MASK = "explicit_mask"
    COLOR_KEY_MASK = "color_key_mask"
    IMAGE_MASK = "image_mask"
    SOFT_MASK = "soft_mask"
    STENCIL_MASK = "stencil_mask"
    UNKNOWN = "unknown"


class PDFImageClipStatus(StrEnum):
    NOT_CLIPPED = "not_clipped"
    PARTIALLY_CLIPPED = "partially_clipped"
    FULLY_CLIPPED = "fully_clipped"
    CLIP_UNKNOWN = "clip_unknown"


class PDFImageVisibility(StrEnum):
    VISIBLE = "visible"
    INVISIBLE = "invisible"
    FULLY_CLIPPED = "fully_clipped"
    PARTIALLY_CLIPPED = "partially_clipped"
    OUTSIDE_CROP_BOX = "outside_crop_box"
    ZERO_OPACITY = "zero_opacity"
    HIDDEN_BY_LAYER = "hidden_by_layer"
    UNKNOWN = "unknown"


class PDFImageExtractionMethod(StrEnum):
    RESOURCE_CATALOG = "resource_catalog"
    PROVIDER_IMAGE_INFO = "provider_image_info"
    PROVIDER_EXTRACT_IMAGE = "provider_extract_image"
    CONTENT_STREAM_OPERATION = "content_stream_operation"
    HEURISTIC = "heuristic"
    UNSUPPORTED = "unsupported"


class PDFImageColorSpace(StrEnum):
    DEVICE_GRAY = "DeviceGray"
    DEVICE_RGB = "DeviceRGB"
    DEVICE_CMYK = "DeviceCMYK"
    CAL_GRAY = "CalGray"
    CAL_RGB = "CalRGB"
    LAB = "Lab"
    ICC_BASED = "ICCBased"
    INDEXED = "Indexed"
    SEPARATION = "Separation"
    DEVICE_N = "DeviceN"
    PATTERN = "Pattern"
    UNKNOWN = "Unknown"


@dataclass(frozen=True, slots=True)
class PDFImageExtractionOptions(Serializable):
    include_encoded_bytes: bool = True
    include_decoded_representation: bool = False
    generate_normalized_exports: bool = False
    include_invisible_images: bool = True
    include_unused_resources: bool = True
    resolve_masks: bool = True
    calculate_effective_dpi: bool = True
    page_selection: tuple[int, ...] | None = None
    max_image_resources: int | None = 10_000
    max_image_occurrences: int | None = 100_000
    max_encoded_image_bytes: int | None = 50 * 1024 * 1024
    max_decoded_image_bytes: int | None = 250 * 1024 * 1024
    max_image_pixels: int | None = 100_000_000
    max_normalized_exports: int | None = 0
    timeout_seconds: float | None = None
    preferred_provider: ProviderId | None = None

    def __post_init__(self) -> None:
        for name in (
            "max_image_resources",
            "max_image_occurrences",
            "max_encoded_image_bytes",
            "max_decoded_image_bytes",
            "max_image_pixels",
            "max_normalized_exports",
        ):
            _validate_non_negative_optional(name, getattr(self, name))
        _validate_positive_optional("timeout_seconds", self.timeout_seconds)
        if self.page_selection is not None and any(page < 0 for page in self.page_selection):
            raise ValueError("page_selection cannot contain negative indexes")

    def safe_options(self) -> dict[str, Any]:
        return {
            "include_encoded_bytes": self.include_encoded_bytes,
            "include_decoded_representation": self.include_decoded_representation,
            "generate_normalized_exports": self.generate_normalized_exports,
            "include_invisible_images": self.include_invisible_images,
            "include_unused_resources": self.include_unused_resources,
            "resolve_masks": self.resolve_masks,
            "calculate_effective_dpi": self.calculate_effective_dpi,
            "page_selection": list(self.page_selection) if self.page_selection else None,
            "max_image_resources": self.max_image_resources,
            "max_image_occurrences": self.max_image_occurrences,
            "max_encoded_image_bytes": self.max_encoded_image_bytes,
            "max_decoded_image_bytes": self.max_decoded_image_bytes,
            "max_image_pixels": self.max_image_pixels,
            "max_normalized_exports": self.max_normalized_exports,
            "timeout_seconds": self.timeout_seconds,
            "preferred_provider": str(self.preferred_provider)
            if self.preferred_provider
            else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.safe_options()


@dataclass(frozen=True, slots=True)
class PDFImageBinaryReference(Serializable):
    binary_id: str
    artifact_reference: ArtifactReference | None = None
    content_hash: str | None = None
    size_bytes: int | None = None
    representation: PDFImageBinaryRepresentation = (
        PDFImageBinaryRepresentation.ORIGINAL_ENCODED_STREAM
    )
    media_type: str | None = None
    detected_format: str | None = None
    extraction_method: PDFImageExtractionMethod = PDFImageExtractionMethod.UNSUPPORTED
    fidelity: PDFImageBinaryFidelity = PDFImageBinaryFidelity.UNKNOWN
    provider_metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_required_text("binary_id", self.binary_id)
        _validate_non_negative_optional("size_bytes", self.size_bytes)


@dataclass(frozen=True, slots=True)
class PDFImageMaskReference(Serializable):
    mask_id: str
    mask_type: PDFImageMaskType
    masked_image_resource_id: str | None = None
    mask_resource_id: str | None = None
    mask_reference: PDFResourceReference | None = None
    color_key_range: tuple[float, ...] = ()
    matte: tuple[float, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("mask_id", self.mask_id)


@dataclass(frozen=True, slots=True)
class PDFSoftMaskResource(Serializable):
    soft_mask_id: str
    mask_resource_id: str
    source_image_resource_id: str | None = None
    width: int | None = None
    height: int | None = None
    color_space_summary: str | None = None
    luminosity: bool | None = None
    alpha: bool | None = None
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("soft_mask_id", self.soft_mask_id)
        _validate_required_text("mask_resource_id", self.mask_resource_id)
        _validate_positive_optional("width", self.width)
        _validate_positive_optional("height", self.height)


@dataclass(frozen=True, slots=True)
class PDFColorKeyMask(Serializable):
    color_key_mask_id: str
    masked_image_resource_id: str
    color_space_summary: str | None = None
    ranges: tuple[float, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("color_key_mask_id", self.color_key_mask_id)
        _validate_required_text("masked_image_resource_id", self.masked_image_resource_id)


@dataclass(frozen=True, slots=True)
class PDFImageTransparency(Serializable):
    image_alpha: bool | None = None
    soft_mask_reference: PDFImageMaskReference | None = None
    graphics_state_alpha: float | None = None
    blend_mode: str | None = None
    transparency_group_reference: PDFResourceReference | None = None
    effective_opacity: float | None = None

    def __post_init__(self) -> None:
        _validate_opacity_optional("graphics_state_alpha", self.graphics_state_alpha)
        _validate_opacity_optional("effective_opacity", self.effective_opacity)


@dataclass(frozen=True, slots=True)
class PDFImageResource(Serializable):
    image_resource_id: str
    object_reference: PDFObjectReference | None = None
    resource_reference: PDFResourceReference | None = None
    resource_name: str | None = None
    scope: PDFResourceScope | None = None
    image_kind: PDFImageKind = PDFImageKind.UNKNOWN_IMAGE_RESOURCE
    subtype: str | None = None
    width: int | None = None
    height: int | None = None
    bits_per_component: int | None = None
    component_count: int | None = None
    color_space_reference: PDFResourceReference | None = None
    color_space_summary: str | None = None
    original_color_space: PDFImageColorSpace = PDFImageColorSpace.UNKNOWN
    normalized_color_space: PDFImageColorSpace | None = None
    color_conversion_method: str | None = None
    color_conversion_confidence: float = 0.0
    filter_chain: tuple[str, ...] = ()
    compression: str | None = None
    decode_parameters: dict[str, str] = field(default_factory=dict)
    decode_array: tuple[float, ...] = ()
    interpolate: bool | None = None
    image_mask: bool | None = None
    mask_reference: PDFImageMaskReference | None = None
    soft_mask_reference: PDFImageMaskReference | None = None
    transparency: PDFImageTransparency | None = None
    matte: tuple[float, ...] = ()
    intent: str | None = None
    metadata_reference: PDFObjectReference | None = None
    struct_parent: int | None = None
    encoded_artifact_reference: PDFImageBinaryReference | None = None
    decoded_artifact_reference: PDFImageBinaryReference | None = None
    normalized_artifact_reference: PDFImageBinaryReference | None = None
    encoded_hash: str | None = None
    decoded_hash: str | None = None
    visual_content_hash: str | None = None
    encoded_size_bytes: int | None = None
    decoded_size_bytes: int | None = None
    detected_format: str | None = None
    export_format: str | None = None
    pages_using_resource: tuple[PDFPageReference, ...] = ()
    forms_using_resource: tuple[PDFResourceReference, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("image_resource_id", self.image_resource_id)
        _validate_positive_optional("width", self.width)
        _validate_positive_optional("height", self.height)
        _validate_positive_optional("bits_per_component", self.bits_per_component)
        _validate_positive_optional("component_count", self.component_count)
        _validate_confidence(self.color_conversion_confidence)
        _validate_non_negative_optional("struct_parent", self.struct_parent)
        _validate_non_negative_optional("encoded_size_bytes", self.encoded_size_bytes)
        _validate_non_negative_optional("decoded_size_bytes", self.decoded_size_bytes)

    @classmethod
    def from_descriptor(
        cls,
        descriptor: PDFImageResourceDescriptor,
        *,
        encoded_artifact_reference: PDFImageBinaryReference | None = None,
        decoded_artifact_reference: PDFImageBinaryReference | None = None,
    ) -> "PDFImageResource":
        kind = (
            PDFImageKind.SOFT_MASK
            if descriptor.reference.resource_type.value in {"mask", "image_mask"}
            else PDFImageKind.IMAGE_XOBJECT
        )
        mask_reference = (
            PDFImageMaskReference(
                mask_id=f"pdfmask:{descriptor.mask_reference.resource_id}",
                mask_type=PDFImageMaskType.EXPLICIT_MASK,
                masked_image_resource_id=descriptor.reference.resource_id,
                mask_resource_id=descriptor.mask_reference.resource_id,
                mask_reference=descriptor.mask_reference,
                provenance=descriptor.provenance,
            )
            if descriptor.mask_reference is not None
            else None
        )
        soft_mask_reference = (
            PDFImageMaskReference(
                mask_id=f"pdfmask:{descriptor.soft_mask_reference.resource_id}",
                mask_type=PDFImageMaskType.SOFT_MASK,
                masked_image_resource_id=descriptor.reference.resource_id,
                mask_resource_id=descriptor.soft_mask_reference.resource_id,
                mask_reference=descriptor.soft_mask_reference,
                provenance=descriptor.provenance,
            )
            if descriptor.soft_mask_reference is not None
            else None
        )
        return cls(
            image_resource_id=descriptor.reference.resource_id,
            object_reference=descriptor.object_reference,
            resource_reference=descriptor.reference,
            resource_name=descriptor.reference.resource_name,
            scope=descriptor.reference.scope,
            image_kind=kind,
            subtype=descriptor.subtype,
            width=descriptor.width,
            height=descriptor.height,
            bits_per_component=descriptor.bits_per_component,
            color_space_reference=descriptor.color_space_reference,
            color_space_summary=descriptor.dictionary_summary.get("color_space"),
            original_color_space=image_color_space_from_name(
                descriptor.dictionary_summary.get("color_space")
            ),
            filter_chain=descriptor.filter_chain,
            compression=descriptor.filter_chain[0] if descriptor.filter_chain else None,
            image_mask=kind
            in {PDFImageKind.IMAGE_MASK, PDFImageKind.SOFT_MASK, PDFImageKind.STENCIL_MASK},
            mask_reference=mask_reference,
            soft_mask_reference=soft_mask_reference,
            transparency=PDFImageTransparency(soft_mask_reference=soft_mask_reference)
            if soft_mask_reference is not None
            else None,
            encoded_artifact_reference=encoded_artifact_reference,
            decoded_artifact_reference=decoded_artifact_reference,
            encoded_hash=encoded_artifact_reference.content_hash
            if encoded_artifact_reference
            else descriptor.content_hash,
            decoded_hash=decoded_artifact_reference.content_hash
            if decoded_artifact_reference
            else None,
            encoded_size_bytes=encoded_artifact_reference.size_bytes
            if encoded_artifact_reference
            else None,
            decoded_size_bytes=decoded_artifact_reference.size_bytes
            if decoded_artifact_reference
            else None,
            detected_format=encoded_artifact_reference.detected_format
            if encoded_artifact_reference
            else _format_from_filters(descriptor.filter_chain),
            pages_using_resource=descriptor.pages_using_resource,
            forms_using_resource=descriptor.forms_using_resource,
            provenance=descriptor.provenance,
        )


@dataclass(frozen=True, slots=True)
class PDFImageOccurrence(Serializable):
    occurrence_id: str
    image_resource_id: str
    page_id: str
    bounding_box: BoundingBox | None = None
    normalized_bounding_box: NormalizedBoundingBox | None = None
    quad: Quad | None = None
    local_transform: AffineMatrix | None = None
    parent_transform: AffineMatrix | None = None
    effective_transform: AffineMatrix | None = None
    rotation: float | None = None
    scale_x: float | None = None
    scale_y: float | None = None
    skew_x: float | None = None
    skew_y: float | None = None
    mirrored_x: bool | None = None
    mirrored_y: bool | None = None
    clip_path_reference: str | None = None
    clip_geometry: BoundingBox | None = None
    clip_status: PDFImageClipStatus = PDFImageClipStatus.CLIP_UNKNOWN
    soft_mask_reference: PDFImageMaskReference | None = None
    graphics_state_reference: PDFResourceReference | None = None
    transparency: PDFImageTransparency | None = None
    opacity: float | None = None
    blend_mode: str | None = None
    paint_order: PDFPaintOrder | None = None
    content_stream_order: int | None = None
    operation_order: int | None = None
    content_stream_reference: PDFContentStreamReference | None = None
    operation_reference: PDFOperationReference | None = None
    object_reference: PDFObjectReference | None = None
    parent_form_reference: PDFResourceReference | None = None
    form_occurrence_path: tuple[str, ...] = ()
    layer_reference: PDFResourceReference | None = None
    visibility: PDFImageVisibility = PDFImageVisibility.UNKNOWN
    effective_dpi_x: float | None = None
    effective_dpi_y: float | None = None
    source_reference: PDFResourceReference | None = None
    geometry_method: PDFImageExtractionMethod = PDFImageExtractionMethod.UNSUPPORTED
    geometry_confidence: float = 0.0
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("occurrence_id", self.occurrence_id)
        _validate_required_text("image_resource_id", self.image_resource_id)
        _validate_required_text("page_id", self.page_id)
        _validate_opacity_optional("opacity", self.opacity)
        _validate_positive_optional("effective_dpi_x", self.effective_dpi_x)
        _validate_positive_optional("effective_dpi_y", self.effective_dpi_y)
        _validate_confidence(self.geometry_confidence)


@dataclass(frozen=True, slots=True)
class PDFImageCapabilityMatrixEntry(Serializable):
    information: str
    support: PDFImageSupportStatus
    origin: str
    precision: str | None = None
    limitation: str | None = None

    def __post_init__(self) -> None:
        _validate_required_text("information", self.information)
        _validate_required_text("origin", self.origin)


@dataclass(frozen=True, slots=True)
class PDFImageCatalog(Serializable):
    resources: tuple[PDFImageResource, ...] = ()
    masks: tuple[PDFImageMaskReference, ...] = ()
    soft_masks: tuple[PDFSoftMaskResource, ...] = ()
    color_key_masks: tuple[PDFColorKeyMask, ...] = ()
    binary_representations: tuple[PDFImageBinaryReference, ...] = ()
    occurrences: tuple[PDFImageOccurrence, ...] = ()
    unresolved_resources: tuple[PDFResourceReference, ...] = ()
    unresolved_occurrences: tuple[str, ...] = ()
    capability_matrix: tuple[PDFImageCapabilityMatrixEntry, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def resource_by_id(self, image_resource_id: str) -> PDFImageResource | None:
        return next(
            (
                resource
                for resource in self.resources
                if resource.image_resource_id == image_resource_id
            ),
            None,
        )

    def occurrences_for_resource(
        self,
        image_resource_id: str,
    ) -> tuple[PDFImageOccurrence, ...]:
        return tuple(
            occurrence
            for occurrence in self.occurrences
            if occurrence.image_resource_id == image_resource_id
        )

    def occurrences_for_page(self, page_id: str) -> tuple[PDFImageOccurrence, ...]:
        return tuple(
            occurrence for occurrence in self.occurrences if occurrence.page_id == page_id
        )

    def masks_for_image(self, image_resource_id: str) -> tuple[PDFImageMaskReference, ...]:
        return tuple(
            mask for mask in self.masks if mask.masked_image_resource_id == image_resource_id
        )

    def resources_without_known_occurrence(self) -> tuple[PDFImageResource, ...]:
        used = {occurrence.image_resource_id for occurrence in self.occurrences}
        return tuple(
            resource
            for resource in self.resources
            if resource.image_resource_id not in used
        )

    def invisible_occurrences(self) -> tuple[PDFImageOccurrence, ...]:
        return tuple(
            occurrence
            for occurrence in self.occurrences
            if occurrence.visibility != PDFImageVisibility.VISIBLE
        )


@dataclass(frozen=True, slots=True)
class PDFPageImageLayer(Serializable):
    page_reference: PDFPageReference
    occurrence_ids: tuple[str, ...] = ()
    ordered_occurrence_ids: tuple[str, ...] = ()
    unresolved_occurrences: tuple[str, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None


@dataclass(frozen=True, slots=True)
class PDFNativeImageStatistics(Serializable):
    image_resource_count: int = 0
    image_occurrence_count: int = 0
    inline_image_count: int = 0
    image_mask_count: int = 0
    soft_mask_count: int = 0
    unresolved_resource_count: int = 0
    unresolved_occurrence_count: int = 0
    invisible_occurrence_count: int = 0
    reused_resource_count: int = 0
    normalized_export_count: int = 0

    def __post_init__(self) -> None:
        for name in (
            "image_resource_count",
            "image_occurrence_count",
            "inline_image_count",
            "image_mask_count",
            "soft_mask_count",
            "unresolved_resource_count",
            "unresolved_occurrence_count",
            "invisible_occurrence_count",
            "reused_resource_count",
            "normalized_export_count",
        ):
            _validate_non_negative_optional(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class PDFNativeImageArtifact(Serializable):
    artifact_version: ContractVersion
    provider: PDFProviderDescriptor
    image_catalog: PDFImageCatalog
    pages: tuple[PDFPageImageLayer, ...] = ()
    document_id: DocumentId | None = None
    source_structure_artifact: PDFInternalStructureArtifact | None = None
    statistics: PDFNativeImageStatistics = field(default_factory=PDFNativeImageStatistics)
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    provenance: PDFProviderProvenance | None = None


def image_resource_id(
    object_reference: PDFObjectReference | None = None,
    *,
    page_index: int | None = None,
    resource_name: str | None = None,
    inline_index: int | None = None,
    encoded_hash: str | None = None,
) -> str:
    if object_reference is not None:
        return f"pdfimage:{object_reference.stable_id}"
    if inline_index is not None:
        parts = ["pdfinline", f"page-{page_index}", f"inline-{inline_index}"]
        if encoded_hash:
            parts.append(encoded_hash[:12])
        return ":".join(str(part) for part in parts if part is not None)
    parts = ["pdfimage", f"page-{page_index}" if page_index is not None else "document"]
    if resource_name:
        parts.append(resource_name.strip("/"))
    if encoded_hash:
        parts.append(encoded_hash[:12])
    return ":".join(parts)


def image_occurrence_id(
    page_index: int,
    local_index: int,
    *,
    stream_index: int | None = None,
    operation_index: int | None = None,
    form_path: tuple[str, ...] = (),
) -> str:
    parts = ["pdfimageocc", f"page-{page_index}"]
    if stream_index is not None:
        parts.append(f"stream-{stream_index}")
    if operation_index is not None:
        parts.append(f"operation-{operation_index}")
    parts.append(f"occurrence-{local_index}")
    parts.extend(form_path)
    return ":".join(parts)


def image_binary_id(image_resource_id_value: str, representation: str) -> str:
    return f"pdfimagebin:{image_resource_id_value}:{representation}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def image_color_space_from_name(value: str | None) -> PDFImageColorSpace:
    if not value:
        return PDFImageColorSpace.UNKNOWN
    normalized = value.strip().lstrip("/")
    mapping = {
        "DeviceGray": PDFImageColorSpace.DEVICE_GRAY,
        "DeviceRGB": PDFImageColorSpace.DEVICE_RGB,
        "DeviceCMYK": PDFImageColorSpace.DEVICE_CMYK,
        "CalGray": PDFImageColorSpace.CAL_GRAY,
        "CalRGB": PDFImageColorSpace.CAL_RGB,
        "Lab": PDFImageColorSpace.LAB,
        "ICCBased": PDFImageColorSpace.ICC_BASED,
        "Indexed": PDFImageColorSpace.INDEXED,
        "Separation": PDFImageColorSpace.SEPARATION,
        "DeviceN": PDFImageColorSpace.DEVICE_N,
        "Pattern": PDFImageColorSpace.PATTERN,
    }
    return mapping.get(normalized, PDFImageColorSpace.UNKNOWN)


def _format_from_filters(filters: tuple[str, ...]) -> str | None:
    if not filters:
        return None
    normalized = filters[0].strip("/")
    mapping = {
        "DCTDecode": "jpeg",
        "JPXDecode": "jpeg2000",
        "CCITTFaxDecode": "ccitt",
        "JBIG2Decode": "jbig2",
        "FlateDecode": "raw_pdf_image_stream",
        "RunLengthDecode": "raw_pdf_image_stream",
        "LZWDecode": "raw_pdf_image_stream",
    }
    return mapping.get(normalized, normalized)


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
    "PDFColorKeyMask",
    "PDFImageBinaryFidelity",
    "PDFImageBinaryReference",
    "PDFImageBinaryRepresentation",
    "PDFImageCapabilityMatrixEntry",
    "PDFImageCatalog",
    "PDFImageClipStatus",
    "PDFImageColorSpace",
    "PDFImageExtractionMethod",
    "PDFImageExtractionOptions",
    "PDFImageKind",
    "PDFImageMaskReference",
    "PDFImageMaskType",
    "PDFImageOccurrence",
    "PDFImageResource",
    "PDFImageSupportStatus",
    "PDFImageTransparency",
    "PDFImageVisibility",
    "PDFNativeImageArtifact",
    "PDFNativeImageStatistics",
    "PDFPageImageLayer",
    "PDFSoftMaskResource",
    "image_binary_id",
    "image_color_space_from_name",
    "image_occurrence_id",
    "image_resource_id",
    "sha256_hex",
]
