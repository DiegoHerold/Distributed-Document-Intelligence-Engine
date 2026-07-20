from __future__ import annotations

import asyncio
import inspect
import logging
import pickle
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypeVar

from eixo.core.errors import (
    EixoError,
    ExecutionCancelledError,
    ExecutionError,
    ExecutionRejectedError,
    ExecutionSerializationError,
    ExecutionTimeoutError,
    RuntimeShutdownError,
)
from eixo.core.timestamps import utc_now
from eixo.plugins import (
    CancellationToken,
    ExecutionContext,
    ExecutionMode,
    ExecutionOptions,
    ExecutionResult,
    ExecutionStatus,
    ExecutionTask,
    ProgressReporter,
    RuntimeExecutionContext,
)
from eixo.runtime.local.configuration import LocalRuntimeConfig
from eixo.runtime.local.context import current_execution_context
from eixo.runtime.local.handle import LocalExecutionHandle

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LocalRuntime:
    config: LocalRuntimeConfig = field(default_factory=LocalRuntimeConfig)
    _started: bool = False
    _shutdown: bool = False
    _semaphore: asyncio.Semaphore | None = None
    _thread_pool: ThreadPoolExecutor | None = None
    _process_pool: ProcessPoolExecutor | None = None
    _handles: dict[str, LocalExecutionHandle] = field(default_factory=dict)

    async def __aenter__(self) -> "LocalRuntime":
        await self.start()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.shutdown()

    async def start(self) -> None:
        if self._shutdown:
            raise RuntimeShutdownError("Runtime has already been shut down")
        if self._started:
            return
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_tasks)
        self._thread_pool = ThreadPoolExecutor(max_workers=self.config.max_thread_workers)
        self._process_pool = ProcessPoolExecutor(max_workers=self.config.max_process_workers)
        self._started = True
        self._log("runtime.started")

    async def shutdown(self) -> None:
        if self._shutdown:
            return
        self._log("runtime.stopping")
        self._shutdown = True
        pending = [handle for handle in self._handles.values() if not handle.done()]
        if self.config.cancel_pending_on_shutdown:
            for handle in pending:
                await handle.cancel()
        if pending:
            await asyncio.wait(
                [handle._task for handle in pending],
                timeout=self.config.shutdown_timeout,
            )
        if self._thread_pool is not None:
            self._thread_pool.shutdown(wait=False, cancel_futures=True)
        if self._process_pool is not None:
            self._process_pool.shutdown(wait=False, cancel_futures=True)
        self._log("runtime.stopped")

    async def execute(
        self,
        task: ExecutionTask[InputT, OutputT],
        *,
        context: ExecutionContext,
        options: ExecutionOptions | None = None,
    ) -> ExecutionResult[OutputT]:
        handle = await self.submit(task, context=context, options=options)
        result = await handle.wait()
        return result  # type: ignore[return-value]

    async def submit(
        self,
        task: ExecutionTask[InputT, OutputT],
        *,
        context: ExecutionContext,
        options: ExecutionOptions | None = None,
    ) -> LocalExecutionHandle:
        if self._shutdown:
            raise RuntimeShutdownError("Runtime is shut down")
        if not self._started:
            await self.start()
        progress = ProgressReporter()
        token = CancellationToken()
        runtime_context = RuntimeExecutionContext.from_execution_context(
            context,
            task_id=task.task_id,
            capability_id=task.capability_id,
            cancellation_token=token,
            progress=progress,
        )
        coroutine = self._run_task(task, runtime_context, token, options or ExecutionOptions())
        asyncio_task = asyncio.create_task(coroutine, name=task.task_id)
        handle = LocalExecutionHandle(
            id=task.task_id,
            _task=asyncio_task,  # type: ignore[arg-type]
            _progress=progress,
            _token=token,
        )
        self._handles[task.task_id] = handle
        self._log("task.submitted", task_id=task.task_id, mode=task.execution_mode.value)
        return handle

    async def execute_capability(
        self,
        capability: Any,
        request: InputT,
        *,
        context: ExecutionContext,
        options: ExecutionOptions | None = None,
    ) -> ExecutionResult[OutputT]:
        descriptor = capability.descriptor

        async def run_capability(
            value: InputT,
            runtime_context: RuntimeExecutionContext,
        ) -> OutputT:
            return await capability.execute(value, runtime_context.to_capability_context())

        task = ExecutionTask(
            task_id=f"task_{descriptor.capability_id}",
            name=descriptor.name,
            handler=run_capability,
            input=request,
            execution_mode=ExecutionMode.ASYNC,
            capability_id=descriptor.capability_id,
        )
        return await self.execute(task, context=context, options=options)

    async def _run_task(
        self,
        task: ExecutionTask[InputT, OutputT],
        runtime_context: RuntimeExecutionContext,
        token: CancellationToken,
        options: ExecutionOptions,
    ) -> ExecutionResult[OutputT]:
        if self._semaphore is None:
            raise RuntimeShutdownError("Runtime is not started")
        handle = self._handles.get(task.task_id)
        started_at: datetime | None = None
        async with self._semaphore:
            if handle is not None:
                handle.status = ExecutionStatus.RUNNING
            started_at = utc_now()
            self._log(
                "task.started",
                task_id=task.task_id,
                mode=task.execution_mode.value,
                correlation_id=str(runtime_context.correlation_id),
            )
            timeout = self._resolve_timeout(task, options)
            try:
                token.raise_if_cancelled()
                token_var = current_execution_context.set(runtime_context)
                try:
                    if timeout is None:
                        value = await self._execute_by_mode(task, runtime_context)
                    else:
                        async with asyncio.timeout(timeout):
                            value = await self._execute_by_mode(task, runtime_context)
                finally:
                    current_execution_context.reset(token_var)
                completed_at = utc_now()
                result = ExecutionResult(
                    task_id=task.task_id,
                    status=ExecutionStatus.COMPLETED,
                    value=value,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration=completed_at - started_at,
                    execution_mode=task.execution_mode,
                    metadata=task.metadata,
                )
                if handle is not None:
                    handle.status = ExecutionStatus.COMPLETED
                self._log_result("task.completed", result)
                return result
            except TimeoutError as exc:
                completed_at = utc_now()
                error = ExecutionTimeoutError(
                    f"Task timed out after {timeout} seconds",
                    details={"task_id": task.task_id, "timeout": timeout},
                    cause=exc,
                )
                result = self._error_result(
                    task,
                    ExecutionStatus.TIMED_OUT,
                    error,
                    started_at,
                    completed_at,
                )
                if handle is not None:
                    handle.status = ExecutionStatus.TIMED_OUT
                self._log_result("task.timed_out", result)
                return result
            except asyncio.CancelledError as exc:
                token.cancel()
                completed_at = utc_now()
                error = ExecutionCancelledError(
                    "Task was cancelled",
                    details={"task_id": task.task_id},
                    cause=exc,
                )
                result = self._error_result(
                    task,
                    ExecutionStatus.CANCELLED,
                    error,
                    started_at,
                    completed_at,
                )
                if handle is not None:
                    handle.status = ExecutionStatus.CANCELLED
                self._log_result("task.cancelled", result)
                return result
            except EixoError as exc:
                completed_at = utc_now()
                result = self._error_result(
                    task,
                    ExecutionStatus.FAILED,
                    exc,
                    started_at,
                    completed_at,
                )
                if handle is not None:
                    handle.status = ExecutionStatus.FAILED
                self._log_result("task.failed", result)
                return result
            except Exception as exc:
                completed_at = utc_now()
                error = ExecutionError(
                    "Task failed",
                    details={"task_id": task.task_id, "error_type": type(exc).__name__},
                    cause=exc,
                )
                result = self._error_result(
                    task,
                    ExecutionStatus.FAILED,
                    error,
                    started_at,
                    completed_at,
                )
                if handle is not None:
                    handle.status = ExecutionStatus.FAILED
                self._log_result("task.failed", result)
                return result

    async def _execute_by_mode(
        self,
        task: ExecutionTask[InputT, OutputT],
        runtime_context: RuntimeExecutionContext,
    ) -> OutputT:
        if task.execution_mode == ExecutionMode.ASYNC:
            value = task.handler(task.input, runtime_context)
            if inspect.isawaitable(value):
                return await value
            return value
        if task.execution_mode == ExecutionMode.THREAD:
            return await self._execute_thread(task, runtime_context)
        if task.execution_mode == ExecutionMode.PROCESS:
            return await self._execute_process(task, runtime_context)
        raise ExecutionRejectedError(f"Unsupported execution mode: {task.execution_mode}")

    async def _execute_thread(
        self,
        task: ExecutionTask[InputT, OutputT],
        runtime_context: RuntimeExecutionContext,
    ) -> OutputT:
        if self._thread_pool is None:
            raise RuntimeShutdownError("Thread pool is not available")
        loop = asyncio.get_running_loop()
        ctx = copy_context()

        def call() -> OutputT:
            return ctx.run(task.handler, task.input, runtime_context)  # type: ignore[return-value]

        return await loop.run_in_executor(self._thread_pool, call)

    async def _execute_process(
        self,
        task: ExecutionTask[InputT, OutputT],
        runtime_context: RuntimeExecutionContext,
    ) -> OutputT:
        if self._process_pool is None:
            raise RuntimeShutdownError("Process pool is not available")
        try:
            pickle.dumps((task.handler, task.input, runtime_context.metadata))
        except Exception as exc:
            raise ExecutionSerializationError(
                "Process tasks require serializable handlers and input",
                details={"task_id": task.task_id},
                cause=exc,
            ) from exc
        loop = asyncio.get_running_loop()
        process_context = RuntimeExecutionContext(
            correlation_id=runtime_context.correlation_id,
            trace_id=runtime_context.trace_id,
            tenant_id=runtime_context.tenant_id,
            job_id=runtime_context.job_id,
            document_id=runtime_context.document_id,
            task_id=runtime_context.task_id,
            capability_id=runtime_context.capability_id,
            provider_id=runtime_context.provider_id,
            metadata=runtime_context.metadata,
        )
        return await loop.run_in_executor(
            self._process_pool,
            _process_entrypoint,
            task.handler,
            task.input,
            process_context,
        )

    def _resolve_timeout(
        self,
        task: ExecutionTask[InputT, OutputT],
        options: ExecutionOptions,
    ) -> float | None:
        if options.disable_timeout:
            return None
        if options.timeout is not None:
            return options.timeout
        return task.timeout or self.config.default_timeout

    def _error_result(
        self,
        task: ExecutionTask[InputT, OutputT],
        status: ExecutionStatus,
        error: EixoError,
        started_at: datetime,
        completed_at: datetime,
    ) -> ExecutionResult[OutputT]:
        return ExecutionResult(
            task_id=task.task_id,
            status=status,
            error=error.to_payload(),
            started_at=started_at,
            completed_at=completed_at,
            duration=completed_at - started_at,
            execution_mode=task.execution_mode,
            metadata=task.metadata,
        )

    def _log(self, event: str, **fields: str) -> None:
        logger.info(event, extra={"event": event, **fields})

    def _log_result(self, event: str, result: ExecutionResult[Any]) -> None:
        self._log(
            event,
            task_id=result.task_id,
            status=result.status.value,
            mode=result.execution_mode.value,
            duration=str(result.duration.total_seconds() if result.duration else ""),
        )


def _process_entrypoint(
    handler: Any,
    value: Any,
    runtime_context: RuntimeExecutionContext,
) -> Any:
    result = handler(value, runtime_context)
    if inspect.isawaitable(result):
        raise ExecutionRejectedError("Process handlers must be synchronous")
    return result
