from __future__ import annotations

from argparse import Namespace

from eixo import DocumentEngine
from eixo_cli.output import OutputOptions, render_or_write


async def run_jobs_status(args: Namespace, engine: DocumentEngine, stdout) -> None:
    result = await engine.get_job_status(args.job_id)
    render_or_write(result, OutputOptions.from_args(args), stdout)  # type: ignore[attr-defined]


async def run_jobs_result(args: Namespace, engine: DocumentEngine, stdout) -> None:
    result = await engine.get_job_result(args.job_id)
    render_or_write(result, OutputOptions.from_args(args), stdout)  # type: ignore[attr-defined]


async def run_jobs_cancel(args: Namespace, engine: DocumentEngine, stdout) -> None:
    result = await engine.cancel_job(args.job_id)
    render_or_write(result, OutputOptions.from_args(args), stdout)  # type: ignore[attr-defined]
