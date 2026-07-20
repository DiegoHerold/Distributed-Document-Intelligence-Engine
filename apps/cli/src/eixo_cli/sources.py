from __future__ import annotations

from pathlib import Path

from eixo import DocumentSource, LocalPathSource


def local_path_source(path: str) -> LocalPathSource:
    resolved = Path(path).expanduser()
    source = DocumentSource.from_path(
        resolved,
        declared_media_type=guess_media_type(resolved),
        metadata={"source": "cli"},
    )
    return source


def guess_media_type(path: Path) -> str | None:
    suffix = path.suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".json": "application/json",
    }.get(suffix)


__all__ = ["guess_media_type", "local_path_source"]
