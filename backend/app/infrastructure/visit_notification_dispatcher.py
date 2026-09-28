import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.visit_notifications import VisitEmailSender
from app.domain.notification import VisitNotification
from app.domain.visit import VisitType
from app.infrastructure.database import create_database_engine, create_session_factory
from app.infrastructure.models import NotificationOutboxModel, UserModel, VisitModel


logger = logging.getLogger(__name__)


class VisitNotificationDispatcher:
    def __init__(
        self,
        database_url: str | None,
        sender: VisitEmailSender,
    ) -> None:
        self._database_url = database_url
        self._sender = sender

    async def process_pending(self) -> None:
        engine = create_database_engine(self._database_url)
        session_factory = create_session_factory(engine)
        try:
            deliveries = await self._claim_pending(session_factory)
            for notification_id, notification, attempt_count in deliveries:
                error_type: str | None = None
                try:
                    await self._sender.send_visit_created(notification)
                except Exception as error:
                    error_type = type(error).__name__
                    logger.warning(
                        "Visit notification delivery failed",
                        extra={"notification_id": str(notification_id), "error_type": error_type},
                    )
                await self._complete_delivery(
                    session_factory,
                    notification_id,
                    attempt_count,
                    error_type,
                )
        finally:
            await engine.dispose()

    async def _claim_pending(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> list[tuple[UUID, VisitNotification, int]]:
        now = datetime.now(UTC)
        retryable = and_(
            NotificationOutboxModel.status == "PENDIENTE",
            NotificationOutboxModel.next_attempt_at <= now,
        )
        abandoned = and_(
            NotificationOutboxModel.status == "PROCESANDO",
            NotificationOutboxModel.locked_until <= now,
        )
        async with session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(NotificationOutboxModel, VisitModel, UserModel)
                    .join(VisitModel, VisitModel.id == NotificationOutboxModel.visit_id)
                    .join(UserModel, UserModel.id == VisitModel.brother_id)
                    .where(or_(retryable, abandoned))
                    .order_by(NotificationOutboxModel.created_at, NotificationOutboxModel.id)
                    .limit(100)
                    .with_for_update(of=NotificationOutboxModel, skip_locked=True)
                )
                deliveries: list[tuple[UUID, VisitNotification, int]] = []
                for outbox, visit, brother in result.all():
                    outbox.status = "PROCESANDO"
                    outbox.attempt_count += 1
                    outbox.locked_until = now + timedelta(minutes=2)
                    deliveries.append(
                        (
                            outbox.id,
                            VisitNotification(
                                recipient_email=outbox.recipient_email,
                                brother_name=f"{brother.name} {brother.surname}",
                                visit_type=VisitType(visit.visit_type),
                                scheduled_at=visit.scheduled_at,
                                duration_minutes=visit.duration_minutes,
                                location=visit.location,
                            ),
                            outbox.attempt_count,
                        )
                    )
                return deliveries

    async def _complete_delivery(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        notification_id: UUID,
        attempt_count: int,
        error_type: str | None,
    ) -> None:
        now = datetime.now(UTC)
        async with session_factory() as session:
            async with session.begin():
                outbox = await session.scalar(
                    select(NotificationOutboxModel)
                    .where(
                        NotificationOutboxModel.id == notification_id,
                        NotificationOutboxModel.status == "PROCESANDO",
                    )
                    .with_for_update()
                )
                if outbox is None:
                    return
                outbox.locked_until = None
                outbox.last_attempt_at = now
                if error_type is None:
                    outbox.status = "ENVIADA"
                    outbox.sent_at = now
                    outbox.last_error = None
                else:
                    outbox.status = "PENDIENTE"
                    outbox.last_error = error_type
                    delay_seconds = min(3600, 30 * 2 ** min(attempt_count - 1, 7))
                    outbox.next_attempt_at = now + timedelta(seconds=delay_seconds)