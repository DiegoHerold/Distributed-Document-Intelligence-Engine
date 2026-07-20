from __future__ import annotations

from contextvars import ContextVar

from eixo.core import CorrelationId

current_correlation_id: ContextVar[CorrelationId | None] = ContextVar(
    "eixo_api_correlation_id",
    default=None,
)


def get_correlation_id() -> CorrelationId:
    value = current_correlation_id.get()
    if value is None:
        return CorrelationId.new()
    return value


__all__ = ["current_correlation_id", "get_correlation_id"]
