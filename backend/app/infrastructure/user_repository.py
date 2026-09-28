from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.domain.authentication import UserAccount
from app.infrastructure.models import UserModel


class SQLAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> UserAccount | None:
        result = await self._session.scalar(select(UserModel).where(UserModel.email == email))
        return self._to_account(result)

    async def get_by_id(self, user_id: UUID) -> UserAccount | None:
        result = await self._session.get(UserModel, user_id)
        return self._to_account(result)

    @staticmethod
    def _to_account(result: UserModel | None) -> UserAccount | None:
        if result is None or result.email is None:
            return None

        return UserAccount(
            id=result.id,
            email=result.email,
            password_hash=result.password_hash,
            role=result.role,
            active=result.active,
        )