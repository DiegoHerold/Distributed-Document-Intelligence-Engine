from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tests.parity.normalization import normalize_for_parity


@dataclass(frozen=True, slots=True)
class ChannelResult:
    channel: str
    value: Any


def assert_semantically_equal(*results: ChannelResult) -> None:
    if len(results) < 2:
        raise ValueError("at least two channel results are required")
    normalized = [
        ChannelResult(result.channel, normalize_for_parity(result.value))
        for result in results
    ]
    baseline = normalized[0]
    for candidate in normalized[1:]:
        mismatch = first_mismatch(baseline.value, candidate.value)
        if mismatch is not None:
            path, left, right = mismatch
            raise AssertionError(
                "Parity mismatch at:\n\n"
                f"{path}\n\n"
                f"{baseline.channel}:\n    {left!r}\n\n"
                f"{candidate.channel}:\n    {right!r}"
            )


def first_mismatch(left: Any, right: Any, path: str = "result") -> tuple[str, Any, Any] | None:
    if type(left) is not type(right):
        return path, left, right
    if isinstance(left, dict):
        left_keys = set(left)
        right_keys = set(right)
        if left_keys != right_keys:
            return f"{path}.__keys__", sorted(left_keys), sorted(right_keys)
        for key in sorted(left):
            mismatch = first_mismatch(left[key], right[key], f"{path}.{key}")
            if mismatch is not None:
                return mismatch
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return f"{path}.__len__", len(left), len(right)
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            mismatch = first_mismatch(left_item, right_item, f"{path}[{index}]")
            if mismatch is not None:
                return mismatch
        return None
    if left != right:
        return path, left, right
    return None


__all__ = ["ChannelResult", "assert_semantically_equal", "first_mismatch"]
