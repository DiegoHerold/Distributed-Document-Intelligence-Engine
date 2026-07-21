from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from eixo.core import ArtifactId, ArtifactReference, DocumentId, EixoWarning
from eixo.core.serialization import Serializable
from eixo.core.timestamps import isoformat_utc, utc_now
from eixo.core.versions import ContractVersion, SchemaVersion
from eixo.pdf.inspection import PDFTechnicalInspection
from eixo.pdf.models import PDFProviderDescriptor, PDFProviderProvenance
from eixo.pdf.scene import PDFPageScene, PDFSceneEditabilityHint, PDFSceneFidelity


class PDFArtifactLimitationCategory(StrEnum):
    PROVIDER_LIMITATION = "provider_limitation"
    FORMAT_LIMITATION = "format_limitation"
    UNSUPPORTED_FEATURE = "unsupported_feature"
    PARTIAL_EXTRACTION = "partial_extraction"
    UNRESOLVED_RESOURCE = "unresolved_resource"
    GEOMETRY_LIMITATION = "geometry_limitation"
    PAINT_ORDER_LIMITATION = "paint_order_limitation"
    FONT_LIMITATION = "font_limitation"
    IMAGE_LIMITATION = "image_limitation"
    VECTOR_LIMITATION = "vector_limitation"
    INTERACTION_LIMITATION = "interaction_limitation"
    SECURITY_LIMITATION = "security_limitation"


class PDFNativeSceneEditabilityStatus(StrEnum):
    NATIVE_EDITABLE = "native_editable"
    PARTIALLY_EDITABLE = "partially_editable"
    RECONSTRUCTION_REQUIRED = "reconstruction_required"
    RASTER_ONLY = "raster_only"
    NOT_EDITABLE = "not_editable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class NativePDFSceneSourceArtifactReference(Serializable):
    source_artifact_id: str
    source_artifact_type: str
    artifact_version: ContractVersion | None = None
    schema_version: SchemaVersion | None = None
    artifact_reference: ArtifactReference | None = None
    provider: str | None = None
    provider_version: str | None = None
    content_hash: str | None = None

    def __post_init__(self) -> None:
        _validate_required_text("source_artifact_id", self.source_artifact_id)
        _validate_required_text("source_artifact_type", self.source_artifact_type)


@dataclass(frozen=True, slots=True)
class PDFConsolidatedWarning(Serializable):
    warning_id: str
    code: str
    severity: str
    message: str
    document_id: DocumentId | None = None
    page_id: str | None = None
    element_id: str | None = None
    source_artifact_id: str | None = None
    provider: str | None = None
    details: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_required_text("warning_id", self.warning_id)
        _validate_required_text("code", self.code)
        _validate_required_text("severity", self.severity)
        _validate_required_text("message", self.message)


@dataclass(frozen=True, slots=True)
class PDFArtifactLimitation(Serializable):
    code: str
    category: PDFArtifactLimitationCategory
    scope: str | None = None
    description: str | None = None
    impact: str | None = None
    fallback: str | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        _validate_required_text("code", self.code)


@dataclass(frozen=True, slots=True)
class PDFFidelityDimension(Serializable):
    dimension: str
    level: PDFSceneFidelity
    score: float | None = None
    method: str = "artifact_consolidation"
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_required_text("dimension", self.dimension)
        _validate_required_text("method", self.method)
        _validate_confidence_optional("score", self.score)


@dataclass(frozen=True, slots=True)
class PDFFidelitySummary(Serializable):
    overall_level: PDFSceneFidelity
    dimensions: tuple[PDFFidelityDimension, ...] = ()
    exact_element_count: int = 0
    normalized_element_count: int = 0
    reconstructed_element_count: int = 0
    heuristic_element_count: int = 0
    raster_only_element_count: int = 0
    unsupported_element_count: int = 0
    unknown_element_count: int = 0
    critical_limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "exact_element_count",
            "normalized_element_count",
            "reconstructed_element_count",
            "heuristic_element_count",
            "raster_only_element_count",
            "unsupported_element_count",
            "unknown_element_count",
        ):
            _validate_non_negative_optional(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class PDFEditabilitySummary(Serializable):
    overall_status: PDFNativeSceneEditabilityStatus
    text_status: PDFNativeSceneEditabilityStatus = PDFNativeSceneEditabilityStatus.UNKNOWN
    image_status: PDFNativeSceneEditabilityStatus = PDFNativeSceneEditabilityStatus.UNKNOWN
    vector_status: PDFNativeSceneEditabilityStatus = PDFNativeSceneEditabilityStatus.UNKNOWN
    form_status: PDFNativeSceneEditabilityStatus = PDFNativeSceneEditabilityStatus.UNKNOWN
    native_editable_count: int = 0
    partially_editable_count: int = 0
    reconstruction_required_count: int = 0
    raster_only_count: int = 0
    not_editable_count: int = 0
    unknown_count: int = 0
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "native_editable_count",
            "partially_editable_count",
            "reconstruction_required_count",
            "raster_only_count",
            "not_editable_count",
            "unknown_count",
        ):
            _validate_non_negative_optional(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class NativePDFScenePageSummary(Serializable):
    page_id: str
    page_index: int
    scene_reference: str
    element_count: int = 0
    text_count: int = 0
    image_count: int = 0
    vector_count: int = 0
    interactive_count: int = 0
    warning_count: int = 0
    fidelity: PDFSceneFidelity = PDFSceneFidelity.UNKNOWN
    editability: PDFNativeSceneEditabilityStatus = PDFNativeSceneEditabilityStatus.UNKNOWN

    def __post_init__(self) -> None:
        _validate_required_text("page_id", self.page_id)
        _validate_required_text("scene_reference", self.scene_reference)
        _validate_non_negative_optional("page_index", self.page_index)
        for name in (
            "element_count",
            "text_count",
            "image_count",
            "vector_count",
            "interactive_count",
            "warning_count",
        ):
            _validate_non_negative_optional(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class NativePDFSceneStatistics(Serializable):
    page_count: int = 0
    scene_count: int = 0
    element_count: int = 0
    text_element_count: int = 0
    image_resource_count: int = 0
    image_occurrence_count: int = 0
    vector_element_count: int = 0
    clipping_path_count: int = 0
    link_count: int = 0
    annotation_count: int = 0
    form_field_count: int = 0
    widget_count: int = 0
    layer_count: int = 0
    warning_count: int = 0
    limitation_count: int = 0
    unresolved_reference_count: int = 0
    native_exact_count: int = 0
    native_normalized_count: int = 0
    provider_reconstructed_count: int = 0
    heuristic_count: int = 0
    raster_only_count: int = 0
    unsupported_count: int = 0

    def __post_init__(self) -> None:
        for name in self.to_dict():
            _validate_non_negative_optional(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class NativePDFSceneProvenance(Serializable):
    capability: str = "native_pdf_scene"
    provider: str | None = None
    provider_version: str | None = None
    artifact_versions: dict[str, str] = field(default_factory=dict)
    input_document: str | None = None
    input_hash: str | None = None
    configurations: dict[str, str] = field(default_factory=dict)
    processing_profile: str | None = None
    job_id: str | None = None
    runtime: str | None = None
    created_at: str = field(default_factory=lambda: isoformat_utc(utc_now()))
    source_artifacts: tuple[NativePDFSceneSourceArtifactReference, ...] = ()
    transformations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NativePDFSceneArtifact(Serializable):
    artifact_id: ArtifactId
    artifact_type: str
    artifact_version: ContractVersion
    schema_version: SchemaVersion
    document_id: DocumentId | None = None
    source_document_reference: ArtifactReference | None = None
    source_hash: str | None = None
    created_at: str = field(default_factory=lambda: isoformat_utc(utc_now()))
    provider_summary: tuple[str, ...] = ()
    inspection: PDFTechnicalInspection | None = None
    resource_catalog_reference: str | None = None
    page_scene_references: tuple[str, ...] = ()
    pages: tuple[NativePDFScenePageSummary, ...] = ()
    scenes: tuple[PDFPageScene, ...] = ()
    font_catalog_reference: str | None = None
    text_artifact_reference: NativePDFSceneSourceArtifactReference | None = None
    image_artifact_reference: NativePDFSceneSourceArtifactReference | None = None
    vector_artifact_reference: NativePDFSceneSourceArtifactReference | None = None
    interactive_artifact_reference: NativePDFSceneSourceArtifactReference | None = None
    source_artifacts: tuple[NativePDFSceneSourceArtifactReference, ...] = ()
    fidelity_summary: PDFFidelitySummary = field(
        default_factory=lambda: PDFFidelitySummary(PDFSceneFidelity.UNKNOWN)
    )
    editability_summary: PDFEditabilitySummary = field(
        default_factory=lambda: PDFEditabilitySummary(
            PDFNativeSceneEditabilityStatus.UNKNOWN
        )
    )
    statistics: NativePDFSceneStatistics = field(default_factory=NativePDFSceneStatistics)
    warnings: tuple[PDFConsolidatedWarning, ...] = ()
    limitations: tuple[PDFArtifactLimitation, ...] = ()
    provenance: NativePDFSceneProvenance | PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        _validate_required_text("artifact_type", self.artifact_type)


def native_pdf_scene_artifact_id(
    document_id: DocumentId | None = None,
    source_hash: str | None = None,
) -> ArtifactId:
    seed = str(document_id) if document_id is not None else source_hash or "unknown"
    return ArtifactId.parse(f"art_native_pdf_scene_{_slug(seed)}")


def fidelity_counts(
    scenes: tuple[PDFPageScene, ...],
) -> dict[PDFSceneFidelity, int]:
    counts = {level: 0 for level in PDFSceneFidelity}
    for scene in scenes:
        for element in scene.elements:
            counts[element.fidelity] += 1
    return counts


def editability_counts(
    scenes: tuple[PDFPageScene, ...],
) -> dict[PDFSceneEditabilityHint, int]:
    counts = {status: 0 for status in PDFSceneEditabilityHint}
    for scene in scenes:
        for element in scene.elements:
            counts[element.editability_hint] += 1
    return counts


def _slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in safe.split("_") if part) or "unknown"


def _validate_required_text(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} is required")


def _validate_non_negative_optional(name: str, value: int | float | None) -> None:
    if value is not None and value < 0:
        raise ValueError(f"{name} cannot be negative")


def _validate_confidence_optional(name: str, value: float | None) -> None:
    if value is not None and (value < 0.0 or value > 1.0):
        raise ValueError(f"{name} must be between 0 and 1")


__all__ = [
    "NativePDFSceneArtifact",
    "NativePDFScenePageSummary",
    "NativePDFSceneProvenance",
    "NativePDFSceneSourceArtifactReference",
    "NativePDFSceneStatistics",
    "PDFArtifactLimitation",
    "PDFArtifactLimitationCategory",
    "PDFConsolidatedWarning",
    "PDFEditabilitySummary",
    "PDFFidelityDimension",
    "PDFFidelitySummary",
    "PDFNativeSceneEditabilityStatus",
    "editability_counts",
    "fidelity_counts",
    "native_pdf_scene_artifact_id",
]
