from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from eixo.core.serialization import to_jsonable
from eixo_cli.output.console_renderer import render_console
from eixo_cli.output.json_renderer import render_json


class Writer(Protocol):
    def write(self, value: str) -> object:
        ...


@dataclass(frozen=True, slots=True)
class OutputOptions:
    format: str = "console"
    output: Path | None = None
    pretty: bool = False
    quiet: bool = False
    force: bool = False

    @classmethod
    def from_args(cls, args: Any) -> "OutputOptions":
        output = getattr(args, "output", None)
        return cls(
            format=getattr(args, "format", "console"),
            output=Path(output) if output else None,
            pretty=getattr(args, "pretty", False),
            quiet=getattr(args, "quiet", False),
            force=getattr(args, "force", False),
        )


def render_or_write(value: Any, options: OutputOptions, stdout: Writer) -> None:
    if options.output is not None:
        write_json_file(value, options.output, pretty=options.pretty, force=options.force)
        if not options.quiet:
            stdout.write(f"Resultado gravado em {options.output}\n")
        return
    if options.format == "json":
        stdout.write(render_json(value, pretty=options.pretty) + "\n")
        return
    stdout.write(render_console(value, quiet=options.quiet) + "\n")


def write_json_file(value: Any, path: Path, *, pretty: bool, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(str(path))
    parent = path.parent
    if str(parent) and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    text = render_json(to_jsonable(value), pretty=pretty)
    path.write_text(text + "\n", encoding="utf-8")


__all__ = ["OutputOptions", "render_or_write", "write_json_file"]
