from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request

from eixo.core import CorrelationId, InspectionRequest, ParseRequest
from eixo.engine import DocumentEngine
from eixo_api.dependencies import get_engine
from eixo_api.responses import json_response
from eixo_api.upload import HttpDocumentSourceAdapter, read_multipart_document

router = APIRouter(prefix="/v1", tags=["Documents"])


@router.post(
    "/documents:inspect",
    summary="Inspect an uploaded document",
    responses={
        200: {"description": "Inspection result."},
        413: {"description": "Upload exceeds max_upload_size."},
        422: {"description": "Invalid request or missing capability."},
    },
)
async def inspect_document(
    request: Request,
    engine: DocumentEngine = Depends(get_engine),
):
    config = request.app.state.eixo.config
    upload = await read_multipart_document(request, config)
    adapter = HttpDocumentSourceAdapter(config)
    source = await adapter.to_source(upload.file)
    result = await engine.inspect(
        InspectionRequest(
            source=source,
            options=parse_options(upload.fields.get("options")),
            correlation_id=resolve_correlation_id(
                request,
                upload.fields.get("correlation_id"),
            ),
        )
    )
    return json_response(result)


@router.post(
    "/documents:parse",
    summary="Parse an uploaded document",
    responses={
        200: {"description": "Parse result."},
        413: {"description": "Upload exceeds max_upload_size."},
        415: {"description": "Unsupported or invalid declared media type."},
        422: {"description": "Invalid request or missing capability."},
    },
)
async def parse_document(
    request: Request,
    engine: DocumentEngine = Depends(get_engine),
):
    config = request.app.state.eixo.config
    upload = await read_multipart_document(request, config)
    adapter = HttpDocumentSourceAdapter(config)
    source = await adapter.to_source(upload.file)
    result = await engine.parse(
        ParseRequest(
            source=source,
            profile=upload.fields.get("profile"),
            page_selection=parse_page_selection(
                upload.fields.get("page_selection") or upload.fields.get("pages")
            ),
            options=parse_options(upload.fields.get("options")),
            requested_capability=upload.fields.get("requested_capability"),
            correlation_id=resolve_correlation_id(
                request,
                upload.fields.get("correlation_id"),
            ),
        )
    )
    return json_response(result)


def parse_options(value: str | None) -> dict[str, Any]:
    if value is None or not value.strip():
        return {}
    from eixo.core import ValidationError

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValidationError("options must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValidationError("options must be a JSON object")
    return parsed


def parse_page_selection(value: str | None) -> tuple[int, ...] | None:
    if value is None or not value.strip():
        return None
    stripped = value.strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            parsed = parsed.get("pages")
        if not isinstance(parsed, list):
            from eixo.core import ValidationError

            raise ValidationError("page_selection JSON must be an array or object with pages")
        return tuple(int(item) for item in parsed)
    pages: list[int] = []
    for part in stripped.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                from eixo.core import ValidationError

                raise ValidationError("page range end must be greater than or equal to start")
            pages.extend(range(start, end + 1))
            continue
        pages.append(int(token))
    return tuple(dict.fromkeys(pages)) or None


def resolve_correlation_id(request: Request, value: str | None) -> CorrelationId:
    if value is not None and value.strip():
        return parse_correlation_id(value)
    raw = request.headers.get("X-Correlation-ID")
    if raw is not None:
        try:
            return CorrelationId.parse(raw)
        except ValueError:
            pass
    return CorrelationId.new()


def parse_correlation_id(value: str) -> CorrelationId:
    from eixo.core import ValidationError

    try:
        return CorrelationId.parse(value)
    except ValueError as exc:
        raise ValidationError("correlation_id must start with 'corr_'") from exc


__all__ = [
    "parse_correlation_id",
    "parse_options",
    "parse_page_selection",
    "resolve_correlation_id",
    "router",
]
