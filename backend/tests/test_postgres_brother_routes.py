import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import os
from secrets import token_urlsafe
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.authentication import UserRole
from app.infrastructure.database import create_database_engine
from app.infrastructure.models import AuditModel, ChurchModel, DistrictModel, UserModel
from app.infrastructure.password_service import Argon2PasswordService
from app.main import app


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 to run against configured PostgreSQL",
)


@dataclass
class BrotherScenario:
    prefix: str
    secret_key: str
    district_id: UUID
    church_id: UUID
    other_church_id: UUID
    admin_id: UUID
    pastor_id: UUID
    leader_id: UUID
    other_leader_id: UUID
    foreign_leader_id: UUID
    password: str
    brother_ids: list[UUID] = field(default_factory=list)

    def headers(self, account_id: UUID, role: UserRole) -> dict[str, str]:
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": str(account_id),
                "role": role.value,
                "token_type": "access",
                "iat": now,
                "exp": now + timedelta(minutes=15),
            },
            self.secret_key,
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def brother_scenario(monkeypatch: pytest.MonkeyPatch) -> BrotherScenario:
    scenario = BrotherScenario(
        prefix=f"brother-hu03-{uuid4().hex}",
        secret_key=token_urlsafe(48),
        district_id=uuid4(),
        church_id=uuid4(),
        other_church_id=uuid4(),
        admin_id=uuid4(),
        pastor_id=uuid4(),
        leader_id=uuid4(),
        other_leader_id=uuid4(),
        foreign_leader_id=uuid4(),
        password=token_urlsafe(24),
    )
    monkeypatch.setenv("SECRET_KEY", scenario.secret_key)

    async def prepare() -> None:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                async with session.begin():
                    session.add(
                        DistrictModel(id=scenario.district_id, name=scenario.prefix)
                    )
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
                    password_hash = Argon2PasswordService().hash(scenario.password)
                    session.add_all(
                        [
                            UserModel(
                                id=scenario.admin_id,
                                name=f"{scenario.prefix}-admin",
                                surname="Admin",
                                email=f"{scenario.prefix}-admin@example.invalid",
                                password_hash=password_hash,
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
                                password_hash=password_hash,
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
                                password_hash=password_hash,
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
                                password_hash=password_hash,
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
                                password_hash=password_hash,
                                role=UserRole.LIDER,
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
                    has_assignments = await connection.run_sync(
                        lambda sync_connection: inspect(sync_connection).has_table(
                            "asignaciones_hermano"
                        )
                    )
                    has_audit = await connection.run_sync(
                        lambda sync_connection: inspect(sync_connection).has_table("auditoria")
                    )
                    actor_ids = [
                        scenario.admin_id,
                        scenario.pastor_id,
                        scenario.leader_id,
                        scenario.other_leader_id,
                        scenario.foreign_leader_id,
                    ]
                    if has_audit:
                        await connection.execute(
                            text("ALTER TABLE auditoria DISABLE TRIGGER trg_proteger_auditoria")
                        )
                        await connection.execute(
                            delete(AuditModel).where(
                                AuditModel.actor_id.in_(actor_ids)
                                | AuditModel.resource_id.in_(scenario.brother_ids)
                            )
                        )
                        await connection.execute(
                            text("ALTER TABLE auditoria ENABLE TRIGGER trg_proteger_auditoria")
                        )
                    if has_assignments:
                        await connection.execute(
                            text(
                                "DELETE FROM asignaciones_hermano "
                                "WHERE hermano_id IN ("
                                "SELECT id FROM usuarios WHERE rol = 'HERMANO' "
                                "AND iglesia_id IN (:church_id, :other_church_id)) "
                                "OR lider_id IN (:leader_a, :leader_b, :foreign_leader) "
                                "OR asignado_por IN (:admin_id, :pastor_id, :leader_a, :leader_b)"
                            ),
                            {
                                "leader_a": scenario.leader_id,
                                "leader_b": scenario.other_leader_id,
                                "foreign_leader": scenario.foreign_leader_id,
                                "admin_id": scenario.admin_id,
                                "pastor_id": scenario.pastor_id,
                                "church_id": scenario.church_id,
                                "other_church_id": scenario.other_church_id,
                            },
                        )
                        if scenario.brother_ids:
                            await connection.execute(
                                text(
                                    "DELETE FROM asignaciones_hermano "
                                    "WHERE hermano_id = ANY(:brother_ids)"
                                ),
                                {"brother_ids": scenario.brother_ids},
                            )
                    if scenario.brother_ids:
                        await connection.execute(
                            delete(UserModel).where(UserModel.id.in_(scenario.brother_ids))
                        )
                    await connection.execute(
                        delete(UserModel).where(
                            UserModel.role == UserRole.HERMANO,
                            UserModel.church_id.in_(
                                [scenario.church_id, scenario.other_church_id]
                            ),
                        )
                    )
                    await connection.execute(
                        delete(UserModel).where(
                            UserModel.email.like(f"{scenario.prefix}%")
                            | UserModel.name.like(f"{scenario.prefix}%")
                        )
                    )
                    await connection.execute(
                        delete(ChurchModel).where(
                            ChurchModel.id.in_(
                                [scenario.church_id, scenario.other_church_id]
                            )
                        )
                    )
                    await connection.execute(
                        delete(DistrictModel).where(
                            DistrictModel.id == scenario.district_id
                        )
                    )
            finally:
                await engine.dispose()

        asyncio.run(cleanup())


def test_brother_routes_enforce_scope_and_preserve_leader_assignment_history(
    brother_scenario: BrotherScenario,
) -> None:
    scenario = brother_scenario
    admin_headers = scenario.headers(scenario.admin_id, UserRole.ADMIN)
    pastor_headers = scenario.headers(scenario.pastor_id, UserRole.PASTOR)
    leader_headers = scenario.headers(scenario.leader_id, UserRole.LIDER)
    other_leader_headers = scenario.headers(scenario.other_leader_id, UserRole.LIDER)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/hermanos",
            headers=admin_headers,
            json={
                "name": "Maria",
                "surname": "Test",
                "phone": "3001112233",
                "address": "Calle de prueba",
                "district_id": str(scenario.district_id),
                "church_id": str(scenario.church_id),
                "leader_id": str(scenario.leader_id),
            },
        )
        assert created.status_code == 201
        brother_id = UUID(created.json()["id"])
        scenario.brother_ids.append(brother_id)
        assert created.json()["role"] == UserRole.HERMANO.value
        assert created.json()["active"] is True
        assert "email" not in created.json()
        assert "password_hash" not in created.json()

        pastor_created = client.post(
            "/api/v1/hermanos",
            headers=pastor_headers,
            json={
                "name": "Ana",
                "surname": "Pastor Created",
                "phone": "3002223344",
                "address": "Otra direccion",
                "district_id": str(scenario.district_id),
                "church_id": str(scenario.church_id),
                "leader_id": str(scenario.leader_id),
            },
        )
        assert pastor_created.status_code == 201
        pastor_brother_id = UUID(pastor_created.json()["id"])
        scenario.brother_ids.append(pastor_brother_id)
        assert pastor_created.json()["leader_id"] == str(scenario.leader_id)

        pastor_out_of_scope = client.post(
            "/api/v1/hermanos",
            headers=pastor_headers,
            json={
                "name": "Out",
                "surname": "Of Scope",
                "phone": "3002223345",
                "address": "Address",
                "district_id": str(scenario.district_id),
                "church_id": str(scenario.other_church_id),
                "leader_id": str(scenario.foreign_leader_id),
            },
        )
        assert pastor_out_of_scope.status_code == 403

        pastor_list = client.get("/api/v1/hermanos", headers=pastor_headers)
        assert pastor_list.status_code == 200
        assert {item["id"] for item in pastor_list.json()} == {
            str(brother_id),
            str(pastor_brother_id),
        }

        leader_detail = client.get(
            f"/api/v1/hermanos/{brother_id}",
            headers=leader_headers,
        )
        assert leader_detail.status_code == 200
        assert leader_detail.json()["leader_id"] == str(scenario.leader_id)
        assert client.get(
            f"/api/v1/hermanos/{brother_id}",
            headers=other_leader_headers,
        ).status_code == 404

        profile_update = client.patch(
            f"/api/v1/hermanos/{brother_id}",
            headers=leader_headers,
            json={"phone": "3009998877", "address": "Nueva direccion"},
        )
        assert profile_update.status_code == 200
        assert profile_update.json()["phone"] == "3009998877"
        pastor_profile_update = client.patch(
            f"/api/v1/hermanos/{brother_id}",
            headers=pastor_headers,
            json={"surname": "Pastor Updated"},
        )
        assert pastor_profile_update.status_code == 200
        assert pastor_profile_update.json()["surname"] == "Pastor Updated"
        assert client.patch(
            f"/api/v1/hermanos/{brother_id}",
            headers=leader_headers,
            json={"leader_id": str(scenario.other_leader_id)},
        ).status_code == 422
        assert client.delete(
            f"/api/v1/hermanos/{brother_id}",
            headers=other_leader_headers,
        ).status_code == 404
        assert client.patch(
            f"/api/v1/hermanos/{brother_id}/lider",
            headers=leader_headers,
            json={"leader_id": str(scenario.other_leader_id)},
        ).status_code == 403

        reassigned = client.patch(
            f"/api/v1/hermanos/{brother_id}/lider",
            headers=pastor_headers,
            json={"leader_id": str(scenario.other_leader_id)},
        )
        assert reassigned.status_code == 200
        assert reassigned.json()["leader_id"] == str(scenario.other_leader_id)
        assert client.get(
            f"/api/v1/hermanos/{brother_id}",
            headers=leader_headers,
        ).status_code == 404
        assert client.get(
            f"/api/v1/hermanos/{brother_id}",
            headers=other_leader_headers,
        ).status_code == 200

        cross_church_reassignment = client.patch(
            f"/api/v1/hermanos/{brother_id}/lider",
            headers=admin_headers,
            json={"leader_id": str(scenario.foreign_leader_id)},
        )
        assert cross_church_reassignment.status_code == 422

        second_brother = client.post(
            "/api/v1/hermanos",
            headers=leader_headers,
            json={
                "name": "Luis",
                "surname": "Leader Created",
                "phone": "3005556677",
                "address": "Direccion",
                "district_id": str(scenario.district_id),
                "church_id": str(scenario.church_id),
            },
        )
        assert second_brother.status_code == 201
        second_brother_id = UUID(second_brother.json()["id"])
        scenario.brother_ids.append(second_brother_id)
        assert second_brother.json()["leader_id"] == str(scenario.leader_id)

        pastor_deactivated = client.delete(
            f"/api/v1/hermanos/{second_brother_id}",
            headers=pastor_headers,
        )
        assert pastor_deactivated.status_code == 204

        deactivated = client.delete(
            f"/api/v1/hermanos/{brother_id}",
            headers=other_leader_headers,
        )
        assert deactivated.status_code == 204

    async def read_persistence() -> tuple[UserModel | None, list[dict[str, object]]]:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                brother = await session.get(UserModel, brother_id)
                rows = await session.execute(
                    text(
                        "SELECT lider_id, asignado_por, fecha_fin "
                        "FROM asignaciones_hermano WHERE hermano_id = :brother_id "
                        "ORDER BY fecha_asignacion"
                    ),
                    {"brother_id": brother_id},
                )
                return brother, [dict(row._mapping) for row in rows]
        finally:
            await engine.dispose()

    brother, assignments = asyncio.run(read_persistence())
    assert brother is not None
    assert brother.role is UserRole.HERMANO
    assert brother.email is None
    assert brother.password_hash is None
    assert brother.active is False
    assert brother.leader_id == scenario.other_leader_id
    assert len(assignments) == 2
    assert assignments[0]["lider_id"] == scenario.leader_id
    assert assignments[0]["asignado_por"] == scenario.admin_id
    assert assignments[0]["fecha_fin"] is not None
    assert assignments[1]["lider_id"] == scenario.other_leader_id
    assert assignments[1]["asignado_por"] == scenario.pastor_id
    assert assignments[1]["fecha_fin"] is not None


@pytest.mark.parametrize("invalid_leader", ["pastor_id", "foreign_leader_id"])
def test_postgresql_rejects_brother_with_wrong_role_or_church(
    brother_scenario: BrotherScenario,
    invalid_leader: str,
) -> None:
    scenario = brother_scenario
    invalid_leader_id = getattr(scenario, invalid_leader)
    brother_id = uuid4()

    async def persist_invalid_brother() -> None:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                async with session.begin():
                    session.add(
                        UserModel(
                            id=brother_id,
                            district_id=scenario.district_id,
                            church_id=scenario.church_id,
                            leader_id=invalid_leader_id,
                            name=f"{scenario.prefix}-invalid-brother",
                            surname="Invalid",
                            phone="3000000000",
                            address="Address",
                            role=UserRole.HERMANO,
                            active=True,
                        )
                    )
                    await session.flush()
        finally:
            await engine.dispose()

    with pytest.raises(IntegrityError):
        asyncio.run(persist_invalid_brother())