from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from app.application.authenticate_user import SessionTokens
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import UnauthorizedException
from app.domain.session import RefreshSession


class RefreshSessionRepository(Protocol):
    async def get_by_hash_for_update(self, token_hash: str) -> RefreshSession | None: ...

    async def mark_rotated(
        self,
        session_id: UUID,
        replacement_id: UUID,
        used_at: datetime,
    ) -> None: ...

    async def revoke(self, session_id: UUID, revoked_at: datetime) -> None: ...

    async def revoke_family(self, family_id: UUID, revoked_at: datetime) -> None: ...


class UserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> UserAccount | None: ...


class SessionIssuer(Protocol):
    async def issue(
        self,
        account: UserAccount,
        *,
        access_ttl_seconds: int,
        family_id: UUID | None = None,
    ) -> SessionTokens: ...


class UnitOfWork(Protocol):
    async def commit(self) -> None: ...


class RotateRefreshToken:
    def __init__(
        self,
        sessions: RefreshSessionRepository,
        users: UserRepository,
        issuer: SessionIssuer,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._sessions = sessions
        self._users = users
        self._issuer = issuer
        self._unit_of_work = unit_of_work

    async def execute(self, refresh_token: str) -> SessionTokens:
        token_hash = sha256(refresh_token.encode("utf-8")).hexdigest()
        session = await self._sessions.get_by_hash_for_update(token_hash)
        if session is None:
            raise UnauthorizedException("Refresh token inválido")

        now = datetime.now(UTC)
        if session.used_at is not None or session.replaced_by_id is not None:
            await self._sessions.revoke_family(session.family_id, now)
            await self._unit_of_work.commit()
            raise UnauthorizedException("Refresh token inválido")

        if session.revoked_at is not None:
            raise UnauthorizedException("Refresh token inválido")

        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= now:
            await self._sessions.revoke(session.id, now)
            await self._unit_of_work.commit()
            raise UnauthorizedException("Refresh token inválido")

        account = await self._users.get_by_id(session.user_id)
        if (
            account is None
            or not account.active
            or account.role is UserRole.HERMANO
        ):
            await self._sessions.revoke_family(session.family_id, now)
            await self._unit_of_work.commit()
            raise UnauthorizedException("Refresh token inválido")

        tokens = await self._issuer.issue(
            account,
            access_ttl_seconds=900,
            family_id=session.family_id,
        )
        if tokens.refresh_session_id is None:
            raise RuntimeError("El emisor debe devolver el id de la nueva sesión refresh")

        await self._sessions.mark_rotated(
            session.id,
            tokens.refresh_session_id,
            now,
        )
        return tokens