from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from eixo.core import DocumentId, EixoWarning, ProviderId
from eixo.core.serialization import Serializable
from eixo.core.versions import ContractVersion
from eixo.geometry import AffineMatrix, BoundingBox, Point, Quad
from eixo.pdf.models import PDFProviderDescriptor, PDFProviderProvenance, ProviderLimitation
from eixo.pdf.structure import (
    PDFContentStreamReference,
    PDFInternalStructureArtifact,
    PDFObjectReference,
    PDFOperationReference,
    PDFPageReference,
    PDFPaintOrder,
    PDFResourceReference,
)
from eixo.pdf.typography import (
    PDFFontResource,
    PDFTextDirection,
    PDFTextStyle,
    PDFTypographyArtifact,
    PDFWritingMode,
)


class PDFNativeTextGroupingMethod(StrEnum):
    NATIVE_PROVIDER = "native_provider"
    EIXO_CONSERVATIVE = "eixo_conservative"
    PROVIDER_DERIVED = "provider_derived"
    HEURISTIC = "heuristic"
    UNAVAILABLE = "unavailable"


class PDFNativeTextVisibility(StrEnum):
    VISIBLE = "visible"
    INVISIBLE_RENDER_MODE = "invisible_render_mode"
    FULLY_CLIPPED = "fully_clipped"
    PARTIALLY_CLIPPED = "partially_clipped"
    ZERO_OPACITY = "zero_opacity"
    OUTSIDE_CROP_BOX = "outside_crop_box"
    HIDDEN_BY_LAYER = "hidden_by_layer"
    UNKNOWN = "unknown"


class PDFNativeTextRelationType(StrEnum):
    GLYPH_BELONGS_TO_SPAN = "glyph_belongs_to_span"
    GLYPH_BELONGS_TO_WORD = "glyph_belongs_to_word"
    SPAN_BELONGS_TO_LINE = "span_belongs_to_line"
    LINE_BELONGS_TO_BLOCK = "line_belongs_to_block"
    WORD_INTERSECTS_SPAN = "word_intersects_span"
    ELEMENT_USES_FONT = "element_uses_font"
    ELEMENT_USES_STYLE = "element_uses_style"
    DERIVED_FROM_OPERATION = "derived_from_operation"
    PAINTED_IN_STREAM = "painted_in_stream"
    OCCURS_IN_FORM = "occurs_in_form"


class PDFNativeTextExtractionMethod(StrEnum):
    RAW_CONTENT_OPERATION = "raw_content_operation"
    PROVIDER_RAWDICT = "provider_rawdict"
    PROVIDER_WORDS = "provider_words"
    EIXO_GROUPING = "eixo_grouping"
    UNSUPPORTED = "unsupported"


class PDFNativeTextOrderConfidence(StrEnum):
    EXACT = "exact"
    HIGH = "high"
    PARTIAL = "partial"
    PROVIDER_APPROXIMATION = "provider_approximation"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class PDFNativeTextExtractionOptions(Serializable):
    include_glyphs: bool = True
    include_characters: bool = True
    include_words: bool = True
    include_native_lines: bool = True
    include_native_blocks: bool = True
    include_invisible_text: bool = True
    preserve_raw_text: bool = True
    normalize_unicode: bool = True
    page_selection: tuple[int, ...] | None = None
    max_glyphs_per_page: int | None = 250_000
    timeout_seconds: float | None = None
    preferred_provider: ProviderId | None = None

    def __post_init__(self) -> None:
        _validate_positive_optional("max_glyphs_per_page", self.max_glyphs_per_page)
        _validate_positive_optional("timeout_seconds", self.timeout_seconds)
        if self.page_selection is not None and any(page < 0 for page in self.page_selection):
            raise ValueError("page_selection cannot contain negative indexes")

    def safe_options(self) -> dict[str, Any]:
        return {
            "include_glyphs": self.include_glyphs,
            "include_characters": self.include_characters,
            "include_words": self.include_words,
            "include_native_lines": self.include_native_lines,
            "include_native_blocks": self.include_native_blocks,
            "include_invisible_text": self.include_invisible_text,
            "preserve_raw_text": self.preserve_raw_text,
            "normalize_unicode": self.normalize_unicode,
            "page_selection": list(self.page_selection) if self.page_selection else None,
            "max_glyphs_per_page": self.max_glyphs_per_page,
            "timeout_seconds": self.timeout_seconds,
            "preferred_provider": str(self.preferred_provider)
            if self.preferred_provider
            else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.safe_options()


@dataclass(frozen=True, slots=True)
class PDFTextBaseline(Serializable):
    baseline_id: str
    page_id: str
    start: Point | None = None
    end: Point | None = None
    angle_degrees: float | None = None
    confidence: float = 0.0
    extraction_method: PDFNativeTextExtractionMethod = (
        PDFNativeTextExtractionMethod.UNSUPPORTED
    )

    def __post_init__(self) -> None:
        _validate_required_text("baseline_id", self.baseline_id)
        _validate_required_text("page_id", self.page_id)
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class NativeGlyph(Serializable):
    glyph_id: str
    page_id: str
    font_id: str | None = None
    style_id: str | None = None
    char_code: int | None = None
    cid: int | None = None
    font_glyph_id: int | None = None
    unicode_text: str | None = None
    normalized_unicode_text: str | None = None
    origin: Point | None = None
    advance: float | None = None
    bounding_box: BoundingBox | None = None
    quad: Quad | None = None
    baseline_reference: str | None = None
    text_matrix: AffineMatrix | None = None
    effective_transform: AffineMatrix | None = None
    font_size: float | None = None
    writing_mode: PDFWritingMode = PDFWritingMode.UNKNOWN
    direction: PDFTextDirection = PDFTextDirection.UNKNOWN
    content_stream_reference: PDFContentStreamReference | None = None
    operation_reference: PDFOperationReference | None = None
    object_reference: PDFObjectReference | None = None
    paint_order: PDFPaintOrder | None = None
    source_order: int | None = None
    provider_order: int | None = None
    visibility: PDFNativeTextVisibility = PDFNativeTextVisibility.UNKNOWN
    clipped: bool | None = None
    render_mode: int | None = None
    mapping_confidence: float = 0.0
    geometry_confidence: float = 0.0
    extraction_method: PDFNativeTextExtractionMethod = (
        PDFNativeTextExtractionMethod.UNSUPPORTED
    )
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("glyph_id", self.glyph_id)
        _validate_required_text("page_id", self.page_id)
        _validate_non_negative_optional("char_code", self.char_code)
        _validate_non_negative_optional("cid", self.cid)
        _validate_non_negative_optional("font_glyph_id", self.font_glyph_id)
        _validate_non_negative_optional("source_order", self.source_order)
        _validate_non_negative_optional("provider_order", self.provider_order)
        _validate_positive_optional("font_size", self.font_size)
        _validate_confidence(self.mapping_confidence)
        _validate_confidence(self.geometry_confidence)


@dataclass(frozen=True, slots=True)
class NativeCharacter(Serializable):
    character_id: str
    page_id: str
    glyph_ids: tuple[str, ...]
    unicode_text: str
    normalized_unicode_text: str | None = None
    unicode_codepoints: tuple[str, ...] = ()
    mapping_confidence: float = 0.0
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("character_id", self.character_id)
        _validate_required_text("page_id", self.page_id)
        if self.unicode_text == "":
            raise ValueError("unicode_text is required")
        if not self.glyph_ids:
            raise ValueError("NativeCharacter requires at least one glyph")
        _validate_confidence(self.mapping_confidence)


@dataclass(frozen=True, slots=True)
class NativeWord(Serializable):
    word_id: str
    page_id: str
    glyph_ids: tuple[str, ...]
    character_ids: tuple[str, ...] = ()
    text: str | None = None
    normalized_text: str | None = None
    bounding_box: BoundingBox | None = None
    quad: Quad | None = None
    grouping_method: PDFNativeTextGroupingMethod = (
        PDFNativeTextGroupingMethod.UNAVAILABLE
    )
    confidence: float = 0.0
    source_order: int | None = None
    provider_order: int | None = None
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("word_id", self.word_id)
        _validate_required_text("page_id", self.page_id)
        if not self.glyph_ids:
            raise ValueError("NativeWord requires at least one glyph")
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class NativeTextSpan(Serializable):
    span_id: str
    page_id: str
    glyph_ids: tuple[str, ...]
    character_ids: tuple[str, ...] = ()
    word_ids: tuple[str, ...] = ()
    style_id: str | None = None
    font_id: str | None = None
    raw_text: str | None = None
    normalized_text: str | None = None
    bounding_box: BoundingBox | None = None
    quad: Quad | None = None
    baseline_reference: str | None = None
    grouping_method: PDFNativeTextGroupingMethod = (
        PDFNativeTextGroupingMethod.UNAVAILABLE
    )
    confidence: float = 0.0
    source_order: int | None = None
    provider_order: int | None = None
    paint_order: PDFPaintOrder | None = None
    extraction_method: PDFNativeTextExtractionMethod = (
        PDFNativeTextExtractionMethod.UNSUPPORTED
    )
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("span_id", self.span_id)
        _validate_required_text("page_id", self.page_id)
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class NativeTextLine(Serializable):
    line_id: str
    page_id: str
    span_ids: tuple[str, ...]
    word_ids: tuple[str, ...] = ()
    glyph_ids: tuple[str, ...] = ()
    baseline_id: str | None = None
    raw_text: str | None = None
    bounding_box: BoundingBox | None = None
    direction: PDFTextDirection = PDFTextDirection.UNKNOWN
    grouping_method: PDFNativeTextGroupingMethod = (
        PDFNativeTextGroupingMethod.UNAVAILABLE
    )
    confidence: float = 0.0
    source_order: int | None = None
    provider_order: int | None = None
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("line_id", self.line_id)
        _validate_required_text("page_id", self.page_id)
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class NativeTextBlock(Serializable):
    block_id: str
    page_id: str
    line_ids: tuple[str, ...]
    span_ids: tuple[str, ...] = ()
    word_ids: tuple[str, ...] = ()
    glyph_ids: tuple[str, ...] = ()
    raw_text: str | None = None
    bounding_box: BoundingBox | None = None
    grouping_method: PDFNativeTextGroupingMethod = (
        PDFNativeTextGroupingMethod.UNAVAILABLE
    )
    confidence: float = 0.0
    source_order: int | None = None
    provider_order: int | None = None
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("block_id", self.block_id)
        _validate_required_text("page_id", self.page_id)
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class PDFNativeTextRelation(Serializable):
    source_id: str
    target_id: str
    relation_type: PDFNativeTextRelationType
    confidence: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_required_text("source_id", self.source_id)
        _validate_required_text("target_id", self.target_id)
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class PDFPageNativeTextLayer(Serializable):
    page_reference: PDFPageReference
    glyphs: tuple[NativeGlyph, ...] = ()
    characters: tuple[NativeCharacter, ...] = ()
    words: tuple[NativeWord, ...] = ()
    spans: tuple[NativeTextSpan, ...] = ()
    baselines: tuple[PDFTextBaseline, ...] = ()
    lines: tuple[NativeTextLine, ...] = ()
    blocks: tuple[NativeTextBlock, ...] = ()
    relations: tuple[PDFNativeTextRelation, ...] = ()
    unresolved_text: tuple[str, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    provenance: PDFProviderProvenance | None = None


@dataclass(frozen=True, slots=True)
class PDFNativeTextStatistics(Serializable):
    glyph_count: int = 0
    character_count: int = 0
    word_count: int = 0
    span_count: int = 0
    line_count: int = 0
    block_count: int = 0
    unresolved_unicode_count: int = 0
    unresolved_font_count: int = 0
    invisible_text_count: int = 0
    rotated_text_count: int = 0
    vertical_text_count: int = 0

    def __post_init__(self) -> None:
        for name in (
            "glyph_count",
            "character_count",
            "word_count",
            "span_count",
            "line_count",
            "block_count",
            "unresolved_unicode_count",
            "unresolved_font_count",
            "invisible_text_count",
            "rotated_text_count",
            "vertical_text_count",
        ):
            _validate_non_negative_optional(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class PDFNativeTextLayer(Serializable):
    page_text_layers: tuple[PDFPageNativeTextLayer, ...] = ()
    text_styles: tuple[PDFTextStyle, ...] = ()
    font_references: tuple[PDFFontResource, ...] = ()
    unresolved_text: tuple[str, ...] = ()
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    provenance: PDFProviderProvenance | None = None


@dataclass(frozen=True, slots=True)
class PDFNativeTextArtifact(Serializable):
    artifact_version: ContractVersion
    provider: PDFProviderDescriptor
    document_id: DocumentId | None = None
    source_structure_artifact: PDFInternalStructureArtifact | None = None
    typography_artifact: PDFTypographyArtifact | None = None
    pages: tuple[PDFPageNativeTextLayer, ...] = ()
    text_layer: PDFNativeTextLayer | None = None
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    statistics: PDFNativeTextStatistics = field(default_factory=PDFNativeTextStatistics)
    provenance: PDFProviderProvenance | None = None


def native_glyph_id(page_index: int, span_index: int, glyph_index: int) -> str:
    return f"pdfglyph:page-{page_index}:span-{span_index}:glyph-{glyph_index}"


def native_character_id(glyph_id: str, character_index: int = 0) -> str:
    return f"pdfchar:{glyph_id}:{character_index}"


def native_word_id(page_index: int, line_index: int, word_index: int) -> str:
    return f"pdfword:page-{page_index}:line-{line_index}:word-{word_index}"


def native_span_id(page_index: int, block_index: int, line_index: int, span_index: int) -> str:
    return f"pdfspan:page-{page_index}:block-{block_index}:line-{line_index}:span-{span_index}"


def native_line_id(page_index: int, block_index: int, line_index: int) -> str:
    return f"pdfline:page-{page_index}:block-{block_index}:line-{line_index}"


def native_block_id(page_index: int, block_index: int) -> str:
    return f"pdfblock:page-{page_index}:block-{block_index}"


def native_baseline_id(page_index: int, block_index: int, line_index: int) -> str:
    return f"pdfbaseline:page-{page_index}:block-{block_index}:line-{line_index}"


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


__all__ = [
    "NativeCharacter",
    "NativeGlyph",
    "NativeTextBlock",
    "NativeTextLine",
    "NativeTextSpan",
    "NativeWord",
    "PDFNativeTextArtifact",
    "PDFNativeTextExtractionMethod",
    "PDFNativeTextExtractionOptions",
    "PDFNativeTextGroupingMethod",
    "PDFNativeTextLayer",
    "PDFNativeTextOrderConfidence",
    "PDFNativeTextRelation",
    "PDFNativeTextRelationType",
    "PDFNativeTextStatistics",
    "PDFNativeTextVisibility",
    "PDFPageNativeTextLayer",
    "PDFTextBaseline",
    "native_baseline_id",
    "native_block_id",
    "native_character_id",
    "native_glyph_id",
    "native_line_id",
    "native_span_id",
    "native_word_id",
]
