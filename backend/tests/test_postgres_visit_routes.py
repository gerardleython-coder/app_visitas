import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import os
from secrets import token_urlsafe
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.authentication import UserRole
from app.infrastructure.database import DatabaseSettings, create_database_engine
from app.infrastructure.models import (
    ChurchModel,
    DistrictModel,
    NotificationOutboxModel,
    UserModel,
    VisitHistoryModel,
    VisitModel,
)
from app.main import app
from app.infrastructure.visit_notification_dispatcher import VisitNotificationDispatcher
from app.presentation.dependencies import get_visit_notification_dispatcher


BOGOTA = ZoneInfo("America/Bogota")

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 to run against configured PostgreSQL",
)


@dataclass
class VisitScenario:
    prefix: str
    secret_key: str
    district_id: UUID
    church_id: UUID
    other_church_id: UUID
    admin_id: UUID
    pastor_id: UUID
    other_pastor_id: UUID
    leader_id: UUID
    other_leader_id: UUID
    foreign_leader_id: UUID
    brother_id: UUID
    other_brother_id: UUID

    def headers(self, user_id: UUID, role: UserRole) -> dict[str, str]:
        issued_at = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": str(user_id),
                "role": role.value,
                "token_type": "access",
                "iat": issued_at,
                "exp": issued_at + timedelta(minutes=15),
            },
            self.secret_key,
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def visit_scenario(monkeypatch: pytest.MonkeyPatch) -> VisitScenario:
    scenario = VisitScenario(
        prefix=f"hu04-{uuid4().hex}",
        secret_key=token_urlsafe(48),
        district_id=uuid4(),
        church_id=uuid4(),
        other_church_id=uuid4(),
        admin_id=uuid4(),
        pastor_id=uuid4(),
        other_pastor_id=uuid4(),
        leader_id=uuid4(),
        other_leader_id=uuid4(),
        foreign_leader_id=uuid4(),
        brother_id=uuid4(),
        other_brother_id=uuid4(),
    )
    monkeypatch.setenv("SECRET_KEY", scenario.secret_key)

    async def prepare() -> None:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                async with session.begin():
                    session.add(DistrictModel(id=scenario.district_id, name=scenario.prefix))
                    await session.flush()
                    session.add_all(
                        [
                            ChurchModel(
                                id=scenario.church_id,
                                district_id=scenario.district_id,
                                name=f"{scenario.prefix}-church",
                            ),
                            ChurchModel(
                                id=scenario.other_church_id,
                                district_id=scenario.district_id,
                                name=f"{scenario.prefix}-other-church",
                            ),
                        ]
                    )
                    await session.flush()
                    session.add_all(
                        [
                            UserModel(
                                id=scenario.admin_id,
                                name=f"{scenario.prefix}-admin",
                                surname="Admin",
                                email=f"{scenario.prefix}-admin@example.invalid",
                                password_hash="test-only-hash",
                                role=UserRole.ADMIN,
                                active=True,
                            ),
                            UserModel(
                                id=scenario.pastor_id,
                                district_id=scenario.district_id,
                                church_id=scenario.church_id,
                                name=f"{scenario.prefix}-pastor",
                                surname="Pastor",
                                email=f"{scenario.prefix}-pastor@example.invalid",
                                password_hash="test-only-hash",
                                role=UserRole.PASTOR,
                                is_primary_pastor=True,
                                active=True,
                            ),
                            UserModel(
                                id=scenario.other_pastor_id,
                                district_id=scenario.district_id,
                                church_id=scenario.other_church_id,
                                name=f"{scenario.prefix}-other-pastor",
                                surname="Other Pastor",
                                email=f"{scenario.prefix}-other-pastor@example.invalid",
                                password_hash="test-only-hash",
                                role=UserRole.PASTOR,
                                active=True,
                            ),
                            UserModel(
                                id=scenario.leader_id,
                                district_id=scenario.district_id,
                                church_id=scenario.church_id,
                                name=f"{scenario.prefix}-leader-a",
                                surname="Leader A",
                                email=f"{scenario.prefix}-leader-a@example.invalid",
                                password_hash="test-only-hash",
                                role=UserRole.LIDER,
                                active=True,
                            ),
                            UserModel(
                                id=scenario.other_leader_id,
                                district_id=scenario.district_id,
                                church_id=scenario.church_id,
                                name=f"{scenario.prefix}-leader-b",
                                surname="Leader B",
                                email=f"{scenario.prefix}-leader-b@example.invalid",
                                password_hash="test-only-hash",
                                role=UserRole.LIDER,
                                active=True,
                            ),
                            UserModel(
                                id=scenario.foreign_leader_id,
                                district_id=scenario.district_id,
                                church_id=scenario.other_church_id,
                                name=f"{scenario.prefix}-leader-foreign",
                                surname="Foreign Leader",
                                email=f"{scenario.prefix}-leader-foreign@example.invalid",
                                password_hash="test-only-hash",
                                role=UserRole.LIDER,
                                active=True,
                            ),
                        ]
                    )
                    await session.flush()
                    session.add_all(
                        [
                            UserModel(
                                id=scenario.brother_id,
                                district_id=scenario.district_id,
                                church_id=scenario.church_id,
                                leader_id=scenario.leader_id,
                                name=f"{scenario.prefix}-brother-a",
                                surname="Brother A",
                                phone="3001112233",
                                address="Address A",
                                role=UserRole.HERMANO,
                                active=True,
                            ),
                            UserModel(
                                id=scenario.other_brother_id,
                                district_id=scenario.district_id,
                                church_id=scenario.church_id,
                                leader_id=scenario.other_leader_id,
                                name=f"{scenario.prefix}-brother-b",
                                surname="Brother B",
                                phone="3001112234",
                                address="Address B",
                                role=UserRole.HERMANO,
                                active=True,
                            ),
                        ]
                    )
        finally:
            await engine.dispose()

    asyncio.run(prepare())
    try:
        yield scenario
    finally:
        async def cleanup() -> None:
            engine = create_database_engine()
            try:
                async with engine.begin() as connection:
                    await connection.execute(
                        text("ALTER TABLE visita_historial DISABLE TRIGGER trg_proteger_historial_visita")
                    )
                    await connection.execute(
                        text("ALTER TABLE visitas DISABLE TRIGGER trg_impedir_eliminar_visita")
                    )
                    visit_ids = select(VisitModel.id).where(
                        VisitModel.brother_id.in_(
                            [scenario.brother_id, scenario.other_brother_id]
                        )
                    )
                    await connection.execute(
                        delete(NotificationOutboxModel).where(
                            NotificationOutboxModel.visit_id.in_(visit_ids)
                        )
                    )
                    await connection.execute(
                        delete(VisitHistoryModel).where(VisitHistoryModel.visit_id.in_(visit_ids))
                    )
                    await connection.execute(
                        delete(VisitModel).where(
                            VisitModel.brother_id.in_(
                                [scenario.brother_id, scenario.other_brother_id]
                            )
                        )
                    )
                    await connection.execute(
                        text("ALTER TABLE visitas ENABLE TRIGGER trg_impedir_eliminar_visita")
                    )
                    await connection.execute(
                        text("ALTER TABLE visita_historial ENABLE TRIGGER trg_proteger_historial_visita")
                    )
                    await connection.execute(
                        delete(UserModel).where(
                            UserModel.id.in_([scenario.brother_id, scenario.other_brother_id])
                        )
                    )
                    await connection.execute(
                        delete(UserModel).where(UserModel.email.like(f"{scenario.prefix}%"))
                    )
                    await connection.execute(
                        delete(ChurchModel).where(
                            ChurchModel.id.in_([scenario.church_id, scenario.other_church_id])
                        )
                    )
                    await connection.execute(
                        delete(DistrictModel).where(DistrictModel.id == scenario.district_id)
                    )
            finally:
                await engine.dispose()

        asyncio.run(cleanup())


def visit_request(brother_id: UUID, scheduled_at: datetime) -> dict[str, object]:
    return {
        "brother_id": str(brother_id),
        "visit_type": "CUIDADO_PASTORAL",
        "scheduled_at": scheduled_at.isoformat(),
        "duration_minutes": 45,
        "location": "Domicilio",
        "observations": "Seguimiento pastoral",
    }


def test_visits_create_duplicate_past_date_and_scope(visit_scenario: VisitScenario) -> None:
    scenario = visit_scenario
    admin_headers = scenario.headers(scenario.admin_id, UserRole.ADMIN)
    pastor_headers = scenario.headers(scenario.pastor_id, UserRole.PASTOR)
    other_pastor_headers = scenario.headers(scenario.other_pastor_id, UserRole.PASTOR)
    leader_headers = scenario.headers(scenario.leader_id, UserRole.LIDER)
    other_leader_headers = scenario.headers(scenario.other_leader_id, UserRole.LIDER)
    scheduled_at = datetime.now(BOGOTA) + timedelta(hours=2)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/visitas",
            headers=admin_headers,
            json=visit_request(scenario.brother_id, scheduled_at),
        )
        assert created.status_code == 201
        visit = created.json()
        assert visit["status"] == "PROGRAMADA"
        assert visit["leader_id"] == str(scenario.leader_id)
        assert visit["created_by"] == str(scenario.admin_id)

        pastor_visit = client.post(
            "/api/v1/visitas",
            headers=pastor_headers,
            json=visit_request(
                scenario.brother_id,
                scheduled_at + timedelta(hours=1),
            ),
        )
        assert pastor_visit.status_code == 201

        leader_visit = client.post(
            "/api/v1/visitas",
            headers=leader_headers,
            json=visit_request(
                scenario.brother_id,
                scheduled_at + timedelta(hours=2),
            ),
        )
        assert leader_visit.status_code == 201

        duplicate = client.post(
            "/api/v1/visitas",
            headers=admin_headers,
            json=visit_request(scenario.brother_id, scheduled_at),
        )
        assert duplicate.status_code == 409

        past_visit = client.post(
            "/api/v1/visitas",
            headers=admin_headers,
            json=visit_request(
                scenario.brother_id,
                datetime.now(BOGOTA) - timedelta(minutes=1),
            ),
        )
        assert past_visit.status_code == 422

        admin_list = client.get("/api/v1/visitas", headers=admin_headers)
        assert admin_list.status_code == 200
        assert {item["id"] for item in admin_list.json()} == {
            visit["id"],
            pastor_visit.json()["id"],
            leader_visit.json()["id"],
        }
        assert client.get("/api/v1/visitas", headers=pastor_headers).status_code == 200
        assert client.get("/api/v1/visitas", headers=other_pastor_headers).json() == []
        assert client.get("/api/v1/visitas", headers=leader_headers).status_code == 200
        assert client.get("/api/v1/visitas", headers=other_leader_headers).json() == []
        assert client.get(
            f"/api/v1/visitas/{visit['id']}",
            headers=other_leader_headers,
        ).status_code == 404
        assert client.post(
            "/api/v1/visitas",
            headers=leader_headers,
            json=visit_request(
                scenario.other_brother_id,
                datetime.now(BOGOTA) + timedelta(hours=3),
            ),
        ).status_code == 404


def test_visit_transitions_and_audit_history(visit_scenario: VisitScenario) -> None:
    scenario = visit_scenario
    admin_headers = scenario.headers(scenario.admin_id, UserRole.ADMIN)
    pastor_headers = scenario.headers(scenario.pastor_id, UserRole.PASTOR)
    leader_headers = scenario.headers(scenario.leader_id, UserRole.LIDER)

    with TestClient(app) as client:
        scheduled_at = datetime.now(BOGOTA) + timedelta(hours=2)
        created = client.post(
            "/api/v1/visitas",
            headers=admin_headers,
            json=visit_request(scenario.brother_id, scheduled_at),
        )
        assert created.status_code == 201
        visit_id = UUID(created.json()["id"])

        rescheduled_at = scheduled_at + timedelta(days=1)
        rescheduled = client.patch(
            f"/api/v1/visitas/{visit_id}",
            headers=pastor_headers,
            json={"scheduled_at": rescheduled_at.isoformat()},
        )
        assert rescheduled.status_code == 200
        assert rescheduled.json()["status"] == "PROGRAMADA"

        past_reschedule = client.patch(
            f"/api/v1/visitas/{visit_id}",
            headers=pastor_headers,
            json={
                "scheduled_at": (
                    datetime.now(BOGOTA) - timedelta(minutes=1)
                ).isoformat()
            },
        )
        assert past_reschedule.status_code == 422

        future_completion = client.patch(
            f"/api/v1/visitas/{visit_id}",
            headers=pastor_headers,
            json={"status": "COMPLETADA"},
        )
        assert future_completion.status_code == 422

        async def move_visit_into_past() -> None:
            engine = create_database_engine()
            try:
                session_factory = async_sessionmaker(engine, expire_on_commit=False)
                async with session_factory() as session:
                    async with session.begin():
                        model = await session.get(VisitModel, visit_id)
                        assert model is not None
                        model.scheduled_at = datetime.now(UTC) - timedelta(minutes=1)
            finally:
                await engine.dispose()

        asyncio.run(move_visit_into_past())
        completed = client.patch(
            f"/api/v1/visitas/{visit_id}",
            headers=pastor_headers,
            json={"status": "COMPLETADA"},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "COMPLETADA"

        assert client.patch(
            f"/api/v1/visitas/{visit_id}",
            headers=pastor_headers,
            json={"observations": "No permitido"},
        ).status_code == 403
        assert client.patch(
            f"/api/v1/visitas/{visit_id}",
            headers=leader_headers,
            json={"observations": "No permitido"},
        ).status_code == 403

        admin_edit = client.patch(
            f"/api/v1/visitas/{visit_id}",
            headers=admin_headers,
            json={"observations": "Actualización administrativa"},
        )
        assert admin_edit.status_code == 200
        assert admin_edit.json()["observations"] == "Actualización administrativa"

        history = client.get(
            f"/api/v1/visitas/{visit_id}/history",
            headers=admin_headers,
        )
        assert history.status_code == 200
        assert [entry["action"] for entry in history.json()] == [
            "CREADA",
            "REPROGRAMADA",
            "COMPLETADA",
            "MODIFICADA",
        ]
        assert history.json()[1]["previous_scheduled_at"] is not None
        assert history.json()[1]["new_scheduled_at"] is not None
        assert history.json()[2]["actor_id"] == str(scenario.pastor_id)
        assert client.get(
            f"/api/v1/visitas/{visit_id}/history",
            headers=leader_headers,
        ).status_code == 403
        assert client.get(
            f"/api/v1/visitas/{visit_id}/history",
            headers=scenario.headers(scenario.other_pastor_id, UserRole.PASTOR),
        ).status_code == 404

        cancellation_at = datetime.now(BOGOTA) + timedelta(days=3)
        to_cancel = client.post(
            "/api/v1/visitas",
            headers=admin_headers,
            json=visit_request(scenario.other_brother_id, cancellation_at),
        )
        assert to_cancel.status_code == 201
        cancel_id = to_cancel.json()["id"]

        missing_reason = client.request(
            "DELETE",
            f"/api/v1/visitas/{cancel_id}",
            headers=pastor_headers,
            json={},
        )
        assert missing_reason.status_code == 422

        cancelled = client.request(
            "DELETE",
            f"/api/v1/visitas/{cancel_id}",
            headers=pastor_headers,
            json={"reason": "El hermano no estará disponible"},
        )
        assert cancelled.status_code == 204
        assert client.patch(
            f"/api/v1/visitas/{cancel_id}",
            headers=admin_headers,
            json={"scheduled_at": (cancellation_at + timedelta(days=1)).isoformat()},
        ).status_code == 409
        assert client.request(
            "DELETE",
            f"/api/v1/visitas/{cancel_id}",
            headers=admin_headers,
            json={"reason": "Segundo intento"},
        ).status_code == 409

        cancel_history = client.get(
            f"/api/v1/visitas/{cancel_id}/history",
            headers=pastor_headers,
        )
        assert cancel_history.status_code == 200
        assert cancel_history.json()[-1]["action"] == "CANCELADA"
        assert cancel_history.json()[-1]["reason"] == "El hermano no estará disponible"


@pytest.mark.parametrize("invalid_reference", ["foreign_leader", "brother_as_creator"])
def test_postgres_visit_trigger_rejects_invalid_leader_or_creator(
    visit_scenario: VisitScenario,
    invalid_reference: str,
) -> None:
    scenario = visit_scenario
    invalid_leader_id = (
        scenario.foreign_leader_id
        if invalid_reference == "foreign_leader"
        else scenario.leader_id
    )
    creator_id = (
        scenario.brother_id
        if invalid_reference == "brother_as_creator"
        else scenario.admin_id
    )

    async def persist_invalid_visit() -> None:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                async with session.begin():
                    session.add(
                        VisitModel(
                            brother_id=scenario.brother_id,
                            leader_id=invalid_leader_id,
                            created_by_id=creator_id,
                            visit_type="CUIDADO_PASTORAL",
                            scheduled_at=datetime.now(UTC) + timedelta(days=2),
                            duration_minutes=30,
                            location="Home",
                            observations="Direct database write",
                            status="PROGRAMADA",
                        )
                    )
                    await session.flush()
        finally:
            await engine.dispose()

    with pytest.raises(IntegrityError):
        asyncio.run(persist_invalid_visit())


def test_postgres_prevents_physical_visit_delete_and_history_mutation(
    visit_scenario: VisitScenario,
) -> None:
    scenario = visit_scenario
    visit_id = uuid4()

    async def create_visit_and_history() -> None:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                async with session.begin():
                    session.add(
                        VisitModel(
                            id=visit_id,
                            brother_id=scenario.brother_id,
                            leader_id=scenario.leader_id,
                            created_by_id=scenario.admin_id,
                            visit_type="ENSENANZA",
                            scheduled_at=datetime.now(UTC) + timedelta(days=2),
                            duration_minutes=30,
                            location="Home",
                            observations="Guard test",
                            status="PROGRAMADA",
                        )
                    )
                    await session.flush()
                    session.add(
                        VisitHistoryModel(
                            visit_id=visit_id,
                            actor_id=scenario.admin_id,
                            action="CREADA",
                            new_status="PROGRAMADA",
                        )
                    )
        finally:
            await engine.dispose()

    async def attempt_visit_delete() -> None:
        engine = create_database_engine()
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(VisitModel).where(VisitModel.id == visit_id))
        finally:
            await engine.dispose()

    async def attempt_history_update() -> None:
        engine = create_database_engine()
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    VisitHistoryModel.__table__.update()
                    .where(VisitHistoryModel.visit_id == visit_id)
                    .values(accion="ALTERADA")
                )
        finally:
            await engine.dispose()

    asyncio.run(create_visit_and_history())
    with pytest.raises(IntegrityError):
        asyncio.run(attempt_visit_delete())
    with pytest.raises(IntegrityError):
        asyncio.run(attempt_history_update())


def test_notification_failure_keeps_visit_and_outbox_for_retry(
    visit_scenario: VisitScenario,
) -> None:
    scenario = visit_scenario

    class FailingEmailSender:
        async def send_visit_created(self, notification: object) -> None:
            raise ConnectionError("SMTP transport unavailable")

    dispatcher = VisitNotificationDispatcher(
        DatabaseSettings().database_url,
        FailingEmailSender(),
    )
    app.dependency_overrides[get_visit_notification_dispatcher] = lambda: dispatcher
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/visitas",
                headers=scenario.headers(scenario.admin_id, UserRole.ADMIN),
                json=visit_request(
                    scenario.brother_id,
                    datetime.now(BOGOTA) + timedelta(days=1),
                ),
            )
        assert response.status_code == 201
        visit_id = UUID(response.json()["id"])

        async def inspect_result() -> tuple[VisitModel | None, list[NotificationOutboxModel]]:
            engine = create_database_engine()
            try:
                session_factory = async_sessionmaker(engine, expire_on_commit=False)
                async with session_factory() as session:
                    visit = await session.get(VisitModel, visit_id)
                    notifications = list(
                        (
                            await session.scalars(
                                select(NotificationOutboxModel).where(
                                    NotificationOutboxModel.visit_id == visit_id
                                )
                            )
                        ).all()
                    )
                    return visit, notifications
            finally:
                await engine.dispose()

        visit, notifications = asyncio.run(inspect_result())
        assert visit is not None
        assert len(notifications) == 2
        assert {item.recipient_email for item in notifications} == {
            f"{scenario.prefix}-leader-a@example.invalid",
            f"{scenario.prefix}-pastor@example.invalid",
        }
        assert all(item.status == "PENDIENTE" for item in notifications)
        assert all(item.attempt_count == 1 for item in notifications)
        assert all(item.last_error == "ConnectionError" for item in notifications)
    finally:
        app.dependency_overrides.pop(get_visit_notification_dispatcher, None)