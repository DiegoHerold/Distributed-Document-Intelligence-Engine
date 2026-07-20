from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from eixo.runtime.local import LocalRuntimeConfig


@dataclass(frozen=True, slots=True)
class LocalEngineConfig:
    runtime: LocalRuntimeConfig = field(default_factory=LocalRuntimeConfig)
    auto_start: bool = True
    data_directory: Path = field(default_factory=lambda: Path(".eixo/local"))

    def __post_init__(self) -> None:
        if not str(self.data_directory).strip():
            raise ValueError("data_directory is required")
