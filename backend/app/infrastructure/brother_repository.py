from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication import UserRole
from app.domain.brother import BrotherProfile
from app.infrastructure.brother_factory import BrotherFactory
from app.infrastructure.models import BrotherAssignmentModel, UserModel


class SQLAlchemyBrotherRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_brothers(
        self,
        *,
        church_id: UUID | None = None,
        leader_id: UUID | None = None,
    ) -> list[BrotherProfile]:
        statement = select(UserModel).where(UserModel.role == UserRole.HERMANO)
        if church_id is not None:
            statement = statement.where(UserModel.church_id == church_id)
        if leader_id is not None:
            statement = statement.where(UserModel.leader_id == leader_id)
        statement = statement.order_by(UserModel.surname, UserModel.name, UserModel.id)
        result = await self._session.scalars(statement)
        return [self._to_profile(brother) for brother in result.all()]

    async def get_brother(self, brother_id: UUID) -> BrotherProfile | None:
        brother = await self._session.scalar(
            select(UserModel).where(
                UserModel.id == brother_id,
                UserModel.role == UserRole.HERMANO,
            )
        )
        return self._to_profile(brother) if brother is not None else None

    async def create_brother(
        self,
        *,
        name: str,
        surname: str,
        phone: str,
        address: str,
        district_id: UUID,
        church_id: UUID,
        leader_id: UUID,
        assigned_by_id: UUID,
        assigned_at: datetime,
    ) -> BrotherProfile:
        brother = BrotherFactory.create_model(
            name=name,
            surname=surname,
            phone=phone,
            address=address,
            district_id=district_id,
            church_id=church_id,
            leader_id=leader_id,
        )
        self._session.add(brother)
        await self._session.flush()
        self._session.add(
            BrotherAssignmentModel(
                brother_id=brother.id,
                leader_id=leader_id,
                assigned_by_id=assigned_by_id,
                assigned_at=assigned_at,
            )
        )
        await self._session.flush()
        return self._to_profile(brother)

    async def update_brother(
        self,
        brother_id: UUID,
        changes: dict[str, object],
    ) -> BrotherProfile | None:
        brother = await self._session.scalar(
            select(UserModel)
            .where(UserModel.id == brother_id, UserModel.role == UserRole.HERMANO)
            .with_for_update()
        )
        if brother is None or not brother.active:
            return None
        for field, value in changes.items():
            setattr(brother, field, value)
        await self._session.flush()
        return self._to_profile(brother)

    async def deactivate_brother(
        self,
        brother_id: UUID,
        ended_at: datetime,
    ) -> BrotherProfile | None:
        brother = await self._session.scalar(
            select(UserModel)
            .where(UserModel.id == brother_id, UserModel.role == UserRole.HERMANO)
            .with_for_update()
        )
        if brother is None:
            return None
        if not brother.active:
            return self._to_profile(brother)
        brother.active = False
        current_assignment = await self._current_assignment(brother_id)
        if current_assignment is None:
            raise RuntimeError("El hermano no tiene una asignación vigente para cerrar")
        current_assignment.ended_at = ended_at
        await self._session.flush()
        return self._to_profile(brother)

    async def reassign_leader(
        self,
        brother_id: UUID,
        *,
        leader_id: UUID,
        assigned_by_id: UUID,
        assigned_at: datetime,
    ) -> BrotherProfile | None:
        brother = await self._session.scalar(
            select(UserModel)
            .where(UserModel.id == brother_id, UserModel.role == UserRole.HERMANO)
            .with_for_update()
        )
        if brother is None or not brother.active:
            return None
        if brother.leader_id == leader_id:
            return self._to_profile(brother)

        current_assignment = await self._current_assignment(brother_id)
        if current_assignment is None:
            raise RuntimeError("El hermano no tiene una asignación vigente para cerrar")
        current_assignment.ended_at = assigned_at
        brother.leader_id = leader_id
        await self._session.flush()
        self._session.add(
            BrotherAssignmentModel(
                brother_id=brother.id,
                leader_id=leader_id,
                assigned_by_id=assigned_by_id,
                assigned_at=assigned_at,
            )
        )
        await self._session.flush()
        return self._to_profile(brother)

    async def _current_assignment(
        self,
        brother_id: UUID,
    ) -> BrotherAssignmentModel | None:
        return await self._session.scalar(
            select(BrotherAssignmentModel)
            .where(
                BrotherAssignmentModel.brother_id == brother_id,
                BrotherAssignmentModel.ended_at.is_(None),
            )
            .with_for_update()
        )

    @staticmethod
    def _to_profile(brother: UserModel) -> BrotherProfile:
        return BrotherFactory.from_model(brother)