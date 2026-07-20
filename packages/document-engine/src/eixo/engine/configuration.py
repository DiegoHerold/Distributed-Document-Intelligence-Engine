from __future__ import annotations

from dataclasses import dataclass, field

from eixo.runtime.local import LocalRuntimeConfig


@dataclass(frozen=True, slots=True)
class LocalEngineConfig:
    runtime: LocalRuntimeConfig = field(default_factory=LocalRuntimeConfig)
    auto_start: bool = True

