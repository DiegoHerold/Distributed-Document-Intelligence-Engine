from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from eixo.core import ArtifactReference, DocumentId, EixoWarning, ProviderId
from eixo.core.serialization import Serializable
from eixo.core.versions import ContractVersion
from eixo.geometry import AffineMatrix, BoundingBox
from eixo.pdf.models import PDFProviderDescriptor, PDFProviderProvenance, ProviderLimitation
from eixo.pdf.structure import (
    PDFFontResourceDescriptor,
    PDFInternalStructureArtifact,
    PDFMappingStatus,
    PDFObjectReference,
    PDFPageReference,
    PDFResourceReference,
)


class PDFTypographySupportStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    PROVIDER_DERIVED = "provider_derived"
    HEURISTIC = "heuristic"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"
    EXTRACTION_FAILED = "extraction_failed"


class PDFFontType(StrEnum):
    TYPE0 = "Type0"
    TYPE1 = "Type1"
    MM_TYPE1 = "MMType1"
    TYPE3 = "Type3"
    TRUE_TYPE = "TrueType"
    CID_FONT_TYPE0 = "CIDFontType0"
    CID_FONT_TYPE2 = "CIDFontType2"
    UNKNOWN = "Unknown"


class PDFFontEmbeddedStatus(StrEnum):
    NOT_EMBEDDED = "not_embedded"
    EMBEDDED_COMPLETE = "embedded_complete"
    EMBEDDED_SUBSET = "embedded_subset"
    EMBEDDED_UNKNOWN = "embedded_unknown"
    EXTRACTION_UNAVAILABLE = "extraction_unavailable"


class PDFFontFamilyResolutionMethod(StrEnum):
    EXPLICIT = "explicit"
    SUBSET_PREFIX_STRIPPED = "subset_prefix_stripped"
    PROVIDER_DERIVED = "provider_derived"
    HEURISTIC = "heuristic"
    UNRESOLVED = "unresolved"


class PDFGlyphMappingMethod(StrEnum):
    TO_UNICODE = "to_unicode"
    ENCODING_TABLE = "encoding_table"
    CMAP = "cmap"
    PROVIDER_MAPPING = "provider_mapping"
    GLYPH_NAME = "glyph_name"
    HEURISTIC = "heuristic"
    UNRESOLVED = "unresolved"


class PDFMetricSource(StrEnum):
    FONT_PROGRAM = "font_program"
    PDF_DICTIONARY = "pdf_dictionary"
    PROVIDER = "provider"
    OBSERVED_OCCURRENCE = "observed_occurrence"
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"


class PDFWritingMode(StrEnum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    ROTATED = "rotated"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class PDFTextDirection(StrEnum):
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"
    TOP_TO_BOTTOM = "top_to_bottom"
    BOTTOM_TO_TOP = "bottom_to_top"
    VERTICAL = "vertical"
    ROTATED = "rotated"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class PDFColorConversionPrecision(StrEnum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class PDFTypographyOptions(Serializable):
    include_font_programs: bool = False
    include_glyph_mappings: bool = True
    include_text_styles: bool = True
    page_selection: tuple[int, ...] | None = None
    max_fonts: int | None = 10_000
    max_glyph_mappings: int | None = 250_000
    timeout_seconds: float | None = None
    preferred_provider: ProviderId | None = None

    def __post_init__(self) -> None:
        _validate_positive_optional("max_fonts", self.max_fonts)
        _validate_positive_optional("max_glyph_mappings", self.max_glyph_mappings)
        _validate_positive_optional("timeout_seconds", self.timeout_seconds)
        if self.page_selection is not None and any(page < 0 for page in self.page_selection):
            raise ValueError("page_selection cannot contain negative indexes")

    def safe_options(self) -> dict[str, Any]:
        return {
            "include_font_programs": self.include_font_programs,
            "include_glyph_mappings": self.include_glyph_mappings,
            "include_text_styles": self.include_text_styles,
            "page_selection": list(self.page_selection) if self.page_selection else None,
            "max_fonts": self.max_fonts,
            "max_glyph_mappings": self.max_glyph_mappings,
            "timeout_seconds": self.timeout_seconds,
            "preferred_provider": str(self.preferred_provider)
            if self.preferred_provider
            else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.safe_options()


@dataclass(frozen=True, slots=True)
class PDFFontProgramReference(Serializable):
    artifact_reference: ArtifactReference | None = None
    content_hash: str | None = None
    format: str | None = None
    size_bytes: int | None = None
    embedded_status: PDFFontEmbeddedStatus = PDFFontEmbeddedStatus.EMBEDDED_UNKNOWN
    extraction_method: str | None = None

    def __post_init__(self) -> None:
        _validate_non_negative_optional("size_bytes", self.size_bytes)


@dataclass(frozen=True, slots=True)
class PDFEncoding(Serializable):
    encoding_id: str
    name: str | None = None
    object_reference: PDFObjectReference | None = None
    base_encoding: str | None = None
    differences: tuple[str, ...] = ()
    custom: bool | None = None
    status: PDFTypographySupportStatus = PDFTypographySupportStatus.UNKNOWN
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("encoding_id", self.encoding_id)


@dataclass(frozen=True, slots=True)
class PDFCMapReference(Serializable):
    cmap_id: str
    name: str | None = None
    object_reference: PDFObjectReference | None = None
    cid_system_info: dict[str, str] = field(default_factory=dict)
    writing_mode: PDFWritingMode = PDFWritingMode.UNKNOWN
    status: PDFTypographySupportStatus = PDFTypographySupportStatus.UNKNOWN
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("cmap_id", self.cmap_id)


@dataclass(frozen=True, slots=True)
class PDFUnicodeMapping(Serializable):
    mapping_id: str
    font_id: str
    char_code: int | None = None
    cid: int | None = None
    glyph_id: int | None = None
    unicode_text: str | None = None
    normalized_unicode_text: str | None = None
    to_unicode_reference: PDFObjectReference | None = None
    cmap_reference: PDFCMapReference | None = None
    method: PDFGlyphMappingMethod = PDFGlyphMappingMethod.UNRESOLVED
    confidence: float = 0.0
    warnings: tuple[EixoWarning, ...] = ()

    def __post_init__(self) -> None:
        _validate_required_text("mapping_id", self.mapping_id)
        _validate_required_text("font_id", self.font_id)
        _validate_confidence(self.confidence)
        _validate_non_negative_optional("char_code", self.char_code)
        _validate_non_negative_optional("cid", self.cid)
        _validate_non_negative_optional("glyph_id", self.glyph_id)


@dataclass(frozen=True, slots=True)
class PDFGlyphMapping(Serializable):
    mapping_id: str
    font_id: str
    char_code: int | None = None
    cid: int | None = None
    glyph_id: int | None = None
    unicode_text: str | None = None
    normalized_unicode_text: str | None = None
    mapping_method: PDFGlyphMappingMethod = PDFGlyphMappingMethod.UNRESOLVED
    confidence: float = 0.0
    warnings: tuple[EixoWarning, ...] = ()

    def __post_init__(self) -> None:
        _validate_required_text("mapping_id", self.mapping_id)
        _validate_required_text("font_id", self.font_id)
        _validate_confidence(self.confidence)
        _validate_non_negative_optional("char_code", self.char_code)
        _validate_non_negative_optional("cid", self.cid)
        _validate_non_negative_optional("glyph_id", self.glyph_id)


@dataclass(frozen=True, slots=True)
class PDFFontResource(Serializable):
    font_id: str
    resource_name: str | None = None
    object_reference: PDFObjectReference | None = None
    resource_reference: PDFResourceReference | None = None
    scope: str | None = None
    subtype: PDFFontType = PDFFontType.UNKNOWN
    base_font_name: str | None = None
    internal_font_name: str | None = None
    postscript_name: str | None = None
    normalized_family: str | None = None
    family_resolution_method: PDFFontFamilyResolutionMethod = (
        PDFFontFamilyResolutionMethod.UNRESOLVED
    )
    family_resolution_confidence: float = 0.0
    encoding: PDFEncoding | None = None
    encoding_reference: PDFObjectReference | None = None
    to_unicode_reference: PDFObjectReference | None = None
    cmap_reference: PDFCMapReference | None = None
    font_descriptor_reference: PDFObjectReference | None = None
    descendant_font_references: tuple[PDFObjectReference, ...] = ()
    embedded_program_reference: PDFFontProgramReference | None = None
    subset: bool | None = None
    subset_prefix: str | None = None
    embedded: PDFFontEmbeddedStatus = PDFFontEmbeddedStatus.EMBEDDED_UNKNOWN
    vertical_writing: bool | None = None
    symbolic: bool | None = None
    serif: bool | None = None
    fixed_pitch: bool | None = None
    italic: bool | None = None
    italic_source: PDFMetricSource = PDFMetricSource.UNKNOWN
    weight: int | None = None
    weight_source: PDFMetricSource = PDFMetricSource.UNKNOWN
    font_bbox: BoundingBox | None = None
    units_per_em: int | None = None
    ascent: float | None = None
    descent: float | None = None
    cap_height: float | None = None
    x_height: float | None = None
    italic_angle: float | None = None
    stem_v: float | None = None
    widths: tuple[float, ...] = ()
    default_width: float | None = None
    missing_width: float | None = None
    flags: int | None = None
    pages_using_font: tuple[PDFPageReference, ...] = ()
    forms_using_font: tuple[PDFResourceReference, ...] = ()
    status: PDFMappingStatus = PDFMappingStatus.UNKNOWN
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("font_id", self.font_id)
        _validate_confidence(self.family_resolution_confidence)
        _validate_non_negative_optional("units_per_em", self.units_per_em)
        _validate_non_negative_optional("weight", self.weight)

    @classmethod
    def from_descriptor(cls, descriptor: PDFFontResourceDescriptor) -> "PDFFontResource":
        internal_name = descriptor.base_font or descriptor.reference.resource_name
        subset_prefix, cleaned_name = split_subset_font_name(internal_name)
        family, method, confidence = normalize_font_family(cleaned_name)
        encoding_name = _encoding_from_descriptor(descriptor)
        encoding = (
            PDFEncoding(
                encoding_id=f"pdfencoding:{descriptor.reference.resource_id}",
                name=encoding_name,
                status=PDFTypographySupportStatus.PROVIDER_DERIVED,
                provenance=descriptor.provenance,
            )
            if encoding_name
            else None
        )
        subtype = font_type_from_provider(descriptor.font_subtype)
        embedded_status = (
            PDFFontEmbeddedStatus.EMBEDDED_SUBSET
            if descriptor.embedded_font_reference is not None and subset_prefix
            else PDFFontEmbeddedStatus.EMBEDDED_UNKNOWN
            if descriptor.embedded_font_reference is not None
            else PDFFontEmbeddedStatus.EXTRACTION_UNAVAILABLE
        )
        program = (
            PDFFontProgramReference(
                embedded_status=embedded_status,
                extraction_method="provider_reference_only",
            )
            if descriptor.embedded_font_reference is not None
            else None
        )
        return cls(
            font_id=descriptor.reference.resource_id,
            resource_name=descriptor.reference.resource_name,
            object_reference=descriptor.object_reference,
            resource_reference=descriptor.reference,
            scope=descriptor.reference.scope.value,
            subtype=subtype,
            base_font_name=descriptor.base_font,
            internal_font_name=internal_name,
            postscript_name=cleaned_name,
            normalized_family=family,
            family_resolution_method=method,
            family_resolution_confidence=confidence,
            encoding=encoding,
            encoding_reference=descriptor.encoding_reference,
            to_unicode_reference=descriptor.to_unicode_reference,
            font_descriptor_reference=descriptor.font_descriptor_reference,
            descendant_font_references=descriptor.descendant_font_references,
            embedded_program_reference=program,
            subset=bool(subset_prefix) if internal_name else None,
            subset_prefix=subset_prefix,
            embedded=embedded_status,
            vertical_writing=_is_vertical_encoding(encoding_name),
            pages_using_font=descriptor.pages_using_resource,
            forms_using_font=descriptor.forms_using_resource,
            status=descriptor.status,
            provenance=descriptor.provenance,
        )


@dataclass(frozen=True, slots=True)
class PDFTextColor(Serializable):
    original_value: str | tuple[float, ...] | None = None
    color_space: str | None = None
    normalized_rgb: tuple[float, float, float] | None = None
    source: PDFMetricSource = PDFMetricSource.UNKNOWN
    conversion_precision: PDFColorConversionPrecision = (
        PDFColorConversionPrecision.UNAVAILABLE
    )


@dataclass(frozen=True, slots=True)
class PDFTextStyle(Serializable):
    style_id: str
    font_id: str | None = None
    font_size: float | None = None
    font_weight: int | None = None
    weight_source: PDFMetricSource = PDFMetricSource.UNKNOWN
    italic: bool | None = None
    italic_source: PDFMetricSource = PDFMetricSource.UNKNOWN
    synthetic_bold: bool | None = None
    synthetic_italic: bool | None = None
    fill_color: PDFTextColor | None = None
    stroke_color: PDFTextColor | None = None
    fill_opacity: float | None = None
    stroke_opacity: float | None = None
    text_render_mode: int | None = None
    character_spacing: float | None = None
    word_spacing: float | None = None
    horizontal_scaling: float | None = None
    leading: float | None = None
    text_rise: float | None = None
    writing_mode: PDFWritingMode = PDFWritingMode.UNKNOWN
    direction: PDFTextDirection = PDFTextDirection.UNKNOWN
    blend_mode: str | None = None
    graphics_state_reference: PDFResourceReference | None = None
    text_matrix: AffineMatrix | None = None
    effective_transform: AffineMatrix | None = None
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("style_id", self.style_id)
        _validate_positive_optional("font_size", self.font_size)
        _validate_non_negative_optional("font_weight", self.font_weight)
        _validate_opacity_optional("fill_opacity", self.fill_opacity)
        _validate_opacity_optional("stroke_opacity", self.stroke_opacity)


@dataclass(frozen=True, slots=True)
class PDFFontUsage(Serializable):
    usage_id: str
    font_id: str
    page_reference: PDFPageReference | None = None
    content_stream_reference: str | None = None
    element_id: str | None = None
    style_id: str | None = None
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("usage_id", self.usage_id)
        _validate_required_text("font_id", self.font_id)


@dataclass(frozen=True, slots=True)
class PDFFontCapabilityMatrixEntry(Serializable):
    information: str
    support: PDFTypographySupportStatus
    origin: str
    precision: str | None = None
    limitation: str | None = None

    def __post_init__(self) -> None:
        _validate_required_text("information", self.information)
        _validate_required_text("origin", self.origin)


@dataclass(frozen=True, slots=True)
class PDFFontCatalog(Serializable):
    fonts: tuple[PDFFontResource, ...] = ()
    font_programs: tuple[PDFFontProgramReference, ...] = ()
    encodings: tuple[PDFEncoding, ...] = ()
    cmaps: tuple[PDFCMapReference, ...] = ()
    glyph_mappings: tuple[PDFGlyphMapping, ...] = ()
    text_styles: tuple[PDFTextStyle, ...] = ()
    font_usages: tuple[PDFFontUsage, ...] = ()
    unresolved_fonts: tuple[PDFResourceReference, ...] = ()
    capability_matrix: tuple[PDFFontCapabilityMatrixEntry, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def font_by_id(self, font_id: str) -> PDFFontResource | None:
        return next((font for font in self.fonts if font.font_id == font_id), None)

    def fonts_for_page(self, page_index: int) -> tuple[PDFFontResource, ...]:
        return tuple(
            font
            for font in self.fonts
            if any(page.page_index == page_index for page in font.pages_using_font)
        )

    def usages_for_font(self, font_id: str) -> tuple[PDFFontUsage, ...]:
        return tuple(usage for usage in self.font_usages if usage.font_id == font_id)

    def styles_for_font(self, font_id: str) -> tuple[PDFTextStyle, ...]:
        return tuple(style for style in self.text_styles if style.font_id == font_id)

    def fonts_without_unicode(self) -> tuple[PDFFontResource, ...]:
        mapped = {mapping.font_id for mapping in self.glyph_mappings if mapping.unicode_text}
        return tuple(font for font in self.fonts if font.font_id not in mapped)

    def partially_resolved_fonts(self) -> tuple[PDFFontResource, ...]:
        return tuple(
            font
            for font in self.fonts
            if font.status
            in {PDFMappingStatus.PARTIALLY_RECOVERED, PDFMappingStatus.UNKNOWN}
        )


@dataclass(frozen=True, slots=True)
class PDFTypographyArtifact(Serializable):
    artifact_version: ContractVersion
    provider: PDFProviderDescriptor
    font_catalog: PDFFontCatalog
    document_id: DocumentId | None = None
    source_structure_artifact: PDFInternalStructureArtifact | None = None
    text_styles: tuple[PDFTextStyle, ...] = ()
    unresolved_resources: tuple[PDFResourceReference, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    provenance: PDFProviderProvenance | None = None


def split_subset_font_name(name: str | None) -> tuple[str | None, str | None]:
    if not name:
        return None, None
    cleaned = name.strip().lstrip("/")
    match = re.match(r"^([A-Z]{6})\+(.+)$", cleaned)
    if not match:
        return None, cleaned
    return match.group(1), match.group(2)


def normalize_font_family(
    name: str | None,
) -> tuple[str | None, PDFFontFamilyResolutionMethod, float]:
    if not name:
        return None, PDFFontFamilyResolutionMethod.UNRESOLVED, 0.0
    cleaned = name.strip().lstrip("/")
    if not cleaned:
        return None, PDFFontFamilyResolutionMethod.UNRESOLVED, 0.0
    base = cleaned.split("-", 1)[0]
    for suffix in ("Bold", "Italic", "Oblique", "Regular", "MT", "PS"):
        if base.endswith(suffix) and len(base) > len(suffix):
            base = base[: -len(suffix)]
    if base != cleaned:
        return base, PDFFontFamilyResolutionMethod.HEURISTIC, 0.65
    return cleaned, PDFFontFamilyResolutionMethod.PROVIDER_DERIVED, 0.75


def font_type_from_provider(value: str | None) -> PDFFontType:
    if not value:
        return PDFFontType.UNKNOWN
    normalized = value.replace(" ", "").lower()
    mapping = {
        "type0": PDFFontType.TYPE0,
        "type1": PDFFontType.TYPE1,
        "mmtype1": PDFFontType.MM_TYPE1,
        "type3": PDFFontType.TYPE3,
        "truetype": PDFFontType.TRUE_TYPE,
        "cidfonttype0": PDFFontType.CID_FONT_TYPE0,
        "cidfonttype2": PDFFontType.CID_FONT_TYPE2,
    }
    return mapping.get(normalized, PDFFontType.UNKNOWN)


def typography_style_id(
    font_id: str | None,
    font_size: float | None,
    fill_color: str | None = None,
    render_mode: int | None = None,
) -> str:
    parts = [
        "pdfstyle",
        font_id or "unknown-font",
        _stable_float(font_size),
        fill_color or "unknown-color",
        str(render_mode) if render_mode is not None else "unknown-render",
    ]
    return ":".join(part.replace(" ", "_") for part in parts)


def glyph_mapping_id(font_id: str, index: int | str) -> str:
    return f"pdfglyphmap:{font_id}:{index}"


def _encoding_from_descriptor(descriptor: PDFFontResourceDescriptor) -> str | None:
    provider_tuple = descriptor.dictionary_summary.get("provider_tuple")
    if not provider_tuple:
        return None
    parts = provider_tuple.split("|")
    return parts[5] if len(parts) > 5 and parts[5] else None


def _is_vertical_encoding(value: str | None) -> bool | None:
    if not value:
        return None
    return value.endswith("-V") or "Vertical" in value


def _stable_float(value: float | None) -> str:
    if value is None:
        return "unknown-size"
    return f"{value:.6g}"


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
    "PDFCMapReference",
    "PDFColorConversionPrecision",
    "PDFEncoding",
    "PDFFontCatalog",
    "PDFFontCapabilityMatrixEntry",
    "PDFFontEmbeddedStatus",
    "PDFFontFamilyResolutionMethod",
    "PDFFontProgramReference",
    "PDFFontResource",
    "PDFFontType",
    "PDFFontUsage",
    "PDFGlyphMapping",
    "PDFGlyphMappingMethod",
    "PDFMetricSource",
    "PDFTextColor",
    "PDFTextDirection",
    "PDFTextStyle",
    "PDFTypographyArtifact",
    "PDFTypographyOptions",
    "PDFTypographySupportStatus",
    "PDFUnicodeMapping",
    "PDFWritingMode",
    "font_type_from_provider",
    "glyph_mapping_id",
    "normalize_font_family",
    "split_subset_font_name",
    "typography_style_id",
]
