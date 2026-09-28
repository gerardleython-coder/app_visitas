from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authenticate_user import SessionTokens
from app.domain.authentication import UserAccount
from app.infrastructure.models import RefreshSessionModel


class SQLAlchemySessionIssuer:
    def __init__(
        self,
        session: AsyncSession,
        secret_key: str,
        refresh_ttl: timedelta = timedelta(days=30),
    ) -> None:
        self._session = session
        self._secret_key = secret_key
        self._refresh_ttl = refresh_ttl

    async def issue(
        self,
        account: UserAccount,
        *,
        access_ttl_seconds: int,
    ) -> SessionTokens:
        issued_at = datetime.now(UTC)
        access_token = jwt.encode(
            {
                "sub": str(account.id),
                "role": account.role.value,
                "token_type": "access",
                "iat": issued_at,
                "exp": issued_at + timedelta(seconds=access_ttl_seconds),
            },
            self._secret_key,
            algorithm="HS256",
        )
        refresh_token = token_urlsafe(64)
        token_hash = sha256(refresh_token.encode("utf-8")).hexdigest()
        self._session.add(
            RefreshSessionModel(
                user_id=account.id,
                token_hash=token_hash,
                expires_at=issued_at + self._refresh_ttl,
            )
        )
        await self._session.flush()

        return SessionTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_in=access_ttl_seconds,
        )