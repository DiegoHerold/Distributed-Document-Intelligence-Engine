from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    GENERAL_ERROR = 1
    INVALID_ARGUMENTS = 2
    SOURCE_NOT_FOUND = 3
    UNSUPPORTED_FORMAT = 4
    VALIDATION_ERROR = 5
    CAPABILITY_UNAVAILABLE = 6
    JOB_NOT_FOUND = 7
    PROCESSING_FAILED = 8
    PROCESSING_CANCELLED = 9
    TIMEOUT = 10
    CONFIGURATION_ERROR = 11


__all__ = ["ExitCode"]
