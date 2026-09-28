from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RefreshSession:
    id: UUID
    family_id: UUID
    user_id: UUID
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None
    replaced_by_id: UUID | None