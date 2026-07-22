from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import FastAPI

from eixo.engine import DocumentEngine
from eixo.engine.lifecycle import EngineState
from eixo.diagnostics import TemporaryDiagnosticConfig, TemporaryDiagnosticStore
from eixo_api.configuration import ApiConfig


@dataclass(slots=True)
class ApiState:
    config: ApiConfig
    engine: DocumentEngine | None
    ready: bool = False
    shutting_down: bool = False
    startup_error: str | None = None
    temporary_diagnostic_store: TemporaryDiagnosticStore | None = None
    temporary_diagnostic_engine_factory: object | None = None

    def require_engine(self) -> DocumentEngine:
        if self.engine is None:
            self.engine = DocumentEngine.local(
                default_timeout=self.config.request_timeout,
                data_directory=self.config.local_data_dir,
            )
        return self.engine

    def require_temporary_diagnostic_store(self) -> TemporaryDiagnosticStore:
        if self.temporary_diagnostic_store is None:
            self.temporary_diagnostic_store = TemporaryDiagnosticStore(
                TemporaryDiagnosticConfig(
                    root_directory=self.config.temporary_diagnostics_dir,
                    heartbeat_interval=(
                        self.config.temporary_diagnostic_heartbeat_interval
                    ),
                    inactive_session_grace_period=(
                        self.config.temporary_diagnostic_inactive_grace_period
                    ),
                    maximum_session_lifetime=(
                        self.config.temporary_diagnostic_maximum_lifetime
                    ),
                    cleanup_interval=self.config.temporary_diagnostic_cleanup_interval,
                    max_upload_size=self.config.max_upload_size,
                )
            )
        return self.temporary_diagnostic_store

    def readiness_checks(self) -> dict[str, str]:
        if self.shutting_down:
            return {"application": "shutting_down"}
        if self.startup_error is not None:
            return {"startup": "failed"}
        if self.engine is None:
            return {"engine": "not_started"}
        checks = {
            "engine": "ok" if self.engine.state == EngineState.RUNNING else "failed",
            "runtime": "ok" if self.engine.runtime is not None else "failed",
            "registry": "ok" if self.engine.registry is not None else "failed",
            "job_store": (
                "ok"
                if self.engine.get_job_status_use_case is not None
                and self.engine.get_job_result_use_case is not None
                else "failed"
            ),
        }
        return checks

    def is_ready(self) -> bool:
        checks = self.readiness_checks()
        return bool(checks) and all(value == "ok" for value in checks.values())


@asynccontextmanager
async def api_lifespan(app: FastAPI) -> AsyncIterator[None]:
    state: ApiState = app.state.eixo
    try:
        engine = state.require_engine()
        await engine.start()
        state.ready = True
        state.startup_error = None
        yield
    except Exception as exc:
        state.ready = False
        state.startup_error = type(exc).__name__
        raise
    finally:
        state.shutting_down = True
        engine = state.engine
        if engine is not None:
            await engine.shutdown()
        store = state.temporary_diagnostic_store
        if store is not None:
            for session_id in list(store.sessions):
                store.close_session(session_id)
        state.ready = False


__all__ = ["ApiState", "api_lifespan"]
