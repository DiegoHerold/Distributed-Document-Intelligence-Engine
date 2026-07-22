from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from eixo.core import ProcessingRequest
from eixo.engine import DocumentEngine
from eixo_api.dependencies import get_engine
from eixo_api.responses import json_response
from eixo_api.routers.documents import (
    parse_options,
    parse_page_selection,
    resolve_correlation_id,
)
from eixo_api.upload import HttpDocumentSourceAdapter, read_multipart_document

router = APIRouter(prefix="/v1/extractions", tags=["Extractions"])


@router.post(
    "",
    status_code=202,
    summary="Submit an asynchronous extraction job",
    responses={202: {"description": "Job accepted."}},
)
async def submit_extraction(
    request: Request,
    engine: DocumentEngine = Depends(get_engine),
):
    config = request.app.state.eixo.config
    upload = await read_multipart_document(request, config)
    adapter = HttpDocumentSourceAdapter(config)
    source = await adapter.to_source(upload.file)
    job = await engine.submit(
        ProcessingRequest(
            source=source,
            profile=upload.fields.get("profile", "balanced"),
            schema_reference=upload.fields.get("schema_id"),
            template_reference=upload.fields.get("template_id"),
            options=_options_with_pages(
                parse_options(upload.fields.get("options")),
                parse_page_selection(
                    upload.fields.get("page_selection") or upload.fields.get("pages")
                ),
            ),
            correlation_id=resolve_correlation_id(
                request,
                upload.fields.get("correlation_id"),
            ),
        )
    )
    location = f"/v1/extractions/{job.job_id}"
    return json_response(job, status_code=202, headers={"Location": location})


@router.get(
    "/{job_id}",
    summary="Get extraction job status",
    responses={200: {"description": "Job status."}, 404: {"description": "Job not found."}},
)
async def get_extraction_status(
    job_id: str,
    engine: DocumentEngine = Depends(get_engine),
):
    return json_response(await engine.get_job_status(job_id))


@router.get(
    "/{job_id}/result",
    summary="Get extraction job result",
    responses={
        200: {"description": "Completed processing result."},
        409: {"description": "The result is not available yet."},
        404: {"description": "Job not found."},
    },
)
async def get_extraction_result(
    job_id: str,
    engine: DocumentEngine = Depends(get_engine),
):
    return json_response(await engine.get_job_result(job_id))


@router.post(
    "/{job_id}/cancel",
    summary="Cancel extraction job",
    responses={
        202: {"description": "Cancellation accepted."},
        404: {"description": "Job not found."},
        409: {"description": "Invalid job state."},
    },
)
async def cancel_extraction(
    job_id: str,
    engine: DocumentEngine = Depends(get_engine),
):
    return json_response(await engine.cancel_job(job_id), status_code=202)


__all__ = ["router"]


def _options_with_pages(
    options: dict[str, object],
    pages: tuple[int, ...] | None,
) -> dict[str, object]:
    if pages is None:
        return options
    merged = dict(options)
    merged["page_selection"] = {"pages": list(pages)}
    return merged
