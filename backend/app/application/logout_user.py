from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from app.domain.session import RefreshSession


class RefreshSessionRepository(Protocol):
    async def get_by_hash_for_update(self, token_hash: str) -> RefreshSession | None: ...

    async def revoke_family(self, family_id: UUID, revoked_at: datetime) -> None: ...


class LogoutUser:
    def __init__(self, sessions: RefreshSessionRepository) -> None:
        self._sessions = sessions

    async def execute(self, refresh_token: str) -> bool:
        token_hash = sha256(refresh_token.encode("utf-8")).hexdigest()
        session = await self._sessions.get_by_hash_for_update(token_hash)
        if session is None:
            return False

        await self._sessions.revoke_family(session.family_id, datetime.now(UTC))
        return True