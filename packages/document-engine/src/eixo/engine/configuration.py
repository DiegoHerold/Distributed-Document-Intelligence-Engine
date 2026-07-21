from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from eixo.core import IngestionSecurityPolicy
from eixo.pdf import PDFProviderSettings
from eixo.runtime.local import LocalRuntimeConfig


@dataclass(frozen=True, slots=True)
class LocalEngineConfig:
    runtime: LocalRuntimeConfig = field(default_factory=LocalRuntimeConfig)
    auto_start: bool = True
    data_directory: Path = field(default_factory=lambda: Path(".eixo/local"))
    job_database_path: Path | None = None
    security: IngestionSecurityPolicy = field(default_factory=IngestionSecurityPolicy)
    pdf: PDFProviderSettings = field(default_factory=PDFProviderSettings)

    def __post_init__(self) -> None:
        if not str(self.data_directory).strip():
            raise ValueError("data_directory is required")
        if self.job_database_path is not None and not str(self.job_database_path).strip():
            raise ValueError("job_database_path cannot be empty")
