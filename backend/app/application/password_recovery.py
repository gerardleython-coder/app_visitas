from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Callable, Protocol
from uuid import UUID

from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import UnauthorizedException
from app.domain.password_recovery import PasswordResetEmail


class UserRepository(Protocol):
    async def get_by_email(self, email: str) -> UserAccount | None: ...

    async def get_by_id(self, user_id: UUID) -> UserAccount | None: ...

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None: ...


class PasswordRecoveryRepository(Protocol):
    async def create_token(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> None: ...

    async def consume_token(self, token_hash: str, consumed_at: datetime) -> UUID | None: ...


class RefreshSessionRepository(Protocol):
    async def revoke_for_user(self, user_id: UUID, revoked_at: datetime) -> None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...


class PasswordResetEmailSender(Protocol):
    async def send_password_reset(self, recovery_email: PasswordResetEmail) -> None: ...


class RequestPasswordReset:
    def __init__(
        self,
        users: UserRepository,
        recovery: PasswordRecoveryRepository,
        token_factory: Callable[[], str] = lambda: token_urlsafe(32),
    ) -> None:
        self._users = users
        self._recovery = recovery
        self._token_factory = token_factory

    async def execute(self, email: str) -> PasswordResetEmail | None:
        account = await self._users.get_by_email(email.strip())
        if (
            account is None
            or not account.active
            or account.role is UserRole.HERMANO
            or account.password_hash is None
        ):
            return None

        token = self._token_factory()
        token_hash = sha256(token.encode("utf-8")).hexdigest()
        await self._recovery.create_token(
            user_id=account.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        return PasswordResetEmail(recipient_email=account.email, token=token)


class ResetPassword:
    def __init__(
        self,
        users: UserRepository,
        recovery: PasswordRecoveryRepository,
        sessions: RefreshSessionRepository,
        passwords: PasswordHasher,
    ) -> None:
        self._users = users
        self._recovery = recovery
        self._sessions = sessions
        self._passwords = passwords

    async def execute(self, token: str, new_password: str) -> None:
        token_hash = sha256(token.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)
        user_id = await self._recovery.consume_token(token_hash, now)
        if user_id is None:
            raise UnauthorizedException("Token de recuperación inválido o expirado")

        account = await self._users.get_by_id(user_id)
        if (
            account is None
            or not account.active
            or account.role is UserRole.HERMANO
            or account.password_hash is None
        ):
            raise UnauthorizedException("Token de recuperación inválido o expirado")

        password_hash = self._passwords.hash(new_password)
        await self._users.update_password_hash(user_id, password_hash)
        await self._sessions.revoke_for_user(user_id, now)