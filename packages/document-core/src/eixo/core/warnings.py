from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from eixo.core.enums import Severity
from eixo.core.serialization import Serializable


@dataclass(frozen=True, slots=True)
class EixoWarning(Serializable):
    code: str
    message: str
    severity: Severity = Severity.WARNING
    scope: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

