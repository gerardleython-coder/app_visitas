from dataclasses import dataclass
from uuid import UUID

from app.domain.authentication import UserRole


@dataclass(frozen=True, slots=True)
class OperatorProfile:
    id: UUID
    name: str
    surname: str
    email: str
    role: UserRole
    active: bool
    district_id: UUID | None
    church_id: UUID | None
    phone: str | None = None
    address: str | None = None
    is_primary_pastor: bool = False