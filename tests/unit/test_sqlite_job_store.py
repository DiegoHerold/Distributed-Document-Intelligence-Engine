from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from eixo.application.jobs import (
    JobTransitionPolicy,
    LocalJobRecoveryService,
    SQLiteJobStore,
    new_job_record,
)
from eixo.core import (
    BytesSource,
    JobConcurrencyError,
    JobId,
    JobQuery,
    JobResultUnavailableError,
    JobStatus,
    JobStoredResult,
    ProcessingRequest,
    ProcessingResult,
    ProcessingStatus,
    isoformat_utc,
    utc_now,
)


def request() -> ProcessingRequest:
    return ProcessingRequest(source=BytesSource(content=b"%PDF-1.7\n", size=9))


@pytest.mark.anyio
async def test_sqlite_job_store_persists_jobs_and_results(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    policy = JobTransitionPolicy.default()
    created = new_job_record(JobId.new(), request(), operation="process")

    await store.create(created)
    queued = policy.transition(created, to_status=JobStatus.QUEUED)
    await store.update(queued, expected_version=created.version)
    loaded = await store.get(created.job_id)

    assert loaded.status == JobStatus.QUEUED
    assert loaded.request["profile"] == "balanced"

    result = ProcessingResult(
        job_id=created.job_id,
        document_id=None,
        status=ProcessingStatus.COMPLETED,
        data={"ok": True},
    )
    await store.save_result(
        JobStoredResult(
            job_id=created.job_id,
            result=result,
            stored_at=isoformat_utc(utc_now()),
        )
    )

    stored = await store.get_result(created.job_id)
    assert stored.result.data == {"ok": True}


@pytest.mark.anyio
async def test_sqlite_job_store_lists_and_detects_version_conflicts(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    created = new_job_record(JobId.new(), request(), operation="process")

    await store.create(created)
    page = await store.list(JobQuery(status=JobStatus.CREATED))

    assert page.total == 1
    assert page.items[0].job_id == created.job_id

    changed = replace(created, status=JobStatus.QUEUED, version=created.version + 1)
    await store.update(changed, expected_version=created.version)
    with pytest.raises(JobConcurrencyError):
        await store.update(changed, expected_version=created.version)


@pytest.mark.anyio
async def test_job_recovery_marks_non_terminal_jobs(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    policy = JobTransitionPolicy.default()
    running = policy.transition(
        policy.transition(
            new_job_record(JobId.new(), request(), operation="process"),
            to_status=JobStatus.QUEUED,
        ),
        to_status=JobStatus.RUNNING,
    )
    await store.create(running)

    await LocalJobRecoveryService(store, policy).recover()

    recovered = await store.get(running.job_id)
    assert recovered.status == JobStatus.FAILED
    assert recovered.error is not None
    assert recovered.error.code == "job.interrupted"


@pytest.mark.anyio
async def test_sqlite_job_store_reports_missing_result(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    created = new_job_record(JobId.new(), request(), operation="process")
    await store.create(created)

    with pytest.raises(JobResultUnavailableError):
        await store.get_result(created.job_id)
