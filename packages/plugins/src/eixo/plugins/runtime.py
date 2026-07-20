from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Generic, Protocol, TypeVar

from eixo.core.errors import ErrorPayload, ExecutionCancelledError
from eixo.core.ids import (
    CapabilityId,
    CorrelationId,
    DocumentId,
    JobId,
    ProviderId,
    TenantId,
    TraceId,
)
from eixo.core.serialization import Serializable
from eixo.core.timestamps import ensure_utc, utc_now
from eixo.core.warnings import EixoWarning
from eixo.plugins.capabilities import ExecutionContext

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class ExecutionMode(StrEnum):
    ASYNC = "async"
    THREAD = "thread"
    PROCESS = "process"


class ExecutionStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class ExecutionOptions(Serializable):
    timeout: float | None = None
    disable_timeout: bool = False


@dataclass(frozen=True, slots=True)
class ProgressUpdate(Serializable):
    current: float | None = None
    total: float | None = None
    percentage: float | None = None
    message: str | None = None
    stage: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.current is not None and self.current < 0:
            raise ValueError("current progress cannot be negative")
        if self.total is not None and self.total <= 0:
            raise ValueError("total progress must be positive")
        if self.current is not None and self.total is not None and self.current > self.total:
            raise ValueError("current progress cannot exceed total")
        if self.percentage is not None and (
            self.percentage < 0 or self.percentage > 100
        ):
            raise ValueError("percentage must be between 0 and 100")
        object.__setattr__(self, "timestamp", ensure_utc(self.timestamp))


ProgressCallback = Callable[[ProgressUpdate], None | Awaitable[None]]


class ProgressReporter:
    def __init__(self) -> None:
        self._latest: ProgressUpdate | None = None
        self._callbacks: list[ProgressCallback] = []
        self._lock = asyncio.Lock()

    @property
    def latest(self) -> ProgressUpdate | None:
        return self._latest

    def subscribe(self, callback: ProgressCallback) -> None:
        self._callbacks.append(callback)

    async def report(
        self,
        *,
        current: float | None = None,
        total: float | None = None,
        percentage: float | None = None,
        message: str | None = None,
        stage: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> ProgressUpdate:
        if percentage is None and current is not None and total is not None:
            percentage = round((current / total) * 100, 4)
        update = ProgressUpdate(
            current=current,
            total=total,
            percentage=percentage,
            message=message,
            stage=stage,
            metadata=metadata or {},
        )
        async with self._lock:
            self._latest = update
            callbacks = tuple(self._callbacks)
        for callback in callbacks:
            result = callback(update)
            if result is not None:
                await result
        return update


class CancellationToken:
    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise ExecutionCancelledError("Execution was cancelled")

    async def wait(self) -> None:
        await self._event.wait()


@dataclass(frozen=True, slots=True)
class RuntimeExecutionContext(Serializable):
    correlation_id: CorrelationId
    trace_id: TraceId | None = None
    tenant_id: TenantId | None = None
    job_id: JobId | None = None
    document_id: DocumentId | None = None
    task_id: str | None = None
    capability_id: CapabilityId | None = None
    provider_id: ProviderId | None = None
    cancellation_token: CancellationToken | None = None
    progress: ProgressReporter | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_execution_context(
        cls,
        context: ExecutionContext,
        *,
        task_id: str | None = None,
        capability_id: CapabilityId | None = None,
        provider_id: ProviderId | None = None,
        cancellation_token: CancellationToken | None = None,
        progress: ProgressReporter | None = None,
    ) -> "RuntimeExecutionContext":
        return cls(
            correlation_id=context.correlation_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            task_id=task_id,
            capability_id=capability_id,
            provider_id=provider_id,
            cancellation_token=cancellation_token,
            progress=progress,
            metadata=context.metadata,
        )

    def to_capability_context(self) -> ExecutionContext:
        metadata = dict(self.metadata)
        if self.task_id is not None:
            metadata["task_id"] = self.task_id
        return ExecutionContext(
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
            tenant_id=self.tenant_id,
            metadata=metadata,
        )


TaskHandler = Callable[[InputT, RuntimeExecutionContext], OutputT | Awaitable[OutputT]]


@dataclass(frozen=True, slots=True)
class ExecutionTask(Generic[InputT, OutputT], Serializable):
    task_id: str
    name: str
    handler: TaskHandler[InputT, OutputT]
    input: InputT
    execution_mode: ExecutionMode = ExecutionMode.ASYNC
    capability_id: CapabilityId | None = None
    timeout: float | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id cannot be empty")
        if not self.name.strip():
            raise ValueError("task name cannot be empty")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be positive")


@dataclass(frozen=True, slots=True)
class ExecutionResult(Generic[OutputT], Serializable):
    task_id: str
    status: ExecutionStatus
    value: OutputT | None = None
    error: ErrorPayload | None = None
    warnings: tuple[EixoWarning, ...] = ()
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: timedelta | None = None
    execution_mode: ExecutionMode = ExecutionMode.ASYNC
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for attr in ("started_at", "completed_at"):
            value = getattr(self, attr)
            if value is not None:
                object.__setattr__(self, attr, ensure_utc(value))


class ExecutionHandle(Protocol, Generic[OutputT]):
    id: str

    @property
    def status(self) -> ExecutionStatus:
        ...

    @property
    def progress(self) -> ProgressUpdate | None:
        ...

    def done(self) -> bool:
        ...

    async def wait(self) -> ExecutionResult[OutputT]:
        ...

    async def result(self) -> OutputT:
        ...

    async def cancel(self) -> bool:
        ...


class ExecutionRuntime(Protocol):
    async def execute(
        self,
        task: ExecutionTask[InputT, OutputT],
        *,
        context: ExecutionContext,
        options: ExecutionOptions | None = None,
    ) -> ExecutionResult[OutputT]:
        ...

    async def submit(
        self,
        task: ExecutionTask[InputT, OutputT],
        *,
        context: ExecutionContext,
        options: ExecutionOptions | None = None,
    ) -> ExecutionHandle[OutputT]:
        ...

    async def start(self) -> None:
        ...

    async def shutdown(self) -> None:
        ...

