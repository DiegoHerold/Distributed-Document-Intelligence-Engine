from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from eixo.core.ids import ProviderId
from eixo.core.serialization import Serializable
from eixo.core.timestamps import isoformat_utc, utc_now
from eixo.core.versions import ProviderVersion
from eixo.core.warnings import EixoWarning
from eixo.geometry import PageGeometry


class PDFSupportLevel(StrEnum):
    UNSUPPORTED = "unsupported"
    PARTIAL = "partial"
    SUPPORTED = "supported"
    EXPERIMENTAL = "experimental"


class PDFEncryptionState(StrEnum):
    NOT_ENCRYPTED = "not_encrypted"
    ENCRYPTED_UNLOCKED = "encrypted_unlocked"
    PASSWORD_REQUIRED = "password_required"
    INVALID_PASSWORD = "invalid_password"
    UNSUPPORTED_ENCRYPTION = "unsupported_encryption"
    UNKNOWN = "unknown"


class PDFProbeStatus(StrEnum):
    NOT_PDF = "not_pdf"
    SIGNATURE_FOUND = "signature_found"
    VALID = "valid"
    PARTIALLY_CORRUPTED = "partially_corrupted"
    ENCRYPTED = "encrypted"
    UNSUPPORTED = "unsupported"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True, slots=True)
class ProviderLimitation(Serializable):
    code: str
    message: str
    scope: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PDFProviderCapabilities(Serializable):
    supports_encrypted_documents: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_password_authentication: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_incremental_page_access: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_basic_info: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_page_geometry: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_metadata_inspection: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_security_inspection: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_permission_inspection: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_resource_inspection: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_text_presence_inspection: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_image_presence_inspection: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_vector_presence_inspection: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_link_inspection: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_annotation_inspection: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_form_inspection: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_layer_inspection: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_text_extraction: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_glyph_extraction: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_word_extraction: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_native_blocks: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_image_extraction: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_image_occurrences: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_vector_extraction: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_clipping: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_annotations: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_forms: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_layers: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_content_streams: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_object_references: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_embedded_fonts: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED
    supports_rendering: PDFSupportLevel = PDFSupportLevel.UNSUPPORTED

    def support_for(self, name: str) -> PDFSupportLevel:
        if not hasattr(self, name):
            raise ValueError(f"Unknown PDF provider capability: {name}")
        value = getattr(self, name)
        if not isinstance(value, PDFSupportLevel):
            raise ValueError(f"Invalid PDF provider capability field: {name}")
        return value


@dataclass(frozen=True, slots=True)
class PDFProviderDescriptor(Serializable):
    provider_id: ProviderId
    name: str
    provider_version: ProviderVersion
    backend_name: str
    backend_version: str | None
    capabilities: PDFProviderCapabilities
    limitations: tuple[ProviderLimitation, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("provider name cannot be empty")
        if not self.backend_name.strip():
            raise ValueError("backend_name cannot be empty")


@dataclass(frozen=True, slots=True)
class PDFProbeOptions(Serializable):
    password: str | None = field(default=None, repr=False)
    max_file_size_bytes: int | None = None
    max_pages: int | None = None
    lazy: bool = True
    strict_validation: bool = True
    tolerate_partial_corruption: bool = False
    trusted_source: bool = False
    timeout_seconds: float | None = None
    provider_preferences: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_positive_optional("max_file_size_bytes", self.max_file_size_bytes)
        _validate_positive_optional("max_pages", self.max_pages)
        _validate_positive_optional("timeout_seconds", self.timeout_seconds)

    def safe_options(self) -> dict[str, Any]:
        return {
            "max_file_size_bytes": self.max_file_size_bytes,
            "max_pages": self.max_pages,
            "lazy": self.lazy,
            "strict_validation": self.strict_validation,
            "tolerate_partial_corruption": self.tolerate_partial_corruption,
            "trusted_source": self.trusted_source,
            "timeout_seconds": self.timeout_seconds,
            "provider_preferences": dict(self.provider_preferences),
            "password_provided": self.password is not None,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.safe_options()


@dataclass(frozen=True, slots=True)
class PDFOpenOptions(Serializable):
    password: str | None = field(default=None, repr=False)
    max_file_size_bytes: int | None = None
    max_pages: int | None = None
    lazy: bool = True
    strict_validation: bool = True
    tolerate_partial_corruption: bool = False
    trusted_source: bool = False
    timeout_seconds: float | None = None
    provider_preferences: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_positive_optional("max_file_size_bytes", self.max_file_size_bytes)
        _validate_positive_optional("max_pages", self.max_pages)
        _validate_positive_optional("timeout_seconds", self.timeout_seconds)

    def to_probe_options(self) -> PDFProbeOptions:
        return PDFProbeOptions(
            password=self.password,
            max_file_size_bytes=self.max_file_size_bytes,
            max_pages=self.max_pages,
            lazy=self.lazy,
            strict_validation=self.strict_validation,
            tolerate_partial_corruption=self.tolerate_partial_corruption,
            trusted_source=self.trusted_source,
            timeout_seconds=self.timeout_seconds,
            provider_preferences=dict(self.provider_preferences),
        )

    def safe_options(self) -> dict[str, Any]:
        return self.to_probe_options().safe_options()

    def to_dict(self) -> dict[str, Any]:
        return self.safe_options()


@dataclass(frozen=True, slots=True)
class PDFProviderSettings(Serializable):
    default_provider: ProviderId | None = None
    strict_validation: bool = True
    max_file_size_bytes: int | None = None
    max_pages: int | None = None
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        _validate_positive_optional("max_file_size_bytes", self.max_file_size_bytes)
        _validate_positive_optional("max_pages", self.max_pages)
        _validate_positive_optional("timeout_seconds", self.timeout_seconds)

    def open_options(self) -> PDFOpenOptions:
        return PDFOpenOptions(
            max_file_size_bytes=self.max_file_size_bytes,
            max_pages=self.max_pages,
            strict_validation=self.strict_validation,
            timeout_seconds=self.timeout_seconds,
        )


@dataclass(frozen=True, slots=True)
class PDFProviderProvenance(Serializable):
    provider_id: ProviderId
    provider_version: ProviderVersion
    backend_name: str
    backend_version: str | None
    operation: str
    source_reference: str | None = None
    source_hash: str | None = None
    page_index: int | None = None
    options: dict[str, Any] = field(default_factory=dict)
    observed_at: str = field(default_factory=lambda: isoformat_utc(utc_now()))
    execution_id: str | None = None
    job_id: str | None = None


@dataclass(frozen=True, slots=True)
class PDFProbeResult(Serializable):
    supported: bool
    status: PDFProbeStatus
    confidence: float
    detected_media_type: str | None
    detected_version: str | None
    encryption_state: PDFEncryptionState
    requires_password: bool | None
    provider_id: ProviderId
    provider_version: ProviderVersion
    backend_name: str
    backend_version: str | None
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class PDFBasicInfo(Serializable):
    page_count: int
    declared_version: str | None
    interpreted_version: str | None
    encryption_state: PDFEncryptionState
    requires_password: bool
    metadata: dict[str, str] = field(default_factory=dict)
    size_bytes: int | None = None
    provider_id: ProviderId | None = None
    provider_version: ProviderVersion | None = None
    backend_name: str | None = None
    backend_version: str | None = None
    warnings: tuple[EixoWarning, ...] = ()
    limitations: tuple[ProviderLimitation, ...] = ()
    integrity_status: PDFProbeStatus = PDFProbeStatus.VALID
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        if self.page_count < 0:
            raise ValueError("page_count cannot be negative")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("size_bytes cannot be negative")


@dataclass(frozen=True, slots=True)
class PDFPageGeometry(Serializable):
    page_index: int
    page_number: int
    width: float
    height: float
    rotation: int
    media_box: tuple[float, float, float, float] | None = None
    crop_box: tuple[float, float, float, float] | None = None
    canonical_geometry: PageGeometry | None = None
    provenance: PDFProviderProvenance | None = None

    def __post_init__(self) -> None:
        if self.page_index < 0:
            raise ValueError("page_index cannot be negative")
        if self.page_number <= 0:
            raise ValueError("page_number must be positive")
        if self.width < 0 or self.height < 0:
            raise ValueError("page dimensions cannot be negative")


def _validate_positive_optional(name: str, value: int | float | None) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{name} must be positive")


__all__ = [
    "PDFBasicInfo",
    "PDFEncryptionState",
    "PDFOpenOptions",
    "PDFPageGeometry",
    "PDFProbeOptions",
    "PDFProbeResult",
    "PDFProbeStatus",
    "PDFProviderCapabilities",
    "PDFProviderDescriptor",
    "PDFProviderProvenance",
    "PDFProviderSettings",
    "PDFSupportLevel",
    "ProviderLimitation",
]
