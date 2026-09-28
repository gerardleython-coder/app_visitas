from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from app.application.logout_user import LogoutUser
from app.domain.session import RefreshSession


@dataclass
class FakeRefreshSessionRepository:
    stored_session: RefreshSession | None
    revoked_families: list[tuple[UUID, datetime]] = field(default_factory=list)

    async def get_by_hash_for_update(self, token_hash: str) -> RefreshSession | None:
        assert token_hash == sha256("logout-refresh-token".encode()).hexdigest()
        return self.stored_session

    async def revoke_family(self, family_id: UUID, revoked_at: datetime) -> None:
        self.revoked_families.append((family_id, revoked_at))


async def test_logout_revokes_entire_session_family() -> None:
    session = RefreshSession(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
        used_at=None,
        revoked_at=None,
        replaced_by_id=None,
    )
    sessions = FakeRefreshSessionRepository(session)
    logout = LogoutUser(sessions)

    revoked = await logout.execute("logout-refresh-token")

    assert revoked is True
    assert len(sessions.revoked_families) == 1
    assert sessions.revoked_families[0][0] == session.family_id


async def test_logout_is_idempotent_for_unknown_refresh_token() -> None:
    sessions = FakeRefreshSessionRepository(None)
    logout = LogoutUser(sessions)

    revoked = await logout.execute("logout-refresh-token")

    assert revoked is False
    assert sessions.revoked_families == []
