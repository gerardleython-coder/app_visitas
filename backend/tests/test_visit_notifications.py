import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.notification import VisitNotification
from app.domain.visit import Visit, VisitStatus, VisitType
from app.domain.authentication import UserRole
from app.infrastructure.database import Base
from app.infrastructure.email_service import SMTPEmailSender, SMTPSettings
from app.infrastructure.models import (
    ChurchModel,
    DistrictModel,
    NotificationOutboxModel,
    UserModel,
    VisitModel,
)
from app.infrastructure.visit_notification_dispatcher import VisitNotificationDispatcher
from app.infrastructure.visit_notification_queue import SQLAlchemyVisitNotificationQueue
from app.infrastructure.visit_notification_worker import VisitNotificationWorker
from app.infrastructure import visit_notification_worker


@dataclass
class FakeEmailSender:
    failures_remaining: int = 0
    sent: list[VisitNotification] = field(default_factory=list)

    async def send_visit_created(self, notification: VisitNotification) -> None:
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise ConnectionError("mail transport unavailable")
        self.sent.append(notification)


async def seed_visit(session) -> tuple[Visit, str, str]:
    district_id = uuid4()
    church_id = uuid4()
    admin_id = uuid4()
    leader_id = uuid4()
    pastor_id = uuid4()
    brother_id = uuid4()
    visit_id = uuid4()
    leader_email = f"leader-{uuid4().hex}@example.test"
    pastor_email = f"pastor-{uuid4().hex}@example.test"
    scheduled_at = datetime.now(UTC) + timedelta(days=1)
    session.add(DistrictModel(id=district_id, name=f"notification-{uuid4().hex}"))
    await session.flush()
    session.add(ChurchModel(id=church_id, district_id=district_id, name=f"church-{uuid4().hex}"))
    await session.flush()
    session.add_all(
        [
            UserModel(
                id=admin_id,
                name="Notification",
                surname="Admin",
                email=f"admin-{uuid4().hex}@example.test",
                password_hash="test-hash",
                role=UserRole.ADMIN,
                active=True,
            ),
            UserModel(
                id=leader_id,
                district_id=district_id,
                church_id=church_id,
                name="Leader",
                surname="Notification",
                email=leader_email,
                password_hash="test-hash",
                role=UserRole.LIDER,
                active=True,
            ),
            UserModel(
                id=pastor_id,
                district_id=district_id,
                church_id=church_id,
                name="Pastor",
                surname="Principal",
                email=pastor_email,
                password_hash="test-hash",
                role=UserRole.PASTOR,
                active=True,
                is_primary_pastor=True,
            ),
            UserModel(
                id=brother_id,
                district_id=district_id,
                church_id=church_id,
                leader_id=leader_id,
                name="Hermano",
                surname="Notification",
                phone="3000000000",
                address="Test address",
                role=UserRole.HERMANO,
                active=True,
            ),
        ]
    )
    await session.flush()
    session.add(
        VisitModel(
            id=visit_id,
            brother_id=brother_id,
            leader_id=leader_id,
            created_by_id=admin_id,
            visit_type=VisitType.CUIDADO_PASTORAL.value,
            scheduled_at=scheduled_at,
            duration_minutes=45,
            location="Church",
            observations="Follow up",
            status=VisitStatus.PROGRAMADA.value,
        )
    )
    await session.flush()
    return (
        Visit(
            id=visit_id,
            brother_id=brother_id,
            leader_id=leader_id,
            church_id=church_id,
            created_by_id=admin_id,
            visit_type=VisitType.CUIDADO_PASTORAL,
            scheduled_at=scheduled_at,
            completed_at=None,
            duration_minutes=45,
            location="Church",
            observations="Follow up",
            status=VisitStatus.PROGRAMADA,
            cancellation_reason=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        leader_email,
        pastor_email,
    )


async def test_notification_queue_targets_leader_and_primary_pastor(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'notifications.db'}"
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            visit, leader_email, pastor_email = await seed_visit(session)
            await SQLAlchemyVisitNotificationQueue(session).enqueue_visit_created(visit)
            await session.commit()
            records = list(
                (
                    await session.scalars(
                        select(NotificationOutboxModel).where(
                            NotificationOutboxModel.visit_id == visit.id
                        )
                    )
                ).all()
            )

        assert {record.recipient_email for record in records} == {leader_email, pastor_email}
        assert len(records) == 2
        assert all(record.status == "PENDIENTE" for record in records)
    finally:
        await engine.dispose()


async def test_failed_delivery_is_recorded_pending_and_can_be_retried(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'notification-retry.db'}"
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            visit, _, _ = await seed_visit(session)
            queue = SQLAlchemyVisitNotificationQueue(session)
            await queue.enqueue_visit_created(visit)
            await session.commit()
            record_id = await session.scalar(
                select(NotificationOutboxModel.id).where(
                    NotificationOutboxModel.visit_id == visit.id
                )
            )

        sender = FakeEmailSender(failures_remaining=2)
        dispatcher = VisitNotificationDispatcher(database_url, sender)
        await dispatcher.process_pending()

        async with session_factory() as session:
            failed = await session.get(NotificationOutboxModel, record_id)
            assert failed is not None
            assert failed.status == "PENDIENTE"
            assert failed.attempt_count == 1
            assert failed.last_error == "ConnectionError"
            await session.execute(
                update(NotificationOutboxModel)
                .where(NotificationOutboxModel.id == record_id)
                .values(next_attempt_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await session.commit()

        await dispatcher.process_pending()

        async with session_factory() as session:
            sent = await session.get(NotificationOutboxModel, record_id)
            assert sent is not None
            assert sent.status == "ENVIADA"
            assert sent.attempt_count == 2
            assert sent.last_error is None
            assert len(sender.sent) == 1
    finally:
        await engine.dispose()


async def test_smtp_sender_uses_tls_and_sends_visit_details(monkeypatch) -> None:
    class FakeSMTP:
        def __init__(self, host, port, timeout) -> None:
            self.connection = (host, port, timeout)
            self.message = None
            self.tls_started = False

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def ehlo(self) -> None:
            return None

        def starttls(self, *, context) -> None:
            self.tls_started = context is not None

        def send_message(self, message) -> None:
            self.message = message

    smtp_client = FakeSMTP("smtp.example.test", 587, 10)
    monkeypatch.setattr(
        "app.infrastructure.email_service.smtplib.SMTP",
        lambda *args, **kwargs: smtp_client,
    )
    sender = SMTPEmailSender(
        SMTPSettings(
            _env_file=None,
            smtp_host="smtp.example.test",
            smtp_port=587,
            smtp_use_tls=True,
            emails_from_email="no-reply@example.test",
        )
    )

    await sender.send_visit_created(
        VisitNotification(
            recipient_email="leader@example.test",
            brother_name="Hermano Test",
            visit_type=VisitType.CUIDADO_PASTORAL,
            scheduled_at=datetime.now(UTC) + timedelta(days=1),
            duration_minutes=45,
            location="Iglesia",
        )
    )

    assert smtp_client.connection == ("smtp.example.test", 587, 10)
    assert smtp_client.tls_started is True
    assert smtp_client.message["To"] == "leader@example.test"
    assert "Hermano Test" in smtp_client.message.get_content()
    assert "45 minutos" in smtp_client.message.get_content()


async def test_smtp_sender_rejects_missing_configuration() -> None:
    sender = SMTPEmailSender(SMTPSettings(_env_file=None))
    notification = VisitNotification(
        recipient_email="leader@example.test",
        brother_name="Hermano Test",
        visit_type=VisitType.CUIDADO_PASTORAL,
        scheduled_at=datetime.now(UTC) + timedelta(days=1),
        duration_minutes=45,
        location="Iglesia",
    )

    with pytest.raises(RuntimeError, match="SMTP no está configurado"):
        await sender.send_visit_created(notification)


async def test_notification_worker_polls_until_stopped() -> None:
    stop_event = asyncio.Event()

    class FakeDispatcher:
        calls = 0

        async def process_pending(self) -> None:
            self.calls += 1
            stop_event.set()

    dispatcher = FakeDispatcher()
    worker = VisitNotificationWorker(dispatcher, poll_interval_seconds=0)

    await worker.run(stop_event)

    assert dispatcher.calls == 1


async def test_notification_worker_continues_after_poll_failure(monkeypatch) -> None:
    stop_event = asyncio.Event()
    logged_errors = []
    monkeypatch.setattr(
        visit_notification_worker.logger,
        "error",
        lambda *args, **kwargs: logged_errors.append(kwargs),
    )

    class FailingOnceDispatcher:
        calls = 0

        async def process_pending(self) -> None:
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("database unavailable")
            stop_event.set()

    dispatcher = FailingOnceDispatcher()
    worker = VisitNotificationWorker(dispatcher, poll_interval_seconds=0)

    await worker.run(stop_event)

    assert dispatcher.calls == 2
    assert logged_errors == [{"extra": {"error_type": "ConnectionError"}}]