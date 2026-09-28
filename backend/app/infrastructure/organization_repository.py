from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication import UserAccount, UserRole
from app.domain.organization import Church
from app.infrastructure.models import ChurchModel, UserModel


class SQLAlchemyChurchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, church_id: UUID) -> Church | None:
        church = await self._session.scalar(
            select(ChurchModel).where(ChurchModel.id == church_id)
        )
        if church is None:
            return None

        return Church(id=church.id, district_id=church.district_id, active=church.active)


class SQLAlchemyOperatorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_operator(
        self,
        *,
        name: str,
        surname: str,
        email: str,
        password_hash: str,
        role: UserRole,
        district_id: UUID,
        church_id: UUID,
    ) -> UserAccount:
        user = UserModel(
            name=name,
            surname=surname,
            email=email,
            password_hash=password_hash,
            role=role,
            district_id=district_id,
            church_id=church_id,
            active=True,
        )
        self._session.add(user)
        await self._session.flush()

        return UserAccount(
            id=user.id,
            email=email,
            password_hash=password_hash,
            role=role,
            active=True,
        )