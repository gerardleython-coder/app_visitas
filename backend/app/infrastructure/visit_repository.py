from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.visit import Visit, VisitHistoryEntry, VisitStatus, VisitType
from app.infrastructure.models import UserModel, VisitHistoryModel, VisitModel
from app.infrastructure.visit_factory import VisitFactory


class SQLAlchemyVisitRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_visits(
        self,
        *,
        church_id: UUID | None = None,
        leader_id: UUID | None = None,
        brother_id: UUID | None = None,
    ) -> list[Visit]:
        statement = select(VisitModel, UserModel.church_id).join(
            UserModel,
            UserModel.id == VisitModel.brother_id,
        )
        if church_id is not None:
            statement = statement.where(UserModel.church_id == church_id)
        if leader_id is not None:
            statement = statement.where(VisitModel.leader_id == leader_id)
        if brother_id is not None:
            statement = statement.where(VisitModel.brother_id == brother_id)
        statement = statement.order_by(VisitModel.scheduled_at.desc(), VisitModel.id)
        rows = (await self._session.execute(statement)).all()
        return [VisitFactory.from_model(model, model_church_id) for model, model_church_id in rows]

    async def get_visit(self, visit_id: UUID) -> Visit | None:
        row = await self._session.execute(
            select(VisitModel, UserModel.church_id)
            .join(UserModel, UserModel.id == VisitModel.brother_id)
            .where(VisitModel.id == visit_id)
        )
        result = row.one_or_none()
        if result is None:
            return None
        model, church_id = result
        return VisitFactory.from_model(model, church_id)

    async def create_visit(
        self,
        *,
        brother_id: UUID,
        leader_id: UUID,
        created_by_id: UUID,
        visit_type: VisitType,
        scheduled_at: datetime,
        duration_minutes: int,
        location: str,
        observations: str,
        created_at: datetime,
    ) -> Visit:
        model = VisitModel(
            brother_id=brother_id,
            leader_id=leader_id,
            created_by_id=created_by_id,
            visit_type=visit_type.value,
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            location=location,
            observations=observations,
            status=VisitStatus.PROGRAMADA.value,
            created_at=created_at,
            updated_at=created_at,
        )
        self._session.add(model)
        await self._session.flush()
        self._session.add(
            VisitHistoryModel(
                visit_id=model.id,
                actor_id=created_by_id,
                action="CREADA",
                new_status=VisitStatus.PROGRAMADA.value,
                new_scheduled_at=scheduled_at,
                new_values={
                    "visit_type": visit_type.value,
                    "duration_minutes": duration_minutes,
                    "location": location,
                    "observations": observations,
                    "brother_id": str(brother_id),
                    "leader_id": str(leader_id),
                },
            )
        )
        await self._session.flush()
        brother = await self._session.get(UserModel, brother_id)
        if brother is None or brother.church_id is None:
            raise RuntimeError("El hermano asociado a la visita dejó de existir")
        return VisitFactory.from_model(model, brother.church_id)

    async def update_visit(
        self,
        visit_id: UUID,
        *,
        changes: Mapping[str, object],
        actor_id: UUID,
        action: str,
        occurred_at: datetime,
        new_status: VisitStatus | None = None,
        completed_at: datetime | None = None,
        cancellation_reason: str | None = None,
    ) -> Visit | None:
        model = await self._session.scalar(
            select(VisitModel).where(VisitModel.id == visit_id).with_for_update()
        )
        if model is None:
            return None

        previous_status = VisitStatus(model.status)
        previous_scheduled_at = model.scheduled_at
        previous_values = {
            field: self._json_value(getattr(model, field))
            for field in changes
        }
        for field, value in changes.items():
            if field == "visit_type" and isinstance(value, VisitType):
                value = value.value
            setattr(model, field, value)
        if new_status is not None:
            model.status = new_status.value
        if completed_at is not None:
            model.completed_at = completed_at
        if cancellation_reason is not None:
            model.cancellation_reason = cancellation_reason
        model.updated_at = occurred_at

        new_values = {
            field: self._json_value(getattr(model, field))
            for field in changes
        }
        if cancellation_reason is not None:
            new_values["cancellation_reason"] = cancellation_reason
        await self._session.flush()
        self._session.add(
            VisitHistoryModel(
                visit_id=model.id,
                actor_id=actor_id,
                action=action,
                previous_status=previous_status.value,
                new_status=model.status,
                previous_scheduled_at=previous_scheduled_at,
                new_scheduled_at=model.scheduled_at,
                previous_values=previous_values or None,
                new_values=new_values or None,
                reason=cancellation_reason,
                created_at=occurred_at,
            )
        )
        await self._session.flush()
        brother = await self._session.get(UserModel, model.brother_id)
        if brother is None or brother.church_id is None:
            raise RuntimeError("El hermano asociado a la visita dejó de existir")
        return VisitFactory.from_model(model, brother.church_id)

    async def list_history(self, visit_id: UUID) -> list[VisitHistoryEntry]:
        result = await self._session.scalars(
            select(VisitHistoryModel)
            .where(VisitHistoryModel.visit_id == visit_id)
            .order_by(VisitHistoryModel.created_at, VisitHistoryModel.id)
        )
        return [VisitFactory.history_from_model(row) for row in result.all()]

    @staticmethod
    def _json_value(value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, VisitType | VisitStatus):
            return value.value
        return value