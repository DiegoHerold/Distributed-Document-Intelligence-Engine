from __future__ import annotations

import argparse
import json
from typing import TextIO

from eixo.diagnostics.pdf_validation_lab import validate_pdf_batch

from eixo_cli.commands.parse import parse_pages


async def run_pdf_validate(
    args: argparse.Namespace,
    engine: object,
    stdout: TextIO,
) -> None:
    page_selection = parse_pages(args.pages)
    if hasattr(engine, "validate_pdf_batch"):
        result = await engine.validate_pdf_batch(  # type: ignore[attr-defined]
            args.source,
            output_directory=args.output,
            profile=args.profile.replace("-", "_"),
            pages=page_selection,
            password=args.password,
            diagnostic_preview=args.diagnostic_preview,
        )
    else:
        result = await validate_pdf_batch(
            engine,  # type: ignore[arg-type]
            args.source,
            output_directory=args.output,
            profile=args.profile.replace("-", "_"),
            page_selection=page_selection,
            password=args.password,
            diagnostic_preview=args.diagnostic_preview,
        )
    payload = result.to_dict()
    if args.format == "json":
        stdout.write(
            json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True) + "\n"
        )
        return
    stdout.write(f"PDF validation batch: {payload['document_count']} document(s)\n")
    stdout.write(f"Completed: {payload['documents_completed']}\n")
    stdout.write(f"Failed: {payload['documents_failed']}\n")
    stdout.write(f"Warnings: {payload['warning_count']}\n")
    stdout.write(f"Limitations: {payload['limitation_count']}\n")
    stdout.write(f"Report: {payload['consolidated_report_path']}\n")
    if args.open_report:
        stdout.write("Open report requested; report path printed above.\n")


__all__ = ["run_pdf_validate"]
