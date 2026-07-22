from __future__ import annotations

from argparse import Namespace

from eixo import DocumentEngine, ParseRequest
from eixo_cli.output import OutputOptions, render_or_write
from eixo_cli.sources import local_path_source


async def run_parse(args: Namespace, engine: DocumentEngine, stdout) -> None:
    source = local_path_source(args.source)
    result = await engine.parse(
        ParseRequest(
            source=source,
            profile=args.profile.replace("-", "_"),
            page_selection=parse_pages(args.pages),
        )
    )
    render_or_write(result, OutputOptions.from_args(args), stdout)  # type: ignore[attr-defined]


def parse_pages(value: str | None) -> tuple[int, ...] | None:
    if value is None or not value.strip():
        return None
    pages: list[int] = []
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                raise ValueError("page range end must be greater than or equal to start")
            pages.extend(range(start, end + 1))
            continue
        pages.append(int(token))
    return tuple(dict.fromkeys(pages)) or None
