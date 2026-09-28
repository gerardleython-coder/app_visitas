from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    PASTOR = "PASTOR"
    LIDER = "LIDER"
    HERMANO = "HERMANO"


@dataclass(frozen=True, slots=True)
class UserAccount:
    id: UUID
    email: str
    password_hash: str | None
    role: UserRole
    active: bool