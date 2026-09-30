from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication import UserAccount, UserRole
from app.domain.organization import Church
from app.domain.operator import OperatorProfile
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

        return Church(
            id=church.id,
            district_id=church.district_id,
            active=church.active,
            name=church.name,
            address=church.address,
        )


class SQLAlchemyOperatorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_bootstrap(self) -> None:
        if self._session.get_bind().dialect.name == "postgresql":
            await self._session.execute(text("SELECT pg_advisory_xact_lock(1547311916, 441811)"))

    async def count_administrators(self) -> int:
        count = await self._session.scalar(
            select(func.count(UserModel.id)).where(UserModel.role == UserRole.ADMIN)
        )
        return int(count or 0)

    async def create_administrator(
        self,
        *,
        name: str,
        surname: str,
        email: str,
        password_hash: str,
    ) -> UserAccount:
        user = UserModel(
            name=name,
            surname=surname,
            email=email,
            password_hash=password_hash,
            role=UserRole.ADMIN,
            active=True,
        )
        self._session.add(user)
        await self._session.flush()
        return UserAccount(
            id=user.id,
            email=email,
            password_hash=password_hash,
            role=UserRole.ADMIN,
            active=True,
        )

    async def list_administrators(self) -> list[OperatorProfile]:
        result = await self._session.scalars(
            select(UserModel)
            .where(UserModel.role == UserRole.ADMIN)
            .order_by(UserModel.surname, UserModel.name, UserModel.id)
        )
        return [self._to_operator(user) for user in result.all()]

    async def lock_administrators(self) -> None:
        await self._session.scalars(
            select(UserModel.id)
            .where(UserModel.role == UserRole.ADMIN)
            .order_by(UserModel.id)
            .with_for_update()
        )

    async def has_active_administrator(self, *, excluding_id: UUID) -> bool:
        administrator_id = await self._session.scalar(
            select(UserModel.id)
            .where(
                UserModel.role == UserRole.ADMIN,
                UserModel.active.is_(True),
                UserModel.id != excluding_id,
            )
            .limit(1)
        )
        return administrator_id is not None

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

    async def list_operators(
        self,
        role: UserRole,
        *,
        church_id: UUID | None = None,
    ) -> list[OperatorProfile]:
        statement = select(UserModel).where(UserModel.role == role)
        if church_id is not None:
            statement = statement.where(UserModel.church_id == church_id)
        statement = statement.order_by(UserModel.surname, UserModel.name, UserModel.id)
        result = await self._session.scalars(statement)
        return [self._to_operator(user) for user in result.all() if user.email is not None]

    async def get_operator(self, operator_id: UUID) -> OperatorProfile | None:
        user = await self._session.get(UserModel, operator_id)
        return self._to_operator(user) if user is not None else None

    async def update_operator(
        self,
        operator_id: UUID,
        changes: dict[str, object],
    ) -> OperatorProfile | None:
        user = await self._session.get(UserModel, operator_id)
        if user is None:
            return None
        for field, value in changes.items():
            setattr(user, field, value)
        await self._session.flush()
        return self._to_operator(user)

    async def lock_church(self, church_id: UUID) -> bool:
        locked_id = await self._session.scalar(
            select(ChurchModel.id)
            .where(ChurchModel.id == church_id)
            .with_for_update()
        )
        return locked_id is not None

    async def has_active_primary_pastor(
        self,
        church_id: UUID,
        *,
        excluding_id: UUID,
    ) -> bool:
        pastor_id = await self._session.scalar(
            select(UserModel.id)
            .where(
                UserModel.church_id == church_id,
                UserModel.id != excluding_id,
                UserModel.role == UserRole.PASTOR,
                UserModel.active.is_(True),
                UserModel.is_primary_pastor.is_(True),
            )
            .limit(1)
        )
        return pastor_id is not None

    async def set_primary_pastor(
        self,
        church_id: UUID,
        pastor_id: UUID,
    ) -> OperatorProfile | None:
        await self._session.execute(
            update(UserModel)
            .where(
                UserModel.church_id == church_id,
                UserModel.role == UserRole.PASTOR,
                UserModel.active.is_(True),
                UserModel.is_primary_pastor.is_(True),
                UserModel.id != pastor_id,
            )
            .values(is_primary_pastor=False)
        )
        pastor = await self._session.get(UserModel, pastor_id)
        if pastor is None:
            return None
        pastor.is_primary_pastor = True
        await self._session.flush()
        return self._to_operator(pastor)

    async def deactivate_operator(self, operator_id: UUID) -> OperatorProfile | None:
        user = await self._session.get(UserModel, operator_id)
        if user is None:
            return None
        user.active = False
        user.is_primary_pastor = False
        await self._session.flush()
        return self._to_operator(user)

    @staticmethod
    def _to_operator(user: UserModel) -> OperatorProfile:
        if user.email is None:
            raise ValueError("Un operador debe tener email")
        return OperatorProfile(
            id=user.id,
            name=user.name,
            surname=user.surname,
            email=user.email,
            role=user.role,
            active=user.active,
            district_id=user.district_id,
            church_id=user.church_id,
            phone=user.phone,
            address=user.address,
            is_primary_pastor=user.is_primary_pastor,
        )