from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import UnauthorizedException


@dataclass(frozen=True, slots=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_session_id: UUID | None = None


class UserRepository(Protocol):
    async def get_by_email(self, email: str) -> UserAccount | None: ...


class PasswordVerifier(Protocol):
    def verify(self, password: str, password_hash: str | None) -> bool: ...


class SessionIssuer(Protocol):
    async def issue(
        self,
        account: UserAccount,
        *,
        access_ttl_seconds: int,
    ) -> SessionTokens: ...


class AuthenticateUser:
    def __init__(
        self,
        users: UserRepository,
        passwords: PasswordVerifier,
        sessions: SessionIssuer,
    ) -> None:
        self._users = users
        self._passwords = passwords
        self._sessions = sessions

    async def execute(self, email: str, password: str) -> SessionTokens:
        account = await self._users.get_by_email(email)
        password_hash = (
            account.password_hash
            if account is not None and account.role is not UserRole.HERMANO
            else None
        )
        password_is_valid = self._passwords.verify(password, password_hash)

        if (
            account is None
            or not account.active
            or account.role is UserRole.HERMANO
            or not password_is_valid
        ):
            raise UnauthorizedException("Credenciales inválidas")

        return await self._sessions.issue(account, access_ttl_seconds=900)