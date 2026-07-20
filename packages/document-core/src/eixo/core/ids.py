from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Self
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class TypedId:
    value: str
    prefix: ClassVar[str] = "id"

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError(f"{self.__class__.__name__} cannot be empty")
        if not self.value.startswith(f"{self.prefix}_"):
            raise ValueError(f"{self.__class__.__name__} must start with '{self.prefix}_'")

    @classmethod
    def new(cls) -> Self:
        return cls(f"{cls.prefix}_{uuid4().hex}")

    @classmethod
    def parse(cls, value: str) -> Self:
        return cls(value)

    def __str__(self) -> str:
        return self.value


class DocumentId(TypedId):
    prefix = "doc"


class JobId(TypedId):
    prefix = "job"


class ArtifactId(TypedId):
    prefix = "art"


class PlanId(TypedId):
    prefix = "plan"


class ElementId(TypedId):
    prefix = "el"


class TemplateId(TypedId):
    prefix = "tpl"


class SchemaId(TypedId):
    prefix = "schema"


class CapabilityId(TypedId):
    prefix = "cap"


class ProviderId(TypedId):
    prefix = "prov"


class TenantId(TypedId):
    prefix = "tenant"


class CorrelationId(TypedId):
    prefix = "corr"


class TraceId(TypedId):
    prefix = "trace"

