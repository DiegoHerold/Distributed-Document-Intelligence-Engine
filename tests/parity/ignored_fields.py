from __future__ import annotations

IGNORED_PATHS: frozenset[str] = frozenset(
    {
        "correlation_id",
        "details.task_id",
        "details.timeout",
        "execution_metadata",
        "job.created_at",
        "job.job_id",
        "metadata.filename",
        "status.completed_at",
        "status.created_at",
        "status.job_id",
        "status.started_at",
        "cancel.completed_at",
        "cancel.created_at",
        "cancel.job_id",
        "cancel.started_at",
    }
)

IGNORED_PATH_REASONS: dict[str, str] = {
    "correlation_id": "Each transport creates or propagates correlation IDs differently.",
    "details.task_id": "Runtime task IDs are channel-local execution metadata.",
    "details.timeout": "Timeout duration is runtime diagnostic metadata.",
    "execution_metadata": "Execution timing and correlation metadata are channel-local.",
    "job.created_at": "Submitted jobs are created independently in each channel.",
    "job.job_id": "Submit job IDs are non-deterministic per local engine instance.",
    "metadata.filename": "HTTP and local file paths can sanitize or preserve names differently.",
    "status.completed_at": "Job lifecycle timestamps are execution metadata.",
    "status.created_at": "Job lifecycle timestamps are execution metadata.",
    "status.job_id": "Job status IDs differ across channel-local job stores.",
    "status.started_at": "Job lifecycle timestamps are execution metadata.",
    "cancel.completed_at": "Cancellation timestamps are execution metadata.",
    "cancel.created_at": "Cancellation timestamps are execution metadata.",
    "cancel.job_id": "Cancelled job IDs differ across channel-local job stores.",
    "cancel.started_at": "Cancellation timestamps are execution metadata.",
}


__all__ = ["IGNORED_PATHS", "IGNORED_PATH_REASONS"]
