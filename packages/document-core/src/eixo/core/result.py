from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from eixo.core.errors import ErrorPayload
from eixo.core.serialization import Serializable
from eixo.core.warnings import EixoWarning

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class OperationResult(Generic[T], Serializable):
    value: T | None = None
    warnings: tuple[EixoWarning, ...] = ()
    errors: tuple[ErrorPayload, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

