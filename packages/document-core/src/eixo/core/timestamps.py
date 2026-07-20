from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def isoformat_utc(value: datetime) -> str:
    return ensure_utc(value).isoformat().replace("+00:00", "Z")

