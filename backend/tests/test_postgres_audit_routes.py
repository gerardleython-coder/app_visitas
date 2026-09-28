import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import os
from secrets import token_urlsafe
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.authentication import UserRole
from app.infrastructure.database import create_database_engine
from app.infrastructure.models import (
    AuditModel,
    BrotherAssignmentModel,
    ChurchModel,
    DistrictModel,
    UserModel,
)
from app.main import app


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 to run against configured PostgreSQL",
)


@dataclass
class AuditScenario:
    prefix: str
    secret_key: str
    district_id: UUID
    church_a_id: UUID
    church_b_id: UUID
    admin_id: UUID
    pastor_a_id: UUID
    pastor_b_id: UUID
    created_user_ids: list[UUID] = field(default_factory=list)

    def headers(self, actor_id: UUID, role: UserRole) -> dict[str, str]:
        issued_at = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": str(actor_id),
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
def audit_scenario(monkeypatch: pytest.MonkeyPatch) -> AuditScenario:
    scenario = AuditScenario(
        prefix=f"hu05-{uuid4().hex}",
        secret_key=token_urlsafe(48),
        district_id=uuid4(),
        church_a_id=uuid4(),
        church_b_id=uuid4(),
        admin_id=uuid4(),
        pastor_a_id=uuid4(),
        pastor_b_id=uuid4(),
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
                                id=scenario.church_a_id,
                                district_id=scenario.district_id,
                                name=f"{scenario.prefix}-church-a",
                            ),
                            ChurchModel(
                                id=scenario.church_b_id,
                                district_id=scenario.district_id,
                                name=f"{scenario.prefix}-church-b",
                            ),
                        ]
                    )
                    await session.flush()
                    session.add_all(
                        [
                            UserModel(
                                id=scenario.admin_id,
                                name="Integration Admin",
                                surname="Audit",
                                email=f"{scenario.prefix}-admin@example.invalid",
                                password_hash="test-only-hash",
                                role=UserRole.ADMIN,
                                active=True,
                            ),
                            UserModel(
                                id=scenario.pastor_a_id,
                                district_id=scenario.district_id,
                                church_id=scenario.church_a_id,
                                name="Pastor A",
                                surname="Audit",
                                email=f"{scenario.prefix}-pastor-a@example.invalid",
                                password_hash="test-only-hash",
                                role=UserRole.PASTOR,
                                active=True,
                            ),
                            UserModel(
                                id=scenario.pastor_b_id,
                                district_id=scenario.district_id,
                                church_id=scenario.church_b_id,
                                name="Pastor B",
                                surname="Audit",
                                email=f"{scenario.prefix}-pastor-b@example.invalid",
                                password_hash="test-only-hash",
                                role=UserRole.PASTOR,
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
                    actor_ids = [scenario.admin_id, scenario.pastor_a_id, scenario.pastor_b_id]
                    await connection.execute(
                        text("ALTER TABLE auditoria DISABLE TRIGGER trg_proteger_auditoria")
                    )
                    await connection.execute(
                        delete(AuditModel).where(
                            AuditModel.actor_id.in_(actor_ids)
                            | AuditModel.resource_id.in_(scenario.created_user_ids)
                        )
                    )
                    await connection.execute(
                        text("ALTER TABLE auditoria ENABLE TRIGGER trg_proteger_auditoria")
                    )
                    await connection.execute(
                        delete(BrotherAssignmentModel).where(
                            BrotherAssignmentModel.brother_id.in_(scenario.created_user_ids)
                            | BrotherAssignmentModel.leader_id.in_(scenario.created_user_ids)
                            | BrotherAssignmentModel.assigned_by_id.in_(actor_ids)
                        )
                    )
                    await connection.execute(
                        delete(UserModel).where(
                            UserModel.id.in_(scenario.created_user_ids)
                            | UserModel.id.in_(actor_ids)
                        )
                    )
                    await connection.execute(
                        delete(ChurchModel).where(
                            ChurchModel.id.in_([scenario.church_a_id, scenario.church_b_id])
                        )
                    )
                    await connection.execute(
                        delete(DistrictModel).where(DistrictModel.id == scenario.district_id)
                    )
            finally:
                await engine.dispose()

        asyncio.run(cleanup())


def test_audit_is_global_for_admin_and_limited_to_pastor_church(
    audit_scenario: AuditScenario,
) -> None:
    scenario = audit_scenario
    admin_headers = scenario.headers(scenario.admin_id, UserRole.ADMIN)
    pastor_a_headers = scenario.headers(scenario.pastor_a_id, UserRole.PASTOR)
    pastor_b_headers = scenario.headers(scenario.pastor_b_id, UserRole.PASTOR)
    passwords = [token_urlsafe(24) for _ in range(3)]

    with TestClient(app) as client:
        leader_a_response = client.post(
            "/api/v1/users/lideres",
            headers=admin_headers,
            json={
                "name": "Leader A",
                "surname": "Audit",
                "email": f"{scenario.prefix}-leader-a@example.invalid",
                "password": passwords[0],
                "district_id": str(scenario.district_id),
                "church_id": str(scenario.church_a_id),
            },
        )
        assert leader_a_response.status_code == 201
        leader_a_id = UUID(leader_a_response.json()["id"])
        scenario.created_user_ids.append(leader_a_id)

        leader_a_replacement_response = client.post(
            "/api/v1/users/lideres",
            headers=admin_headers,
            json={
                "name": "Leader A",
                "surname": "Replacement",
                "email": f"{scenario.prefix}-leader-a2@example.invalid",
                "password": passwords[1],
                "district_id": str(scenario.district_id),
                "church_id": str(scenario.church_a_id),
            },
        )
        assert leader_a_replacement_response.status_code == 201
        leader_a_replacement_id = UUID(leader_a_replacement_response.json()["id"])
        scenario.created_user_ids.append(leader_a_replacement_id)

        leader_b_response = client.post(
            "/api/v1/users/lideres",
            headers=admin_headers,
            json={
                "name": "Leader B",
                "surname": "Audit",
                "email": f"{scenario.prefix}-leader-b@example.invalid",
                "password": passwords[2],
                "district_id": str(scenario.district_id),
                "church_id": str(scenario.church_b_id),
            },
        )
        assert leader_b_response.status_code == 201
        leader_b_id = UUID(leader_b_response.json()["id"])
        scenario.created_user_ids.append(leader_b_id)

        brother_a_response = client.post(
            "/api/v1/hermanos",
            headers=admin_headers,
            json={
                "name": "Brother A",
                "surname": "Audit",
                "phone": "3001001001",
                "address": "Church A",
                "district_id": str(scenario.district_id),
                "church_id": str(scenario.church_a_id),
                "leader_id": str(leader_a_id),
            },
        )
        assert brother_a_response.status_code == 201
        brother_a_id = UUID(brother_a_response.json()["id"])
        scenario.created_user_ids.append(brother_a_id)

        brother_b_response = client.post(
            "/api/v1/hermanos",
            headers=admin_headers,
            json={
                "name": "Brother B",
                "surname": "Audit",
                "phone": "3001001002",
                "address": "Church B",
                "district_id": str(scenario.district_id),
                "church_id": str(scenario.church_b_id),
                "leader_id": str(leader_b_id),
            },
        )
        assert brother_b_response.status_code == 201
        brother_b_id = UUID(brother_b_response.json()["id"])
        scenario.created_user_ids.append(brother_b_id)

        update_leader = client.patch(
            f"/api/v1/users/lideres/{leader_a_id}",
            headers=admin_headers,
            json={"name": "Leader A Updated"},
        )
        assert update_leader.status_code == 200

        update_brother = client.patch(
            f"/api/v1/hermanos/{brother_a_id}",
            headers=admin_headers,
            json={"phone": "3001001999"},
        )
        assert update_brother.status_code == 200

        reassign = client.patch(
            f"/api/v1/hermanos/{brother_a_id}/lider",
            headers=admin_headers,
            json={"leader_id": str(leader_a_replacement_id)},
        )
        assert reassign.status_code == 200

        deactivate_brother = client.delete(
            f"/api/v1/hermanos/{brother_b_id}",
            headers=pastor_b_headers,
        )
        assert deactivate_brother.status_code == 204

        deactivate_leader = client.delete(
            f"/api/v1/users/lideres/{leader_a_id}",
            headers=admin_headers,
        )
        assert deactivate_leader.status_code == 204

        admin_audit = client.get("/api/v1/audit", headers=admin_headers)
        assert admin_audit.status_code == 200
        all_events = admin_audit.json()
        leader_created = next(
            event
            for event in all_events
            if event["resource_id"] == str(leader_a_id) and event["action"] == "CREADO"
        )
        leader_modified = next(
            event
            for event in all_events
            if event["resource_id"] == str(leader_a_id) and event["action"] == "MODIFICADO"
        )
        brother_modified = next(
            event
            for event in all_events
            if event["resource_id"] == str(brother_a_id) and event["action"] == "MODIFICADO"
        )
        brother_reassigned = next(
            event
            for event in all_events
            if event["resource_id"] == str(brother_a_id)
            and event["action"] == "LIDER_REASIGNADO"
        )
        brother_deactivated = next(
            event
            for event in all_events
            if event["resource_id"] == str(brother_b_id)
            and event["action"] == "DESACTIVADO"
        )
        assert leader_created["new_values"]["role"] == UserRole.LIDER.value
        assert leader_modified["previous_values"]["name"] == "Leader A"
        assert leader_modified["new_values"]["name"] == "Leader A Updated"
        assert brother_modified["previous_values"]["phone"] == "3001001001"
        assert brother_modified["new_values"]["phone"] == "3001001999"
        assert brother_reassigned["previous_values"]["leader_id"] == str(leader_a_id)
        assert brother_reassigned["new_values"]["leader_id"] == str(leader_a_replacement_id)
        assert brother_deactivated["previous_values"]["active"] is True
        assert brother_deactivated["new_values"]["active"] is False
        sensitive_keys = {
            "password",
            "password_hash",
            "token",
            "token_hash",
            "access_token",
            "refresh_token",
        }
        for event in all_events:
            for snapshot_name in ("previous_values", "new_values"):
                snapshot = event[snapshot_name] or {}
                assert sensitive_keys.isdisjoint(snapshot)
        audit_payload = str(all_events)
        assert all(password not in audit_payload for password in passwords)
        assert all(
            headers["Authorization"] not in audit_payload
            for headers in (admin_headers, pastor_a_headers, pastor_b_headers)
        )

        paged_audit = client.get("/api/v1/audit?limit=1", headers=admin_headers)
        assert paged_audit.status_code == 200
        assert len(paged_audit.json()) == 1

        pastor_audit = client.get("/api/v1/audit", headers=pastor_a_headers)
        assert pastor_audit.status_code == 200
        assert pastor_audit.json()
        assert all(event["church_id"] == str(scenario.church_a_id) for event in pastor_audit.json())
        assert not any(
            event["resource_id"] == str(brother_b_id) for event in pastor_audit.json()
        )

        pastor_b_audit = client.get("/api/v1/audit", headers=pastor_b_headers)
        assert pastor_b_audit.status_code == 200
        assert all(event["church_id"] == str(scenario.church_b_id) for event in pastor_b_audit.json())
        assert any(event["resource_id"] == str(brother_b_id) for event in pastor_b_audit.json())

        leader_headers = scenario.headers(leader_a_replacement_id, UserRole.LIDER)
        assert client.get("/api/v1/audit", headers=leader_headers).status_code == 403


def test_postgresql_rejects_direct_audit_updates_and_deletes(
    audit_scenario: AuditScenario,
) -> None:
    scenario = audit_scenario
    admin_headers = scenario.headers(scenario.admin_id, UserRole.ADMIN)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/users/lideres",
            headers=admin_headers,
            json={
                "name": "Immutable",
                "surname": "Audit",
                "email": f"{scenario.prefix}-immutable@example.invalid",
                "password": token_urlsafe(24),
                "district_id": str(scenario.district_id),
                "church_id": str(scenario.church_a_id),
            },
        )
    assert response.status_code == 201
    resource_id = UUID(response.json()["id"])
    scenario.created_user_ids.append(resource_id)

    async def attempt_update() -> None:
        engine = create_database_engine()
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    update(AuditModel)
                    .where(
                        AuditModel.actor_id == scenario.admin_id,
                        AuditModel.resource_id == resource_id,
                    )
                    .values(reason="tampered")
                )
        finally:
            await engine.dispose()

    async def attempt_delete() -> None:
        engine = create_database_engine()
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    delete(AuditModel).where(
                        AuditModel.actor_id == scenario.admin_id,
                        AuditModel.resource_id == resource_id,
                    )
                )
        finally:
            await engine.dispose()

    with pytest.raises(IntegrityError, match="La auditoría es inmutable"):
        asyncio.run(attempt_update())
    with pytest.raises(IntegrityError, match="La auditoría es inmutable"):
        asyncio.run(attempt_delete())