from __future__ import annotations

from eixo.core.contracts import ErrorResult
from eixo.core.errors import EixoError


def error_to_response(error: EixoError) -> ErrorResult:
    payload = error.to_payload()
    return ErrorResult(
        code=payload.code,
        message=payload.message,
        category=payload.category,
        retryable=payload.retryable,
        details=payload.public_context,
    )

