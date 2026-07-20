from __future__ import annotations

import asyncio
from dataclasses import dataclass

from eixo.core.errors import ExecutionCancelledError, ExecutionError
from eixo.plugins import (
    CancellationToken,
    ExecutionMode,
    ExecutionResult,
    ExecutionStatus,
    ProgressReporter,
    ProgressUpdate,
)


@dataclass(slots=True)
class LocalExecutionHandle:
    id: str
    _task: asyncio.Task[ExecutionResult[object]]
    _progress: ProgressReporter
    _token: CancellationToken
    _status: ExecutionStatus = ExecutionStatus.QUEUED
    _cancel_requested: bool = False

    @property
    def status(self) -> ExecutionStatus:
        if self._task.done() and self._status in {
            ExecutionStatus.CREATED,
            ExecutionStatus.QUEUED,
            ExecutionStatus.RUNNING,
        }:
            try:
                return self._task.result().status
            except asyncio.CancelledError:
                return ExecutionStatus.CANCELLED
            except Exception:
                return ExecutionStatus.FAILED
        return self._status

    @status.setter
    def status(self, value: ExecutionStatus) -> None:
        self._status = value

    @property
    def progress(self) -> ProgressUpdate | None:
        return self._progress.latest

    def done(self) -> bool:
        return self._task.done()

    async def wait(self) -> ExecutionResult[object]:
        try:
            return await self._task
        except asyncio.CancelledError:
            self._status = ExecutionStatus.CANCELLED
            return ExecutionResult(
                task_id=self.id,
                status=ExecutionStatus.CANCELLED,
                error=ExecutionCancelledError("Task was cancelled").to_payload(),
                execution_mode=ExecutionMode.ASYNC,
            )

    async def result(self) -> object:
        result = await self.wait()
        if result.status == ExecutionStatus.COMPLETED:
            return result.value
        if result.status == ExecutionStatus.CANCELLED:
            raise ExecutionCancelledError("Execution was cancelled")
        if result.error is not None:
            raise ExecutionError(result.error.message, details=result.error.details)
        raise ExecutionError(f"Execution ended with status {result.status}")

    async def cancel(self) -> bool:
        self._cancel_requested = True
        if self._task.done():
            return False
        self._token.cancel()
        self._status = ExecutionStatus.CANCELLED
        return self._task.cancel()
