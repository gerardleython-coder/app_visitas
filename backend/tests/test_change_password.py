from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from app.application.change_password import ChangePassword
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import UnauthorizedException


@dataclass
class FakeUserRepository:
    accounts: dict[UUID, UserAccount]
    updated_password_hashes: dict[UUID, str] = field(default_factory=dict)

    async def get_by_id(self, user_id: UUID) -> UserAccount | None:
        return self.accounts.get(user_id)

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        self.updated_password_hashes[user_id] = password_hash


@dataclass
class FakePasswordService:
    current_password: str
    hash_calls: list[str] = field(default_factory=list)

    def verify(self, password: str, password_hash: str | None) -> bool:
        return password == self.current_password and password_hash == "existing-hash"

    def hash(self, password: str) -> str:
        self.hash_calls.append(password)
        return f"new-hash-{password}"


@dataclass
class FakeRefreshSessions:
    revoked_user_ids: list[UUID] = field(default_factory=list)

    async def revoke_for_user(self, user_id: UUID, revoked_at) -> None:
        self.revoked_user_ids.append(user_id)


def account(*, active: bool = True, role: UserRole = UserRole.ADMIN) -> UserAccount:
    return UserAccount(
        id=uuid4(),
        email="operator@example.test",
        password_hash="existing-hash",
        role=role,
        active=active,
    )


async def test_change_password_updates_hash_and_revokes_all_refresh_sessions() -> None:
    actor = account()
    users = FakeUserRepository({actor.id: actor})
    passwords = FakePasswordService("current-password")
    sessions = FakeRefreshSessions()
    use_case = ChangePassword(users, passwords, sessions)

    await use_case.execute(actor, "current-password", "replacement-password")

    assert users.updated_password_hashes == {actor.id: "new-hash-replacement-password"}
    assert passwords.hash_calls == ["replacement-password"]
    assert sessions.revoked_user_ids == [actor.id]


async def test_change_password_rejects_wrong_current_password_without_mutations() -> None:
    actor = account()
    users = FakeUserRepository({actor.id: actor})
    passwords = FakePasswordService("current-password")
    sessions = FakeRefreshSessions()
    use_case = ChangePassword(users, passwords, sessions)

    with pytest.raises(UnauthorizedException):
        await use_case.execute(actor, "wrong-password", "replacement-password")

    assert users.updated_password_hashes == {}
    assert passwords.hash_calls == []
    assert sessions.revoked_user_ids == []


@pytest.mark.parametrize(
    "actor",
    [
        account(active=False),
        account(role=UserRole.HERMANO),
    ],
)
async def test_change_password_rejects_inactive_or_non_operational_account(
    actor: UserAccount,
) -> None:
    users = FakeUserRepository({actor.id: actor})
    passwords = FakePasswordService("current-password")
    sessions = FakeRefreshSessions()
    use_case = ChangePassword(users, passwords, sessions)

    with pytest.raises(UnauthorizedException):
        await use_case.execute(actor, "current-password", "replacement-password")

    assert users.updated_password_hashes == {}
    assert sessions.revoked_user_ids == []