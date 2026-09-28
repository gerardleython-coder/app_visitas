from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.session import RefreshSession
from app.infrastructure.models import RefreshSessionModel


class SQLAlchemyRefreshSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_hash_for_update(self, token_hash: str) -> RefreshSession | None:
        model = await self._session.scalar(
            select(RefreshSessionModel)
            .where(RefreshSessionModel.token_hash == token_hash)
            .with_for_update()
        )
        if model is None:
            return None

        return RefreshSession(
            id=model.id,
            family_id=model.family_id,
            user_id=model.user_id,
            expires_at=model.expires_at,
            used_at=model.used_at,
            revoked_at=model.revoked_at,
            replaced_by_id=model.replaced_by_id,
        )

    async def mark_rotated(
        self,
        session_id: UUID,
        replacement_id: UUID,
        used_at: datetime,
    ) -> None:
        model = await self._session.get(RefreshSessionModel, session_id)
        if model is None:
            raise RuntimeError("La sesión refresh dejó de existir durante la rotación")

        model.used_at = used_at
        model.revoked_at = used_at
        model.replaced_by_id = replacement_id
        await self._session.flush()

    async def revoke(self, session_id: UUID, revoked_at: datetime) -> None:
        await self._session.execute(
            update(RefreshSessionModel)
            .where(
                RefreshSessionModel.id == session_id,
                RefreshSessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    async def revoke_family(self, family_id: UUID, revoked_at: datetime) -> None:
        await self._session.execute(
            update(RefreshSessionModel)
            .where(
                RefreshSessionModel.family_id == family_id,
                RefreshSessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )

    async def revoke_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        await self._session.execute(
            update(RefreshSessionModel)
            .where(
                RefreshSessionModel.user_id == user_id,
                RefreshSessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )