from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class DocumentStatus(StrEnum):
    RECEIVED = "received"
    VALIDATED = "validated"
    STORED = "stored"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REVIEW_REQUIRED = "review_required"
    CANCELLED = "cancelled"
    INSPECTED = "inspected"
    PARSED = "parsed"
    PROCESSED = "processed"
    FAILED = "failed"


class ProcessingStatus(StrEnum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactStatus(StrEnum):
    CREATED = "created"
    AVAILABLE = "available"
    FAILED = "failed"
    DELETED = "deleted"


class CapabilityStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class ResultStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"


class ErrorCategory(StrEnum):
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    CAPABILITY = "capability"
    EXECUTION = "execution"
    TIMEOUT = "timeout"
    CANCELLATION = "cancellation"
    UNSUPPORTED_FORMAT = "unsupported_format"
    NOT_FOUND = "not_found"
    STATE = "state"
    INTERNAL = "internal"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
