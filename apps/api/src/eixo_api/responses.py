from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from eixo.core.serialization import to_jsonable


def json_response(
    value: Any,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        content=to_jsonable(value),
        status_code=status_code,
        headers=headers,
    )


__all__ = ["json_response"]
