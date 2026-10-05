from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class VisitType(StrEnum):
    EVANGELISMO = "EVANGELISMO"
    ENSENANZA = "ENSENANZA"
    CUIDADO_PASTORAL = "CUIDADO_PASTORAL"


class VisitStatus(StrEnum):
    PROGRAMADA = "PROGRAMADA"
    COMPLETADA = "COMPLETADA"
    CANCELADA = "CANCELADA"


@dataclass(frozen=True, slots=True)
class Visit:
    id: UUID
    brother_id: UUID
    leader_id: UUID
    church_id: UUID
    created_by_id: UUID
    visit_type: VisitType
    scheduled_at: datetime
    completed_at: datetime | None
    duration_minutes: int
    location: str
    observations: str
    status: VisitStatus
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class VisitHistoryEntry:
    id: UUID
    visit_id: UUID
    actor_id: UUID
    action: str
    previous_status: VisitStatus | None
    new_status: VisitStatus | None
    previous_scheduled_at: datetime | None
    new_scheduled_at: datetime | None
    previous_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    reason: str | None
    created_at: datetime