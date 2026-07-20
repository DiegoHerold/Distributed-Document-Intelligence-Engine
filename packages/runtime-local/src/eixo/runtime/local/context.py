from __future__ import annotations

from contextvars import ContextVar

from eixo.plugins import RuntimeExecutionContext

current_execution_context: ContextVar[RuntimeExecutionContext | None] = ContextVar(
    "current_execution_context",
    default=None,
)

