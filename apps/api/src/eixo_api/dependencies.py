from __future__ import annotations

from fastapi import Request

from eixo.engine import DocumentEngine
from eixo.engine.lifecycle import EngineState
from eixo_api.lifecycle import ApiState


def get_api_state(request: Request) -> ApiState:
    return request.app.state.eixo


def get_engine(request: Request) -> DocumentEngine:
    state = get_api_state(request)
    engine = state.engine
    if engine is None or engine.state != EngineState.RUNNING or state.shutting_down:
        from eixo.core import InvalidStateTransitionError

        raise InvalidStateTransitionError("DocumentEngine is not ready")
    return engine


__all__ = ["get_api_state", "get_engine"]
