from __future__ import annotations

from argparse import Namespace

from eixo import DocumentEngine, ProcessingRequest
from eixo_cli.output import OutputOptions, render_or_write
from eixo_cli.sources import local_path_source


async def run_process(args: Namespace, engine: DocumentEngine, stdout) -> None:
    source = local_path_source(args.source)
    request = ProcessingRequest(source=source, profile=args.profile)
    if args.wait:
        result = await engine.process(request)
    else:
        result = await engine.submit(request)
    render_or_write(result, OutputOptions.from_args(args), stdout)  # type: ignore[attr-defined]
