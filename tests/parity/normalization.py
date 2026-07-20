from __future__ import annotations

from typing import Any

from eixo.core.serialization import to_jsonable
from tests.parity.ignored_fields import IGNORED_PATHS


def normalize_for_parity(
    value: Any,
    *,
    ignored_paths: frozenset[str] = IGNORED_PATHS,
) -> Any:
    return _normalize(to_jsonable(value), path="", ignored_paths=ignored_paths)


def _normalize(value: Any, *, path: str, ignored_paths: frozenset[str]) -> Any:
    if path in ignored_paths:
        return _Ignored
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in sorted(value.items()):
            child_path = key if not path else f"{path}.{key}"
            normalized = _normalize(item, path=child_path, ignored_paths=ignored_paths)
            if normalized is not _Ignored:
                result[key] = normalized
        return result
    if isinstance(value, list):
        return [
            normalized
            for index, item in enumerate(value)
            if (normalized := _normalize(
                item,
                path=f"{path}[{index}]",
                ignored_paths=ignored_paths,
            ))
            is not _Ignored
        ]
    return value


class _IgnoredValue:
    pass


_Ignored = _IgnoredValue()


__all__ = ["normalize_for_parity"]
