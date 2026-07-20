from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from eixo.core.ids import CorrelationId, TenantId, TraceId
from eixo.core.serialization import Serializable
from eixo.core.timestamps import ensure_utc, utc_now
from eixo.core.versions import ContractVersion, SemanticVersion


@dataclass(frozen=True, slots=True)
class ExecutionMetadata(Serializable):
    correlation_id: CorrelationId
    trace_id: TraceId | None = None
    tenant_id: TenantId | None = None
    requested_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: timedelta | None = None
    engine_version: SemanticVersion | None = None
    contract_version: ContractVersion | None = None

    def __post_init__(self) -> None:
        for name in ("requested_at", "started_at", "completed_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, ensure_utc(value))

    @classmethod
    def requested(cls, correlation_id: CorrelationId | None = None) -> "ExecutionMetadata":
        return cls(correlation_id=correlation_id or CorrelationId.new(), requested_at=utc_now())

