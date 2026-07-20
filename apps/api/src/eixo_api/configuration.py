from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

API_VERSION = "0.1.0"


@dataclass(frozen=True, slots=True)
class ApiConfig:
    title: str = "Eixo API"
    description: str = (
        "Initial REST adapter for the Eixo Distributed Document Intelligence Engine."
    )
    version: str = API_VERSION
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    docs_enabled: bool = True
    cors_allowed_origins: tuple[str, ...] = ()
    max_upload_size: int = 10 * 1024 * 1024
    request_timeout: float = 30.0
    local_data_dir: Path = field(default_factory=lambda: Path(".eixo/api").resolve())

    def __post_init__(self) -> None:
        if self.port <= 0 or self.port > 65535:
            raise ValueError("port must be between 1 and 65535")
        if self.max_upload_size <= 0:
            raise ValueError("max_upload_size must be positive")
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be positive")


ApiSettings = ApiConfig


__all__ = ["API_VERSION", "ApiConfig", "ApiSettings"]
