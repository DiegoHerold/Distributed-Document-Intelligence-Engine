from __future__ import annotations

from pathlib import Path

from eixo import LocalPathSource


def local_path_source(path: str) -> LocalPathSource:
    resolved = Path(path).expanduser()
    if not resolved.exists():
        raise FileNotFoundError(path)
    if not resolved.is_file():
        raise IsADirectoryError(path)
    return LocalPathSource(
        path=resolved,
        filename=resolved.name,
        declared_media_type=guess_media_type(resolved),
        size=resolved.stat().st_size,
        metadata={"source": "cli"},
    )


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
