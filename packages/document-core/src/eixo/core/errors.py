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


class UnsupportedFormatError(EixoError):
    code = "format.unsupported"
    category = ErrorCategory.UNSUPPORTED_FORMAT


class JobNotFoundError(EixoError):
    code = "job.not_found"
    category = ErrorCategory.NOT_FOUND


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
