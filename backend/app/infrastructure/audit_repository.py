from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import AuditEvent, AuditRecord
from app.infrastructure.models import AuditModel


class SQLAlchemyAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_event(self, record: AuditRecord) -> AuditEvent:
        model = AuditModel(
            id=uuid4(),
            actor_id=record.actor_id,
            resource=record.resource,
            resource_id=record.resource_id,
            action=record.action,
            church_id=record.church_id,
            previous_values=record.previous_values,
            new_values=record.new_values,
            reason=record.reason,
            created_at=record.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_event(model)

    async def list_events(
        self,
        *,
        church_id: UUID | None,
        offset: int,
        limit: int,
    ) -> list[AuditEvent]:
        statement = select(AuditModel)
        if church_id is not None:
            statement = statement.where(AuditModel.church_id == church_id)
        statement = statement.order_by(AuditModel.created_at.desc(), AuditModel.id.desc())
        result = await self._session.scalars(statement.offset(offset).limit(limit))
        return [self._to_event(row) for row in result.all()]

    @staticmethod
    def _to_event(model: AuditModel) -> AuditEvent:
        return AuditEvent(
            id=model.id,
            actor_id=model.actor_id,
            resource=model.resource,
            resource_id=model.resource_id,
            action=model.action,
            church_id=model.church_id,
            previous_values=model.previous_values,
            new_values=model.new_values,
            reason=model.reason,
            created_at=model.created_at,
        )