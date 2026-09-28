from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.authentication import UserAccount
from app.domain.visit import VisitStatus, VisitType


@dataclass(frozen=True, slots=True)
class CreateVisitCommand:
    actor: UserAccount
    brother_id: UUID
    visit_type: VisitType
    scheduled_at: datetime
    duration_minutes: int
    location: str
    observations: str


@dataclass(frozen=True, slots=True)
class UpdateVisitCommand:
    actor: UserAccount
    visit_id: UUID
    changes: dict[str, object]


@dataclass(frozen=True, slots=True)
class CancelVisitCommand:
    actor: UserAccount
    visit_id: UUID
    reason: str


@dataclass(frozen=True, slots=True)
class CompleteVisitCommand:
    actor: UserAccount
    visit_id: UUID
    status: VisitStatus = VisitStatus.COMPLETADA