from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import PasswordRecoveryTokenModel


class SQLAlchemyPasswordRecoveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_token(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        self._session.add(
            PasswordRecoveryTokenModel(
                id=uuid4(),
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        await self._session.flush()

    async def consume_token(self, token_hash: str, consumed_at: datetime) -> UUID | None:
        token_record = await self._session.scalar(
            select(PasswordRecoveryTokenModel)
            .where(
                PasswordRecoveryTokenModel.token_hash == token_hash,
                PasswordRecoveryTokenModel.used_at.is_(None),
                PasswordRecoveryTokenModel.expires_at > consumed_at,
            )
            .with_for_update()
        )
        if token_record is None:
            return None
        token_record.used_at = consumed_at
        await self._session.flush()
        return token_record.user_id