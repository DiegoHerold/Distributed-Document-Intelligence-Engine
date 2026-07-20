from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import pytest

from eixo.core import (
    CapabilityId,
    CapabilityStatus,
    CapabilityVersion,
    CorrelationId,
    ExecutionSerializationError,
    ProviderId,
    ProviderVersion,
    RuntimeShutdownError,
)
from eixo.plugins import (
    CapabilityDescriptor,
    CapabilityRegistry,
    ExecutionContext,
    ExecutionMode,
    ExecutionOptions,
    ExecutionStatus,
    ExecutionTask,
    ProviderDescriptor,
    RuntimeExecutionContext,
)
from eixo.runtime.local import LocalRuntime, LocalRuntimeConfig


async def async_echo(value: str, context: RuntimeExecutionContext) -> str:
    assert context.task_id is not None
    return f"{value}:{context.correlation_id}"


def blocking_double(value: int, context: RuntimeExecutionContext) -> int:
    assert context.metadata.get("kind") == "thread"
    time.sleep(0.05)
    return value * 2


def cpu_square(value: int, context: RuntimeExecutionContext) -> int:
    assert context.task_id is not None
    return value * value


async def slow_task(value: str, context: RuntimeExecutionContext) -> str:
    await asyncio.sleep(1)
    return value


async def progress_task(value: int, context: RuntimeExecutionContext) -> int:
    assert context.progress is not None
    await context.progress.report(current=1, total=2, message="half", stage="test")
    await context.progress.report(percentage=100, message="done")
    return value


async def cancellable_task(value: str, context: RuntimeExecutionContext) -> str:
    assert context.cancellation_token is not None
    for _ in range(10):
        context.cancellation_token.raise_if_cancelled()
        await asyncio.sleep(0.05)
    return value


async def failing_task(value: str, context: RuntimeExecutionContext) -> str:
    raise ValueError(f"boom:{value}")


@dataclass(slots=True)
class FakeCapability:
    descriptor: CapabilityDescriptor

    async def execute(self, request: str, context: ExecutionContext) -> str:
        return f"{request}:{context.metadata['task_id']}"


def make_context() -> ExecutionContext:
    return ExecutionContext(correlation_id=CorrelationId.new(), metadata={"kind": "thread"})


def test_async_task_preserves_context_and_metadata() -> None:
    async def run() -> None:
        async with LocalRuntime() as runtime:
            task = ExecutionTask(
                task_id="task_async",
                name="async",
                handler=async_echo,
                input="ok",
            )
            result = await runtime.execute(task, context=make_context())
            assert result.status is ExecutionStatus.COMPLETED
            assert result.value is not None
            assert result.value.startswith("ok:corr_")
            assert result.started_at is not None
            assert result.completed_at is not None
            assert result.duration is not None

    asyncio.run(run())


def test_thread_task_does_not_block_event_loop() -> None:
    async def run() -> None:
        async with LocalRuntime() as runtime:
            task = ExecutionTask(
                task_id="task_thread",
                name="thread",
                handler=blocking_double,
                input=21,
                execution_mode=ExecutionMode.THREAD,
            )
            sleeper = asyncio.create_task(asyncio.sleep(0.01))
            result = await runtime.execute(task, context=make_context())
            assert sleeper.done()
            assert result.value == 42

    asyncio.run(run())


def test_process_task_and_serialization_error() -> None:
    async def run() -> None:
        async with LocalRuntime() as runtime:
            task = ExecutionTask(
                task_id="task_process",
                name="process",
                handler=cpu_square,
                input=9,
                execution_mode=ExecutionMode.PROCESS,
            )
            result = await runtime.execute(task, context=make_context())
            assert result.status is ExecutionStatus.COMPLETED
            assert result.value == 81

            bad_task = ExecutionTask(
                task_id="task_bad_process",
                name="bad-process",
                handler=lambda value, context: value,  # noqa: E731
                input=1,
                execution_mode=ExecutionMode.PROCESS,
            )
            failed = await runtime.execute(bad_task, context=make_context())
            assert failed.status is ExecutionStatus.FAILED
            assert failed.error is not None
            assert failed.error.code == ExecutionSerializationError.code

    asyncio.run(run())


def test_timeout_and_cancel_are_structured() -> None:
    async def run() -> None:
        async with LocalRuntime(LocalRuntimeConfig(default_timeout=0.05)) as runtime:
            timed_out = await runtime.execute(
                ExecutionTask(task_id="task_timeout", name="timeout", handler=slow_task, input="x"),
                context=make_context(),
            )
            assert timed_out.status is ExecutionStatus.TIMED_OUT
            assert timed_out.error is not None
            assert timed_out.error.code == "execution.timeout"

            handle = await runtime.submit(
                ExecutionTask(
                    task_id="task_cancel",
                    name="cancel",
                    handler=cancellable_task,
                    input="x",
                ),
                context=make_context(),
                options=ExecutionOptions(disable_timeout=True),
            )
            await asyncio.sleep(0.02)
            assert await handle.cancel()
            result = await handle.wait()
            assert result.status is ExecutionStatus.CANCELLED

    asyncio.run(run())


def test_progress_callbacks_and_validation() -> None:
    async def run() -> None:
        updates = []
        async with LocalRuntime() as runtime:
            handle = await runtime.submit(
                ExecutionTask(
                    task_id="task_progress",
                    name="progress",
                    handler=progress_task,
                    input=7,
                ),
                context=make_context(),
            )
            handle._progress.subscribe(updates.append)
            result = await handle.wait()
            assert result.value == 7
            assert handle.progress is not None
            assert handle.progress.percentage == 100
            assert updates
            with pytest.raises(ValueError):
                await handle._progress.report(percentage=101)

    asyncio.run(run())


def test_concurrency_limit_and_context_isolation() -> None:
    async def run() -> None:
        running = 0
        max_seen = 0
        lock = asyncio.Lock()

        async def limited(value: int, context: RuntimeExecutionContext) -> str:
            nonlocal running, max_seen
            async with lock:
                running += 1
                max_seen = max(max_seen, running)
            await asyncio.sleep(0.05)
            async with lock:
                running -= 1
            return str(context.correlation_id)

        async with LocalRuntime(LocalRuntimeConfig(max_concurrent_tasks=1)) as runtime:
            handles = [
                await runtime.submit(
                    ExecutionTask(
                        task_id=f"task_limited_{idx}",
                        name="limited",
                        handler=limited,
                        input=idx,
                    ),
                    context=ExecutionContext(correlation_id=CorrelationId.new()),
                )
                for idx in range(3)
            ]
            results = [await handle.wait() for handle in handles]
            assert max_seen == 1
            values = {result.value for result in results}
            assert len(values) == 3

    asyncio.run(run())


def test_lifecycle_shutdown_and_rejection_after_shutdown() -> None:
    async def run() -> None:
        runtime = LocalRuntime()
        await runtime.start()
        await runtime.shutdown()
        await runtime.shutdown()
        with pytest.raises(RuntimeShutdownError):
            await runtime.submit(
                ExecutionTask(
                    task_id="task_rejected",
                    name="rejected",
                    handler=async_echo,
                    input="x",
                ),
                context=make_context(),
            )

    asyncio.run(run())


def test_registry_capability_and_runtime_integration() -> None:
    async def run() -> None:
        registry = CapabilityRegistry()
        provider_id = ProviderId.new()
        capability_id = CapabilityId.new()
        registry.register_provider(
            ProviderDescriptor(
                provider_id=provider_id,
                name="fake",
                version=ProviderVersion("1.0.0"),
                status=CapabilityStatus.ACTIVE,
            )
        )
        capability = FakeCapability(
            CapabilityDescriptor(
                capability_id=capability_id,
                name="fake-capability",
                description="Fake",
                version=CapabilityVersion("1.0.0"),
                input_contract="str",
                output_contract="str",
                supported_formats=("txt",),
                supported_media_types=("text/plain",),
                provider_id=provider_id,
                provider_version=ProviderVersion("1.0.0"),
            )
        )
        registry.register(capability)
        resolved = registry.resolve(document_format="txt")
        async with LocalRuntime() as runtime:
            result = await runtime.execute_capability(
                resolved,
                "hello",
                context=make_context(),
            )
            assert result.status is ExecutionStatus.COMPLETED
            assert result.value == f"hello:task_{capability_id}"

    asyncio.run(run())


def test_capability_failure_is_structured() -> None:
    async def run() -> None:
        async with LocalRuntime() as runtime:
            result = await runtime.execute(
                ExecutionTask(task_id="task_fail", name="fail", handler=failing_task, input="x"),
                context=make_context(),
            )
            assert result.status is ExecutionStatus.FAILED
            assert result.error is not None
            assert result.error.code == "execution.error"

    asyncio.run(run())
