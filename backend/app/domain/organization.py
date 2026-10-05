from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class District:
    id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class Church:
    id: UUID
    district_id: UUID
    active: bool = True
    name: str = ""
    address: str | None = None