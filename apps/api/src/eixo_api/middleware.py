from __future__ import annotations

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from eixo.core import CorrelationId
from eixo_api.context import current_correlation_id

logger = logging.getLogger(__name__)

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        raw = request.headers.get(CORRELATION_HEADER)
        correlation_id = _parse_or_new_correlation_id(raw)
        token = current_correlation_id.set(correlation_id)
        started = time.perf_counter()
        logger.info(
            "http.request.started",
            extra={
                "event": "http.request.started",
                "method": request.method,
                "path": request.url.path,
                "correlation_id": str(correlation_id),
            },
        )
        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - started
            logger.info(
                "http.request.failed",
                extra={
                    "event": "http.request.failed",
                    "method": request.method,
                    "path": request.url.path,
                    "duration": duration,
                    "correlation_id": str(correlation_id),
                },
            )
            raise
        finally:
            current_correlation_id.reset(token)
        response.headers[CORRELATION_HEADER] = str(correlation_id)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        duration = time.perf_counter() - started
        logger.info(
            "http.request.completed",
            extra={
                "event": "http.request.completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": duration,
                "correlation_id": str(correlation_id),
            },
        )
        return response


def _parse_or_new_correlation_id(raw: str | None) -> CorrelationId:
    if raw is None:
        return CorrelationId.new()
    try:
        return CorrelationId.parse(raw)
    except ValueError:
        return CorrelationId.new()


__all__ = ["CORRELATION_HEADER", "CorrelationIdMiddleware"]
