from __future__ import annotations

from collections.abc import Callable

from eixo import DocumentEngine

EngineFactory = Callable[[], DocumentEngine]


def create_local_engine() -> DocumentEngine:
    return DocumentEngine.local()


__all__ = ["EngineFactory", "create_local_engine"]
