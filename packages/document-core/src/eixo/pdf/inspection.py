from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from eixo.core import ArtifactReference, DocumentSource, EixoWarning, ProviderId
from eixo.core.serialization import Serializable
from eixo.core.versions import ContractVersion
from eixo.geometry import PageGeometry
from eixo.pdf.models import (
    PDFEncryptionState,
    PDFProviderDescriptor,
    PDFProviderProvenance,
    PDFSupportLevel,
    ProviderLimitation,
)


class PDFInspectionState(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"
    NOT_INSPECTED = "not_inspected"
    NOT_APPLICABLE = "not_applicable"
    UNSUPPORTED = "unsupported"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"


class PDFIntegrityStatus(StrEnum):
    VALID = "valid"
    VALID_WITH_WARNINGS = "valid_with_warnings"
    PARTIALLY_VALID = "partially_valid"
    REPAIRED = "repaired"
    CORRUPTED = "corrupted"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"
    INCONCLUSIVE = "inconclusive"


class PDFSecurityStatus(StrEnum):
    NOT_ENCRYPTED = "not_encrypted"
    ENCRYPTED_UNLOCKED = "encrypted_unlocked"
    ENCRYPTED_PASSWORD_REQUIRED = "encrypted_password_required"
    ENCRYPTED_INVALID_PASSWORD = "encrypted_invalid_password"
    ENCRYPTED_PARTIALLY_SUPPORTED = "encrypted_partially_supported"
    ENCRYPTED_UNSUPPORTED = "encrypted_unsupported"
    UNKNOWN = "unknown"


class PDFPermissionStatus(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    UNSUPPORTED = "unsupported"


class PDFSamplingStrategy(StrEnum):
    ALL = "all"
    FIRST = "first"
    FIRST_MIDDLE_LAST = "first_middle_last"
    UNIFORM = "uniform"


class PDFTechnicalProfile(StrEnum):
    DIGITAL_TEXT = "digital_text"
    IMAGE_BASED = "image_based"
    MIXED = "mixed"
    VECTOR_DOMINANT = "vector_dominant"
    FORM_DOCUMENT = "form_document"
    INTERACTIVE = "interactive"
    UNKNOWN = "unknown"


class PDFInspectionFailurePolicy(StrEnum):
    RETURN_PARTIAL = "return_partial"
    FAIL_FAST = "fail_fast"


@dataclass(frozen=True, slots=True)
class PDFInspectionOptions(Serializable):
    password: str | None = field(default=None, repr=False)
    strict_validation: bool = True
    tolerate_partial_corruption: bool = False
    inspect_all_pages: bool = True
    max_pages_to_inspect: int | None = None
    sampling_strategy: PDFSamplingStrategy = PDFSamplingStrategy.ALL
    inspect_metadata: bool = True
    inspect_security: bool = True
    inspect_permissions: bool = True
    inspect_resources: bool = True
    inspect_text: bool = True
    inspect_images: bool = True
    inspect_vectors: bool = True
    inspect_links: bool = True
    inspect_annotations: bool = True
    inspect_forms: bool = True
    inspect_layers: bool = True
    timeout_seconds: float | None = None
    max_objects: int | None = None
    max_resources: int | None = None
    max_structure_depth: int | None = None
    max_memory_bytes: int | None = None
    failure_policy: PDFInspectionFailurePolicy = PDFInspectionFailurePolicy.RETURN_PARTIAL
    preferred_provider: ProviderId | None = None
    detail_level: str = "technical"
    include_raw_metadata: bool = False

    def __post_init__(self) -> None:
        for name in (
            "max_pages_to_inspect",
            "max_objects",
            "max_resources",
            "max_structure_depth",
            "max_memory_bytes",
        ):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not self.detail_level.strip():
            raise ValueError("detail_level cannot be empty")

    def safe_options(self) -> dict[str, Any]:
        return {
            "strict_validation": self.strict_validation,
            "tolerate_partial_corruption": self.tolerate_partial_corruption,
            "inspect_all_pages": self.inspect_all_pages,
            "max_pages_to_inspect": self.max_pages_to_inspect,
            "sampling_strategy": self.sampling_strategy.value,
            "inspect_metadata": self.inspect_metadata,
            "inspect_security": self.inspect_security,
            "inspect_permissions": self.inspect_permissions,
            "inspect_resources": self.inspect_resources,
            "inspect_text": self.inspect_text,
            "inspect_images": self.inspect_images,
            "inspect_vectors": self.inspect_vectors,
            "inspect_links": self.inspect_links,
            "inspect_annotations": self.inspect_annotations,
            "inspect_forms": self.inspect_forms,
            "inspect_layers": self.inspect_layers,
            "timeout_seconds": self.timeout_seconds,
            "max_objects": self.max_objects,
            "max_resources": self.max_resources,
            "max_structure_depth": self.max_structure_depth,
            "max_memory_bytes": self.max_memory_bytes,
            "failure_policy": self.failure_policy.value,
            "preferred_provider": str(self.preferred_provider)
            if self.preferred_provider
            else None,
            "detail_level": self.detail_level,
            "include_raw_metadata": self.include_raw_metadata,
            "password_provided": self.password is not None,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.safe_options()


@dataclass(frozen=True, slots=True)
class PDFSourceIdentity(Serializable):
    source_type: str
    filename: str | None = None
    declared_media_type: str | None = None
    declared_extension: str | None = None
    size_bytes: int | None = None
    origin_reference: str | None = None
    content_hash: str | None = None
    content_hash_algorithm: str | None = None
    artifact_reference: ArtifactReference | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PDFInspectionEvidence(Serializable):
    code: str
    message: str
    scope: str
    page_index: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PDFIntegrityInspection(Serializable):
    status: PDFIntegrityStatus
    header: PDFInspectionState
    eof_marker: PDFInspectionState = PDFInspectionState.UNKNOWN
    trailer: PDFInspectionState = PDFInspectionState.UNKNOWN
    catalog: PDFInspectionState = PDFInspectionState.UNKNOWN
    page_tree: PDFInspectionState = PDFInspectionState.UNKNOWN
    xref: PDFInspectionState = PDFInspectionState.UNKNOWN
    repaired: PDFInspectionState = PDFInspectionState.UNKNOWN
    empty_document: PDFInspectionState = PDFInspectionState.UNKNOWN
    malformed: PDFInspectionState = PDFInspectionState.UNKNOWN
    confidence: float = 0.0
    evidences: tuple[PDFInspectionEvidence, ...] = ()

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class PDFVersionInspection(Serializable):
    declared_version: str | None
    catalog_version: str | None = None
    interpreted_version: str | None = None
    version_mismatch: PDFInspectionState = PDFInspectionState.UNKNOWN
    minimum_feature_version: str | None = None
    linearized: PDFInspectionState = PDFInspectionState.UNKNOWN
    incremental_updates: PDFInspectionState = PDFInspectionState.UNKNOWN
    object_streams: PDFInspectionState = PDFInspectionState.UNKNOWN
    xref_streams: PDFInspectionState = PDFInspectionState.UNKNOWN


@dataclass(frozen=True, slots=True)
class PDFMetadataValue(Serializable):
    normalized: str | None
    sources: tuple[str, ...] = ()
    conflict: bool = False
    confidence: float = 1.0
    warnings: tuple[EixoWarning, ...] = ()

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class PDFMetadataInspection(Serializable):
    status: PDFInspectionState
    fields: dict[str, PDFMetadataValue] = field(default_factory=dict)
    custom_fields: dict[str, PDFMetadataValue] = field(default_factory=dict)
    xmp_metadata: PDFInspectionState = PDFInspectionState.UNKNOWN
    info_dictionary: PDFInspectionState = PDFInspectionState.UNKNOWN
    metadata_conflicts: PDFInspectionState = PDFInspectionState.UNKNOWN
    invalid_dates: PDFInspectionState = PDFInspectionState.UNKNOWN
    malformed_metadata: PDFInspectionState = PDFInspectionState.UNKNOWN


@dataclass(frozen=True, slots=True)
class PDFSecurityInspection(Serializable):
    status: PDFSecurityStatus
    encryption_state: PDFEncryptionState
    password_provided: bool = False
    authenticated: PDFInspectionState = PDFInspectionState.UNKNOWN
    encryption_algorithm: str | None = None
    key_length_bits: int | None = None
    metadata_encrypted: PDFInspectionState = PDFInspectionState.UNKNOWN
    details_supported: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED


@dataclass(frozen=True, slots=True)
class PDFPermissionsInspection(Serializable):
    printing: PDFPermissionStatus = PDFPermissionStatus.UNSUPPORTED
    high_quality_printing: PDFPermissionStatus = PDFPermissionStatus.UNSUPPORTED
    copying: PDFPermissionStatus = PDFPermissionStatus.UNSUPPORTED
    content_extraction: PDFPermissionStatus = PDFPermissionStatus.UNSUPPORTED
    accessibility: PDFPermissionStatus = PDFPermissionStatus.UNSUPPORTED
    modification: PDFPermissionStatus = PDFPermissionStatus.UNSUPPORTED
    document_assembly: PDFPermissionStatus = PDFPermissionStatus.UNSUPPORTED
    annotations: PDFPermissionStatus = PDFPermissionStatus.UNSUPPORTED
    form_filling: PDFPermissionStatus = PDFPermissionStatus.UNSUPPORTED
    signing: PDFPermissionStatus = PDFPermissionStatus.UNSUPPORTED
    technical_capability: PDFInspectionState = PDFInspectionState.UNSUPPORTED


@dataclass(frozen=True, slots=True)
class PDFFeatureSignal(Serializable):
    status: PDFInspectionState
    approximate_count: int | None = None
    pages: tuple[int, ...] = ()
    confidence: float = 0.0
    evidence: tuple[PDFInspectionEvidence, ...] = ()

    def __post_init__(self) -> None:
        if self.approximate_count is not None and self.approximate_count < 0:
            raise ValueError("approximate_count cannot be negative")
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class PDFFeatureInventory(Serializable):
    native_text: PDFFeatureSignal
    images: PDFFeatureSignal
    image_masks: PDFFeatureSignal
    vectors: PDFFeatureSignal
    clipping: PDFFeatureSignal
    transparency: PDFFeatureSignal
    embedded_fonts: PDFFeatureSignal
    non_embedded_fonts: PDFFeatureSignal
    xobjects: PDFFeatureSignal
    form_xobjects: PDFFeatureSignal
    links: PDFFeatureSignal
    annotations: PDFFeatureSignal
    forms: PDFFeatureSignal
    signatures: PDFFeatureSignal
    layers: PDFFeatureSignal
    attachments: PDFFeatureSignal
    javascript: PDFFeatureSignal
    tagged_pdf: PDFFeatureSignal
    logical_structure: PDFFeatureSignal
    incremental_updates: PDFFeatureSignal


@dataclass(frozen=True, slots=True)
class PDFResourceSummary(Serializable):
    fonts: PDFFeatureSignal
    images: PDFFeatureSignal
    vectors: PDFFeatureSignal
    annotations: PDFFeatureSignal
    forms: PDFFeatureSignal
    layers: PDFFeatureSignal
    unsupported_resource_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PDFPageInspection(Serializable):
    page_index: int
    page_number: int
    width: float
    height: float
    rotation: int
    media_box: tuple[float, float, float, float] | None = None
    crop_box: tuple[float, float, float, float] | None = None
    canonical_geometry: PageGeometry | None = None
    unit: str = "pdf_point"
    inspection_status: PDFInspectionState = PDFInspectionState.PRESENT
    has_text: PDFInspectionState = PDFInspectionState.UNKNOWN
    has_images: PDFInspectionState = PDFInspectionState.UNKNOWN
    has_vectors: PDFInspectionState = PDFInspectionState.UNKNOWN
    has_links: PDFInspectionState = PDFInspectionState.UNKNOWN
    has_annotations: PDFInspectionState = PDFInspectionState.UNKNOWN
    has_forms: PDFInspectionState = PDFInspectionState.UNKNOWN
    has_layers: PDFInspectionState = PDFInspectionState.UNKNOWN
    approximate_resource_count: int | None = None
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        if self.page_index < 0:
            raise ValueError("page_index cannot be negative")
        if self.page_number <= 0:
            raise ValueError("page_number must be positive")
        if self.width < 0 or self.height < 0:
            raise ValueError("page dimensions cannot be negative")
        if self.approximate_resource_count is not None and self.approximate_resource_count < 0:
            raise ValueError("approximate_resource_count cannot be negative")


@dataclass(frozen=True, slots=True)
class PDFPageSummary(Serializable):
    total_pages: int
    inspected_pages: int
    not_inspected_pages: int
    pages_with_errors: int = 0
    pages_empty: int = 0
    pages_with_text: int = 0
    pages_with_images: int = 0
    pages_with_vectors: int = 0
    pages_with_annotations: int = 0
    pages_with_forms: int = 0
    pages_with_rotation: int = 0
    min_width: float | None = None
    max_width: float | None = None
    min_height: float | None = None
    max_height: float | None = None
    orientations: tuple[str, ...] = ()
    sampled_page_indexes: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.total_pages < 0 or self.inspected_pages < 0 or self.not_inspected_pages < 0:
            raise ValueError("page counts cannot be negative")
        if self.inspected_pages + self.not_inspected_pages != self.total_pages:
            raise ValueError("inspected and not inspected pages must match total_pages")


@dataclass(frozen=True, slots=True)
class PDFInspectionCoverage(Serializable):
    total_pages: int
    inspected_pages: int
    sampled_page_indexes: tuple[int, ...]
    inspection_complete: bool
    metadata_inspected: PDFInspectionState
    security_inspected: PDFInspectionState
    permissions_inspected: PDFInspectionState
    resources_inspected: PDFInspectionState
    features_inspected: PDFInspectionState
    coverage_ratio: float

    def __post_init__(self) -> None:
        if self.total_pages < 0 or self.inspected_pages < 0:
            raise ValueError("page counts cannot be negative")
        if self.inspected_pages > self.total_pages:
            raise ValueError("inspected_pages cannot exceed total_pages")
        if self.inspection_complete and self.inspected_pages < self.total_pages:
            raise ValueError("inspection_complete cannot be true for partial page coverage")
        _validate_confidence(self.coverage_ratio)


@dataclass(frozen=True, slots=True)
class PDFTechnicalProfileInspection(Serializable):
    profile: PDFTechnicalProfile
    confidence: float
    reasons: tuple[str, ...] = ()
    evidences: tuple[PDFInspectionEvidence, ...] = ()

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class PDFFidelityIndicators(Serializable):
    native_text_fidelity: PDFInspectionState = PDFInspectionState.UNKNOWN
    image_fidelity: PDFInspectionState = PDFInspectionState.UNKNOWN
    vector_fidelity: PDFInspectionState = PDFInspectionState.UNKNOWN
    metadata_fidelity: PDFInspectionState = PDFInspectionState.UNKNOWN
    geometry_fidelity: PDFInspectionState = PDFInspectionState.PARTIAL


@dataclass(frozen=True, slots=True)
class PDFEditabilityHints(Serializable):
    text_editability: PDFInspectionState = PDFInspectionState.UNKNOWN
    image_editability: PDFInspectionState = PDFInspectionState.UNKNOWN
    vector_editability: PDFInspectionState = PDFInspectionState.UNKNOWN
    font_availability: PDFInspectionState = PDFInspectionState.UNKNOWN
    reconstruction_required: PDFInspectionState = PDFInspectionState.UNKNOWN


@dataclass(frozen=True, slots=True)
class PDFInspectionTimings(Serializable):
    probe_seconds: float = 0.0
    open_seconds: float = 0.0
    page_inspection_seconds: float = 0.0
    total_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class PDFPageTechnicalHints(Serializable):
    has_text: PDFInspectionState = PDFInspectionState.UNKNOWN
    has_images: PDFInspectionState = PDFInspectionState.UNKNOWN
    has_vectors: PDFInspectionState = PDFInspectionState.UNKNOWN
    has_links: PDFInspectionState = PDFInspectionState.UNKNOWN
    has_annotations: PDFInspectionState = PDFInspectionState.UNKNOWN
    has_forms: PDFInspectionState = PDFInspectionState.UNKNOWN
    approximate_text_count: int | None = None
    approximate_image_count: int | None = None
    approximate_vector_count: int | None = None
    approximate_link_count: int | None = None
    approximate_annotation_count: int | None = None
    approximate_form_count: int | None = None


@dataclass(frozen=True, slots=True)
class PDFTechnicalInspection(Serializable):
    schema_version: ContractVersion
    document_identity: PDFSourceIdentity
    source: PDFSourceIdentity
    provider: PDFProviderDescriptor
    integrity: PDFIntegrityInspection
    version: PDFVersionInspection
    page_summary: PDFPageSummary
    metadata: PDFMetadataInspection
    security: PDFSecurityInspection
    permissions: PDFPermissionsInspection
    feature_inventory: PDFFeatureInventory
    resource_summary: PDFResourceSummary
    page_inspections: tuple[PDFPageInspection, ...]
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    coverage: PDFInspectionCoverage | None = None
    technical_profile: PDFTechnicalProfileInspection | None = None
    fidelity_indicators: PDFFidelityIndicators = field(default_factory=PDFFidelityIndicators)
    editability_hints: PDFEditabilityHints = field(default_factory=PDFEditabilityHints)
    processing_recommendations: tuple[str, ...] = ()
    evidences: tuple[PDFInspectionEvidence, ...] = ()
    provenance: PDFProviderProvenance | None = None
    timings: PDFInspectionTimings = field(default_factory=PDFInspectionTimings)


def unknown_signal() -> PDFFeatureSignal:
    return PDFFeatureSignal(status=PDFInspectionState.UNKNOWN, confidence=0.0)


def unsupported_signal() -> PDFFeatureSignal:
    return PDFFeatureSignal(status=PDFInspectionState.UNSUPPORTED, confidence=1.0)


def state_from_count(count: int | None, *, unsupported: bool = False) -> PDFInspectionState:
    if unsupported:
        return PDFInspectionState.UNSUPPORTED
    if count is None:
        return PDFInspectionState.UNKNOWN
    return PDFInspectionState.PRESENT if count > 0 else PDFInspectionState.ABSENT


def source_identity(source: DocumentSource) -> PDFSourceIdentity:
    content_hash = source.metadata.get("content_hash")
    return PDFSourceIdentity(
        source_type=source.source_type,
        filename=source.filename,
        declared_media_type=source.declared_media_type,
        declared_extension=source.declared_extension,
        size_bytes=source.size,
        origin_reference=source.origin_reference,
        content_hash=content_hash,
        content_hash_algorithm="sha256" if content_hash else None,
        metadata=dict(source.metadata),
    )


def _validate_confidence(value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise ValueError("confidence must be between 0 and 1")


__all__ = [
    "PDFEditabilityHints",
    "PDFFeatureInventory",
    "PDFFeatureSignal",
    "PDFFidelityIndicators",
    "PDFInspectionCoverage",
    "PDFInspectionEvidence",
    "PDFInspectionFailurePolicy",
    "PDFInspectionOptions",
    "PDFInspectionState",
    "PDFInspectionTimings",
    "PDFIntegrityInspection",
    "PDFIntegrityStatus",
    "PDFMetadataInspection",
    "PDFMetadataValue",
    "PDFPageInspection",
    "PDFPageSummary",
    "PDFPageTechnicalHints",
    "PDFPermissionStatus",
    "PDFPermissionsInspection",
    "PDFResourceSummary",
    "PDFSamplingStrategy",
    "PDFSecurityInspection",
    "PDFSecurityStatus",
    "PDFSourceIdentity",
    "PDFTechnicalInspection",
    "PDFTechnicalProfile",
    "PDFTechnicalProfileInspection",
    "PDFVersionInspection",
    "source_identity",
    "state_from_count",
    "unknown_signal",
    "unsupported_signal",
]
