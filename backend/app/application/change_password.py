from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import UnauthorizedException


class UserRepository(Protocol):
    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None: ...


class PasswordService(Protocol):
    def verify(self, password: str, password_hash: str | None) -> bool: ...

    def hash(self, password: str) -> str: ...


class RefreshSessionRepository(Protocol):
    async def revoke_for_user(self, user_id: UUID, revoked_at: datetime) -> None: ...


class ChangePassword:
    def __init__(
        self,
        users: UserRepository,
        passwords: PasswordService,
        sessions: RefreshSessionRepository,
    ) -> None:
        self._users = users
        self._passwords = passwords
        self._sessions = sessions

    async def execute(
        self,
        actor: UserAccount,
        current_password: str,
        new_password: str,
    ) -> None:
        if (
            not actor.active
            or actor.role is UserRole.HERMANO
            or not self._passwords.verify(current_password, actor.password_hash)
        ):
            raise UnauthorizedException("Credenciales inválidas")

        now = datetime.now(UTC)
        await self._users.update_password_hash(
            actor.id,
            self._passwords.hash(new_password),
        )
        await self._sessions.revoke_for_user(actor.id, now)