from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest

from app.application.authenticate_user import SessionTokens
from app.application.rotate_refresh_token import RotateRefreshToken
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import UnauthorizedException
from app.domain.session import RefreshSession


@dataclass
class FakeRefreshSessionRepository:
    stored_session: RefreshSession | None
    revoked_session_ids: list[UUID] = field(default_factory=list)
    revoked_family_ids: list[UUID] = field(default_factory=list)
    rotations: list[tuple[UUID, UUID, datetime]] = field(default_factory=list)

    async def get_by_hash_for_update(self, token_hash: str) -> RefreshSession | None:
        assert token_hash == sha256("old-refresh-token".encode()).hexdigest()
        return self.stored_session

    async def mark_rotated(
        self,
        session_id: UUID,
        replacement_id: UUID,
        used_at: datetime,
    ) -> None:
        self.rotations.append((session_id, replacement_id, used_at))

    async def revoke(self, session_id: UUID, revoked_at: datetime) -> None:
        self.revoked_session_ids.append(session_id)

    async def revoke_family(self, family_id: UUID, revoked_at: datetime) -> None:
        self.revoked_family_ids.append(family_id)


@dataclass
class FakeUserRepository:
    account: UserAccount | None

    async def get_by_id(self, user_id: UUID) -> UserAccount | None:
        return self.account if self.account and self.account.id == user_id else None


@dataclass
class FakeSessionIssuer:
    tokens: SessionTokens
    issued_for_family: UUID | None = None

    async def issue(
        self,
        account: UserAccount,
        *,
        access_ttl_seconds: int,
        family_id: UUID | None = None,
    ) -> SessionTokens:
        self.issued_for_family = family_id
        return self.tokens


@dataclass
class FakeUnitOfWork:
    commits: int = 0

    async def commit(self) -> None:
        self.commits += 1


def make_session(
    *,
    used_at: datetime | None = None,
    revoked_at: datetime | None = None,
    expires_at: datetime | None = None,
    replaced_by_id: UUID | None = None,
) -> RefreshSession:
    return RefreshSession(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        expires_at=expires_at or datetime.now(UTC) + timedelta(days=1),
        used_at=used_at,
        revoked_at=revoked_at,
        replaced_by_id=replaced_by_id,
    )


def make_account(user_id: UUID) -> UserAccount:
    return UserAccount(
        id=user_id,
        email="admin@example.test",
        password_hash="argon2-hash",
        role=UserRole.ADMIN,
        active=True,
    )


async def test_valid_refresh_rotates_token_within_same_family() -> None:
    stored_session = make_session()
    account = make_account(stored_session.user_id)
    replacement_id = uuid4()
    tokens = SessionTokens(
        "new-access-token",
        "new-refresh-token",
        access_expires_in=900,
        refresh_session_id=replacement_id,
    )
    sessions = FakeRefreshSessionRepository(stored_session)
    issuer = FakeSessionIssuer(tokens)
    unit_of_work = FakeUnitOfWork()
    use_case = RotateRefreshToken(
        sessions=sessions,
        users=FakeUserRepository(account),
        issuer=issuer,
        unit_of_work=unit_of_work,
    )

    result = await use_case.execute("old-refresh-token")

    assert result == tokens
    assert issuer.issued_for_family == stored_session.family_id
    assert sessions.rotations[0][0:2] == (stored_session.id, replacement_id)
    assert sessions.revoked_family_ids == []
    assert unit_of_work.commits == 0


async def test_reused_refresh_revokes_family_before_rejecting() -> None:
    family_id = uuid4()
    stored_session = RefreshSession(
        id=uuid4(),
        family_id=family_id,
        user_id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
        used_at=datetime.now(UTC) - timedelta(minutes=1),
        revoked_at=datetime.now(UTC) - timedelta(minutes=1),
        replaced_by_id=uuid4(),
    )
    sessions = FakeRefreshSessionRepository(stored_session)
    unit_of_work = FakeUnitOfWork()
    use_case = RotateRefreshToken(
        sessions=sessions,
        users=FakeUserRepository(make_account(stored_session.user_id)),
        issuer=FakeSessionIssuer(SessionTokens("a", "r", 900)),
        unit_of_work=unit_of_work,
    )

    with pytest.raises(UnauthorizedException, match="Refresh token inválido"):
        await use_case.execute("old-refresh-token")

    assert sessions.revoked_family_ids == [family_id]
    assert unit_of_work.commits == 1


async def test_expired_refresh_is_revoked_and_rejected() -> None:
    stored_session = make_session(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    sessions = FakeRefreshSessionRepository(stored_session)
    unit_of_work = FakeUnitOfWork()
    use_case = RotateRefreshToken(
        sessions=sessions,
        users=FakeUserRepository(make_account(stored_session.user_id)),
        issuer=FakeSessionIssuer(SessionTokens("a", "r", 900)),
        unit_of_work=unit_of_work,
    )

    with pytest.raises(UnauthorizedException, match="Refresh token inválido"):
        await use_case.execute("old-refresh-token")

    assert sessions.revoked_session_ids == [stored_session.id]
    assert unit_of_work.commits == 1
