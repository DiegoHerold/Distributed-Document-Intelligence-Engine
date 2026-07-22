from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from eixo.core import (
    CapabilityNotFoundError,
    ConfigurationError,
    ArchiveSecurityError,
    ArtifactCorruptedError,
    ArtifactError,
    ArtifactNotFoundError,
    ArtifactStorageError,
    CorrelationId,
    DocumentNotFoundError,
    DocumentRepositoryError,
    DocumentVersionConflictError,
    EixoError,
    EmptyFileError,
    ErrorCategory,
    ErrorResult,
    ExecutionCancelledError,
    ExecutionRejectedError,
    ExecutionTimeoutError,
    FileTooLargeError,
    IngestionSecurityError,
    InvalidMimeError,
    InvalidStateTransitionError,
    InvalidJobTransitionError,
    JobNotFoundError,
    JobAlreadyExistsError,
    JobConcurrencyError,
    JobPersistenceError,
    JobRecoveryError,
    JobResultUnavailableError,
    JobSerializationError,
    CorruptedFileError,
    PageLimitExceededError,
    PDFProviderUnavailableError,
    PathTraversalError,
    ReadTimeoutError,
    SourceNotFileError,
    SourceNotFoundError,
    SourceNotReadableError,
    SourceResolutionError,
    UnsupportedFormatError,
    UnsafeFilenameError,
    ValidationError,
)
from eixo.core.serialization import to_jsonable
from eixo_api.context import get_correlation_id
from eixo_api.upload import UploadTooLargeError

logger = logging.getLogger(__name__)

ERROR_STATUS: tuple[tuple[type[EixoError], int], ...] = (
    (UploadTooLargeError, 413),
    (FileTooLargeError, 413),
    (ReadTimeoutError, 408),
    (PathTraversalError, 400),
    (UnsafeFilenameError, 400),
    (InvalidMimeError, 415),
    (UnsupportedFormatError, 415),
    (ArchiveSecurityError, 422),
    (CorruptedFileError, 422),
    (PageLimitExceededError, 422),
    (EmptyFileError, 422),
    (IngestionSecurityError, 422),
    (ValidationError, 422),
    (SourceNotFoundError, 404),
    (SourceNotFileError, 422),
    (SourceNotReadableError, 422),
    (SourceResolutionError, 422),
    (ArtifactNotFoundError, 404),
    (ArtifactCorruptedError, 500),
    (ArtifactStorageError, 503),
    (ArtifactError, 500),
    (DocumentNotFoundError, 404),
    (DocumentVersionConflictError, 409),
    (DocumentRepositoryError, 500),
    (JobResultUnavailableError, 409),
    (CapabilityNotFoundError, 422),
    (PDFProviderUnavailableError, 503),
    (JobNotFoundError, 404),
    (JobAlreadyExistsError, 409),
    (InvalidJobTransitionError, 409),
    (JobConcurrencyError, 409),
    (JobPersistenceError, 503),
    (JobRecoveryError, 503),
    (JobSerializationError, 500),
    (InvalidStateTransitionError, 409),
    (ExecutionTimeoutError, 504),
    (ExecutionCancelledError, 409),
    (ExecutionRejectedError, 503),
    (ConfigurationError, 503),
)


def register_error_handlers(app: Any) -> None:
    app.add_exception_handler(EixoError, eixo_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)


async def eixo_error_handler(request: Request, exc: EixoError) -> JSONResponse:
    status_code = status_for_error(exc)
    logger.info(
        "http.domain_error",
        extra={
            "event": "http.domain_error",
            "path": request.url.path,
            "status_code": status_code,
            "error_code": exc.code,
            "correlation_id": str(get_correlation_id()),
        },
    )
    return error_response(exc, status_code=status_code)


async def request_validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    error = ErrorResult(
        code="request.invalid",
        message="Request contract is invalid.",
        category=ErrorCategory.VALIDATION,
        retryable=False,
        details={"errors": scrub_validation_errors(exc.errors())},
        correlation_id=get_correlation_id(),
    )
    return JSONResponse(content=to_jsonable(error), status_code=422)


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "http.request.unexpected_error",
        extra={
            "event": "http.request.unexpected_error",
            "path": request.url.path,
            "correlation_id": str(get_correlation_id()),
        },
    )
    error = ErrorResult(
        code="internal.error",
        message="Unexpected server error.",
        category=ErrorCategory.INTERNAL,
        retryable=True,
        correlation_id=get_correlation_id(),
    )
    return JSONResponse(content=to_jsonable(error), status_code=500)


def error_response(error: EixoError, *, status_code: int) -> JSONResponse:
    payload = error.to_payload()
    result = ErrorResult(
        code=payload.code,
        message=payload.message,
        category=payload.category,
        retryable=payload.retryable,
        details=payload.public_context,
        correlation_id=get_correlation_id(),
    )
    return JSONResponse(content=to_jsonable(result), status_code=status_code)


def status_for_error(error: EixoError) -> int:
    for error_type, status_code in ERROR_STATUS:
        if isinstance(error, error_type):
            return status_code
    return 500


def scrub_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in errors:
        cleaned.append(
            {
                "type": str(item.get("type", "validation")),
                "loc": [str(part) for part in item.get("loc", ())],
                "msg": str(item.get("msg", "Invalid value")),
            }
        )
    return cleaned


__all__ = [
    "ERROR_STATUS",
    "error_response",
    "register_error_handlers",
    "status_for_error",
]
