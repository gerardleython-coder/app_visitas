from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication import UserAccount
from app.infrastructure.models import UserModel


class SQLAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> UserAccount | None:
        result = await self._session.scalar(select(UserModel).where(UserModel.email == email))
        if result is None or result.email is None:
            return None

        return UserAccount(
            id=result.id,
            email=result.email,
            password_hash=result.password_hash,
            role=result.role,
            active=result.active,
        )