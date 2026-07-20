from __future__ import annotations

import traceback
from typing import Protocol

from eixo import (
    CapabilityNotFoundError,
    ConfigurationError,
    EixoError,
    ExecutionCancelledError,
    ExecutionTimeoutError,
    InvalidStateTransitionError,
    JobNotFoundError,
    SourceNotFileError,
    SourceNotFoundError,
    SourceNotReadableError,
    UnsupportedFormatError,
    ValidationError,
)
from eixo.core import ErrorCategory, ErrorResult
from eixo.core.serialization import to_jsonable
from eixo_cli.exit_codes import ExitCode


class Writer(Protocol):
    def write(self, value: str) -> object:
        ...


def exit_code_for_error(error: BaseException) -> ExitCode:
    if isinstance(error, FileExistsError):
        return ExitCode.INVALID_ARGUMENTS
    if isinstance(error, FileNotFoundError):
        return ExitCode.SOURCE_NOT_FOUND
    if isinstance(error, SourceNotFoundError):
        return ExitCode.SOURCE_NOT_FOUND
    if isinstance(error, IsADirectoryError):
        return ExitCode.INVALID_ARGUMENTS
    if isinstance(error, (SourceNotFileError, SourceNotReadableError)):
        return ExitCode.INVALID_ARGUMENTS
    if isinstance(error, UnsupportedFormatError):
        return ExitCode.UNSUPPORTED_FORMAT
    if isinstance(error, CapabilityNotFoundError):
        return ExitCode.CAPABILITY_UNAVAILABLE
    if isinstance(error, JobNotFoundError):
        return ExitCode.JOB_NOT_FOUND
    if isinstance(error, ExecutionTimeoutError):
        return ExitCode.TIMEOUT
    if isinstance(error, ExecutionCancelledError):
        return ExitCode.PROCESSING_CANCELLED
    if isinstance(error, ConfigurationError):
        return ExitCode.CONFIGURATION_ERROR
    if isinstance(error, ValidationError):
        return ExitCode.VALIDATION_ERROR
    if isinstance(error, InvalidStateTransitionError):
        return ExitCode.PROCESSING_FAILED
    if isinstance(error, EixoError):
        return ExitCode.PROCESSING_FAILED
    return ExitCode.GENERAL_ERROR


def user_message_for_error(error: BaseException) -> str:
    if isinstance(error, FileNotFoundError):
        return f'Erro: nao foi possivel localizar o arquivo "{error.args[0]}".'
    if isinstance(error, SourceNotFoundError):
        return "Erro: nao foi possivel localizar a origem do documento."
    if isinstance(error, IsADirectoryError):
        return f'Erro: o caminho "{error.args[0]}" nao e um arquivo.'
    if isinstance(error, SourceNotFileError):
        return "Erro: a origem do documento nao e um arquivo."
    if isinstance(error, SourceNotReadableError):
        return "Erro: a origem do documento nao pode ser lida."
    if isinstance(error, CapabilityNotFoundError):
        return "Erro: capability necessaria nao encontrada."
    if isinstance(error, JobNotFoundError):
        return "Erro: job nao encontrado."
    if isinstance(error, UnsupportedFormatError):
        return "Erro: formato nao suportado."
    if isinstance(error, ExecutionTimeoutError):
        return "Erro: tempo de execucao excedido."
    if isinstance(error, ExecutionCancelledError):
        return "Erro: processamento cancelado."
    if isinstance(error, ConfigurationError):
        return "Erro: configuracao invalida."
    if isinstance(error, ValidationError):
        return f"Erro: {error.message}"
    if isinstance(error, InvalidStateTransitionError):
        return f"Erro: {error.message}"
    if isinstance(error, EixoError):
        return f"Erro: {error.message}"
    if isinstance(error, FileExistsError):
        return f'Erro: o arquivo "{error.args[0]}" ja existe. Use --force.'
    return "Erro: falha inesperada."


def report_error(error: BaseException, stderr: Writer, *, debug: bool = False) -> None:
    stderr.write(user_message_for_error(error) + "\n")
    if debug:
        stderr.write("Detalhes tecnicos:\n")
        stderr.write("".join(traceback.format_exception(error)))


def error_result_for_exception(error: BaseException) -> ErrorResult:
    if isinstance(error, EixoError):
        payload = error.to_payload()
        return ErrorResult(
            code=payload.code,
            message=payload.message,
            category=payload.category,
            retryable=payload.retryable,
            details=payload.public_context,
        )
    if isinstance(error, FileNotFoundError):
        return ErrorResult(
            code="source.not_found",
            message=user_message_for_error(error),
            category=ErrorCategory.NOT_FOUND,
        )
    if isinstance(error, FileExistsError):
        return ErrorResult(
            code="output.exists",
            message=user_message_for_error(error),
            category=ErrorCategory.VALIDATION,
        )
    if isinstance(error, IsADirectoryError):
        return ErrorResult(
            code="source.invalid",
            message=user_message_for_error(error),
            category=ErrorCategory.VALIDATION,
        )
    return ErrorResult(
        code="cli.error",
        message=user_message_for_error(error),
        category=ErrorCategory.INTERNAL,
        retryable=True,
    )


def report_json_error(error: BaseException, stderr: Writer) -> None:
    import json

    stderr.write(json.dumps(to_jsonable(error_result_for_exception(error))) + "\n")


__all__ = [
    "error_result_for_exception",
    "exit_code_for_error",
    "report_error",
    "report_json_error",
    "user_message_for_error",
]
