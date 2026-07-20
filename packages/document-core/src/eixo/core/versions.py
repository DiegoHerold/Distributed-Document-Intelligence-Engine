from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Self

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")


@dataclass(frozen=True, slots=True, order=True)
class SemanticVersion:
    value: str

    def __post_init__(self) -> None:
        if not _SEMVER.match(self.value):
            raise ValueError(f"Invalid semantic version: {self.value!r}")

    @classmethod
    def parse(cls, value: str) -> Self:
        return cls(value)

    def __str__(self) -> str:
        return self.value


class SchemaVersion(SemanticVersion):
    pass


class ContractVersion(SemanticVersion):
    pass


class ProviderVersion(SemanticVersion):
    pass


class CapabilityVersion(SemanticVersion):
    pass

