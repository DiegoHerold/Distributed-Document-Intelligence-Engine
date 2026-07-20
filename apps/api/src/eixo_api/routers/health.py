from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from eixo.core.serialization import to_jsonable
from eixo_api.dependencies import get_api_state

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    summary="Process health",
    responses={200: {"description": "The HTTP process is alive."}},
)
async def health(request: Request) -> dict[str, str]:
    state = get_api_state(request)
    return {
        "status": "ok",
        "service": "eixo-api",
        "version": state.config.version,
    }


@router.get(
    "/ready",
    summary="Application readiness",
    responses={
        200: {"description": "The API is ready for document operations."},
        503: {"description": "The API is not ready."},
    },
)
async def ready(request: Request) -> JSONResponse:
    state = get_api_state(request)
    checks = state.readiness_checks()
    status = "ready" if state.is_ready() else "not_ready"
    payload = {
        "status": status,
        "checks": checks,
        "capabilities": {
            "registered": (
                len(state.engine.registry.list_capabilities())
                if state.engine is not None
                else 0
            )
        },
    }
    return JSONResponse(
        content=to_jsonable(payload),
        status_code=200 if status == "ready" else 503,
    )
