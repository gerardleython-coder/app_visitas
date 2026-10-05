from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.visit import Visit
from app.domain.authentication import UserRole
from app.infrastructure.models import NotificationOutboxModel, UserModel


class SQLAlchemyVisitNotificationQueue:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue_visit_created(self, visit: Visit) -> None:
        leader_email = await self._session.scalar(
            select(UserModel.email).where(
                UserModel.id == visit.leader_id,
                UserModel.role == UserRole.LIDER,
                UserModel.active.is_(True),
            )
        )
        pastor_email = await self._session.scalar(
            select(UserModel.email)
            .where(
                UserModel.church_id == visit.church_id,
                UserModel.role == UserRole.PASTOR,
                UserModel.active.is_(True),
                UserModel.is_primary_pastor.is_(True),
            )
            .limit(1)
        )
        for recipient in dict.fromkeys((leader_email, pastor_email)):
            if recipient is not None:
                self._session.add(
                    NotificationOutboxModel(
                        visit_id=visit.id,
                        recipient_email=recipient,
                        notification_type="VISITA_CREADA",
                        status="PENDIENTE",
                        next_attempt_at=datetime.now(UTC),
                    )
                )
        await self._session.flush()