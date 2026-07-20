from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LocalRuntimeConfig:
    max_concurrent_tasks: int = 8
    max_thread_workers: int = 4
    max_process_workers: int = 2
    default_timeout: float | None = 30.0
    shutdown_timeout: float = 10.0
    cancel_pending_on_shutdown: bool = True

    def __post_init__(self) -> None:
        if self.max_concurrent_tasks < 1:
            raise ValueError("max_concurrent_tasks must be greater than zero")
        if self.max_thread_workers < 1:
            raise ValueError("max_thread_workers must be greater than zero")
        if self.max_process_workers < 1:
            raise ValueError("max_process_workers must be greater than zero")
        if self.default_timeout is not None and self.default_timeout <= 0:
            raise ValueError("default_timeout must be positive")
        if self.shutdown_timeout <= 0:
            raise ValueError("shutdown_timeout must be positive")

