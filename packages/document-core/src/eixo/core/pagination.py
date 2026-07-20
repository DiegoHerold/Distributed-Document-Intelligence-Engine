from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from eixo.core.serialization import Serializable

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PageRequest(Serializable):
    limit: int = 50
    cursor: str | None = None
    page: int | None = None

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 500:
            raise ValueError("limit must be between 1 and 500")
        if self.page is not None and self.page < 1:
            raise ValueError("page must be greater than zero")


@dataclass(frozen=True, slots=True)
class PaginationMetadata(Serializable):
    limit: int
    total: int | None = None
    next_cursor: str | None = None
    page: int | None = None


@dataclass(frozen=True, slots=True)
class PageResult(Generic[T], Serializable):
    items: tuple[T, ...]
    pagination: PaginationMetadata

