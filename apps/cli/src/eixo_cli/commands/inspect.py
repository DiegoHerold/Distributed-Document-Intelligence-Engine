from __future__ import annotations

from argparse import Namespace

from eixo import DocumentEngine, InspectionRequest
from eixo_cli.output import OutputOptions, render_or_write
from eixo_cli.sources import local_path_source


async def run_inspect(args: Namespace, engine: DocumentEngine, stdout) -> None:
    source = local_path_source(args.source)
    result = await engine.inspect(InspectionRequest(source=source))
    render_or_write(result, OutputOptions.from_args(args), stdout)  # type: ignore[attr-defined]
