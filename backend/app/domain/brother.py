from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class BrotherProfile:
    id: UUID
    name: str
    surname: str
    phone: str
    address: str
    district_id: UUID
    church_id: UUID
    leader_id: UUID
    active: bool