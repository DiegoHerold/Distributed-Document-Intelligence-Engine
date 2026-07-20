from __future__ import annotations

import json
from typing import Any

from eixo.core.serialization import to_jsonable


def render_json(value: Any, *, pretty: bool = False) -> str:
    return json.dumps(
        to_jsonable(value),
        ensure_ascii=False,
        indent=2 if pretty else None,
        sort_keys=pretty,
    )


__all__ = ["render_json"]
