from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from eixo.core.enums import ErrorCategory


@dataclass(frozen=True, slots=True)
class ErrorPayload:
    code: str
    message: str
    category: ErrorCategory
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    public_context: dict[str, Any] = field(default_factory=dict)


class EixoError(Exception):
    code = "eixo.error"
    category = ErrorCategory.INTERNAL
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
        public_context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause
        self.public_context = public_context or {}

    def to_payload(self) -> ErrorPayload:
        return ErrorPayload(
            code=self.code,
            message=self.message,
            category=self.category,
            retryable=self.retryable,
            details=self.details,
            public_context=self.public_context,
        )


class ValidationError(EixoError):
    code = "validation.error"
    category = ErrorCategory.VALIDATION


class SourceResolutionError(EixoError):
    code = "source.resolution_failed"
    category = ErrorCategory.VALIDATION


class SourceNotFoundError(SourceResolutionError):
    code = "source.not_found"
    category = ErrorCategory.NOT_FOUND


class SourceNotFileError(SourceResolutionError):
    code = "source.not_file"


class SourceNotReadableError(SourceResolutionError):
    code = "source.not_readable"


class ArtifactError(EixoError):
    code = "artifact.error"
    category = ErrorCategory.EXECUTION


class ArtifactNotFoundError(ArtifactError):
    code = "artifact.not_found"
    category = ErrorCategory.NOT_FOUND


class ArtifactMetadataMissingError(ArtifactError):
    code = "artifact.metadata_missing"


class ArtifactCorruptedError(ArtifactError):
    code = "artifact.corrupted"


class ArtifactHashMismatchError(ArtifactCorruptedError):
    code = "artifact.hash_mismatch"


class ArtifactSizeMismatchError(ArtifactCorruptedError):
    code = "artifact.size_mismatch"


class ArtifactStorageError(ArtifactError):
    code = "artifact.storage_failure"
    retryable = True


class DocumentRepositoryError(EixoError):
    code = "document.repository_error"
    category = ErrorCategory.EXECUTION


class DocumentNotFoundError(DocumentRepositoryError):
    code = "document.not_found"
    category = ErrorCategory.NOT_FOUND


class DocumentVersionConflictError(DocumentRepositoryError):
    code = "document.version_conflict"


class ConfigurationError(EixoError):
    code = "configuration.error"
    category = ErrorCategory.CONFIGURATION


class CapabilityError(EixoError):
    code = "capability.error"
    category = ErrorCategory.CAPABILITY


class CapabilityNotFoundError(CapabilityError):
    code = "capability.not_found"


class CapabilityAlreadyRegisteredError(CapabilityError):
    code = "capability.already_registered"


class IncompatibleCapabilityError(CapabilityError):
    code = "capability.incompatible"


class IngestionSecurityError(EixoError):
    code = "ingestion_security_error"
    category = ErrorCategory.VALIDATION


class FileTooLargeError(IngestionSecurityError):
    code = "file_too_large"


class EmptyFileError(IngestionSecurityError):
    code = "empty_file"


class UnsupportedFormatError(IngestionSecurityError):
    code = "unsupported_format"
    category = ErrorCategory.UNSUPPORTED_FORMAT


class InvalidMimeError(IngestionSecurityError):
    code = "invalid_mime"


class MimeMismatchError(InvalidMimeError):
    code = "mime_mismatch"


class CorruptedFileError(IngestionSecurityError):
    code = "corrupted_file"


class TruncatedFileError(CorruptedFileError):
    code = "truncated_file"


class InvalidContainerError(CorruptedFileError):
    code = "invalid_container"


class InvalidDocumentStructureError(CorruptedFileError):
    code = "invalid_document_structure"


class UnsafeFilenameError(IngestionSecurityError):
    code = "unsafe_filename"


class PathTraversalError(IngestionSecurityError):
    code = "path_traversal_detected"


class UnsafeStorageKeyError(PathTraversalError):
    code = "unsafe_storage_key"


class ArchiveSecurityError(IngestionSecurityError):
    code = "archive_security_error"


class ArchiveTooManyEntriesError(ArchiveSecurityError):
    code = "archive_too_many_entries"


class ArchiveUncompressedSizeExceededError(ArchiveSecurityError):
    code = "archive_uncompressed_size_exceeded"


class ArchiveEntryTooLargeError(ArchiveSecurityError):
    code = "archive_entry_too_large"


class SuspiciousCompressionRatioError(ArchiveSecurityError):
    code = "suspicious_compression_ratio"


class ZipBombError(ArchiveSecurityError):
    code = "zip_bomb_detected"


class EncryptedArchiveNotAllowedError(ArchiveSecurityError):
    code = "encrypted_archive_not_allowed"


class UnsafeArchiveEntryError(ArchiveSecurityError):
    code = "unsafe_archive_entry"


class PageLimitExceededError(IngestionSecurityError):
    code = "page_limit_exceeded"


class ReadTimeoutError(IngestionSecurityError):
    code = "read_timeout"
    category = ErrorCategory.TIMEOUT
    retryable = True


class PDFProviderError(EixoError):
    code = "pdf.provider_error"
    category = ErrorCategory.EXECUTION


class PDFProviderUnavailableError(PDFProviderError):
    code = "pdf.provider_unavailable"
    category = ErrorCategory.CONFIGURATION


class UnsupportedPDFError(PDFProviderError):
    code = "pdf.unsupported"
    category = ErrorCategory.UNSUPPORTED_FORMAT


class InvalidPDFError(PDFProviderError):
    code = "pdf.invalid"
    category = ErrorCategory.VALIDATION


class CorruptedPDFError(InvalidPDFError):
    code = "pdf.corrupted"


class EncryptedPDFError(PDFProviderError):
    code = "pdf.encrypted"
    category = ErrorCategory.VALIDATION


class PDFPasswordRequiredError(EncryptedPDFError):
    code = "pdf.password_required"


class InvalidPDFPasswordError(EncryptedPDFError):
    code = "pdf.invalid_password"


class PDFPageOutOfRangeError(PDFProviderError):
    code = "pdf.page_out_of_range"
    category = ErrorCategory.VALIDATION


class PDFResourceLimitExceededError(PDFProviderError):
    code = "pdf.resource_limit_exceeded"
    category = ErrorCategory.VALIDATION


class PDFProviderExecutionError(PDFProviderError):
    code = "pdf.provider_execution_error"
    retryable = True


class ClosedPDFDocumentError(PDFProviderError):
    code = "pdf.document_closed"
    category = ErrorCategory.STATE


class JobNotFoundError(EixoError):
    code = "job.not_found"
    category = ErrorCategory.NOT_FOUND


class JobAlreadyExistsError(EixoError):
    code = "job.already_exists"
    category = ErrorCategory.STATE


class InvalidJobTransitionError(EixoError):
    code = "job.invalid_transition"
    category = ErrorCategory.STATE


class JobConcurrencyError(EixoError):
    code = "job.concurrency_conflict"
    category = ErrorCategory.STATE


class JobPersistenceError(EixoError):
    code = "job.persistence_error"
    category = ErrorCategory.EXECUTION
    retryable = True


class JobSerializationError(EixoError):
    code = "job.serialization_error"
    category = ErrorCategory.EXECUTION


class JobResultUnavailableError(EixoError):
    code = "job.result_unavailable"
    category = ErrorCategory.STATE


class JobRecoveryError(EixoError):
    code = "job.recovery_error"
    category = ErrorCategory.EXECUTION
    retryable = True


class InvalidStateTransitionError(EixoError):
    code = "state.invalid_transition"
    category = ErrorCategory.STATE


class InternalProcessingError(EixoError):
    code = "processing.internal"
    category = ErrorCategory.INTERNAL
    retryable = True


class ExecutionError(EixoError):
    code = "execution.error"
    category = ErrorCategory.EXECUTION


class ExecutionTimeoutError(ExecutionError):
    code = "execution.timeout"
    category = ErrorCategory.TIMEOUT
    retryable = True


class ExecutionCancelledError(ExecutionError):
    code = "execution.cancelled"
    category = ErrorCategory.CANCELLATION


class ExecutionRejectedError(ExecutionError):
    code = "execution.rejected"
    category = ErrorCategory.EXECUTION
    retryable = True


class ExecutionSerializationError(ExecutionError):
    code = "execution.serialization"
    category = ErrorCategory.EXECUTION


class RuntimeShutdownError(ExecutionError):
    code = "runtime.shutdown"
    category = ErrorCategory.STATE
