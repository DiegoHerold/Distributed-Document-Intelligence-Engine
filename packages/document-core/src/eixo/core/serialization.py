from __future__ import annotations

import base64
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import Any, Mapping, Union, get_args, get_origin


class Serializable:
    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        return schema_for_type(cls)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    module = value.__class__.__module__
    if hasattr(value, "__str__") and module.startswith(("eixo.core.ids", "eixo.core.versions")):
        return str(value)
    if is_dataclass(value):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in fields(value)}
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(item) for item in value]
    return value


def schema_for_type(tp: Any) -> dict[str, Any]:
    origin = get_origin(tp)
    args = get_args(tp)
    if origin in (Union, UnionType):
        non_none = [arg for arg in args if arg is not type(None)]
        if len(non_none) == 1:
            return schema_for_type(non_none[0]) | {"nullable": True}
        return {"anyOf": [schema_for_type(arg) for arg in non_none]}
    if origin in (list, tuple, set, frozenset):
        item_type = args[0] if args else Any
        return {"type": "array", "items": schema_for_type(item_type)}
    if origin in (dict, Mapping):
        return {"type": "object"}
    if isinstance(tp, type) and issubclass(tp, Enum):
        return {"type": "string", "enum": [item.value for item in tp]}
    if is_dataclass(tp):
        properties: dict[str, Any] = {}
        required: list[str] = []
        for field in fields(tp):
            properties[field.name] = schema_for_type(field.type)
            if _is_required(field.type):
                required.append(field.name)
        schema: dict[str, Any] = {
            "type": "object",
            "title": tp.__name__,
            "properties": properties,
            "additionalProperties": False,
        }
        if required:
            schema["required"] = required
        return schema
    if tp in (str, Path):
        return {"type": "string"}
    if tp is bytes:
        return {"type": "string", "contentEncoding": "base64"}
    if tp is int:
        return {"type": "integer"}
    if tp is float:
        return {"type": "number"}
    if tp is bool:
        return {"type": "boolean"}
    if tp in (datetime,):
        return {"type": "string", "format": "date-time"}
    if tp in (timedelta,):
        return {"type": "number", "description": "Duration in seconds."}
    if tp is Any:
        return {}
    return {"type": "string"}


def _is_required(tp: Any) -> bool:
    origin = get_origin(tp)
    if origin in (Union, UnionType):
        return type(None) not in get_args(tp)
    return True
