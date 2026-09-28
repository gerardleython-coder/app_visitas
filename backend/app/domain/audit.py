from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: UUID
    actor_id: UUID
    resource: str
    resource_id: UUID
    action: str
    church_id: UUID | None
    previous_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    reason: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AuditRecord:
    actor_id: UUID
    resource: str
    resource_id: UUID
    action: str
    church_id: UUID | None
    previous_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    reason: str | None = None
    created_at: datetime | None = None