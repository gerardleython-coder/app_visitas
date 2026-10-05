import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import os
from secrets import token_urlsafe
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.authentication import UserRole
from app.infrastructure.database import create_database_engine
from app.infrastructure.models import AuditModel, ChurchModel, DistrictModel, UserModel
from app.main import app


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 to run against configured PostgreSQL",
)


@dataclass
class TerritoryScenario:
    prefix: str
    secret_key: str
    district_id: UUID
    church_id: UUID
    admin_id: UUID
    pastor_id: UUID
    leader_id: UUID
    brother_id: UUID
    created_district_ids: list[UUID] = field(default_factory=list)
    created_church_ids: list[UUID] = field(default_factory=list)

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
def territory_scenario(monkeypatch: pytest.MonkeyPatch) -> TerritoryScenario:
    scenario = TerritoryScenario(
        prefix=f"territory-{uuid4().hex}",
        secret_key=token_urlsafe(48),
        district_id=uuid4(),
        church_id=uuid4(),
        admin_id=uuid4(),
        pastor_id=uuid4(),
        leader_id=uuid4(),
        brother_id=uuid4(),
    )
    monkeypatch.setenv("SECRET_KEY", scenario.secret_key)

    async def prepare() -> None:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                async with session.begin():
                    session.add(
                        DistrictModel(id=scenario.district_id, name=f"{scenario.prefix}-district")
                    )
                    await session.flush()
                    session.add(
                        ChurchModel(
                            id=scenario.church_id,
                            district_id=scenario.district_id,
                            name=f"{scenario.prefix}-church",
                        )
                    )
                    await session.flush()
                    session.add_all(
                        [
                            UserModel(
                                id=scenario.admin_id,
                                name="Territory",
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
                                name="Territory",
                                surname="Pastor",
                                email=f"{scenario.prefix}-pastor@example.invalid",
                                password_hash="test-only-hash",
                                role=UserRole.PASTOR,
                                active=True,
                            ),
                            UserModel(
                                id=scenario.leader_id,
                                district_id=scenario.district_id,
                                church_id=scenario.church_id,
                                name="Territory",
                                surname="Leader",
                                email=f"{scenario.prefix}-leader@example.invalid",
                                password_hash="test-only-hash",
                                role=UserRole.LIDER,
                                active=True,
                            ),
                            UserModel(
                                id=scenario.brother_id,
                                district_id=scenario.district_id,
                                church_id=scenario.church_id,
                                leader_id=scenario.leader_id,
                                name="Territory",
                                surname="Brother",
                                phone="3000000000",
                                address="Test address",
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
                        text("ALTER TABLE auditoria DISABLE TRIGGER trg_proteger_auditoria")
                    )
                    await connection.execute(
                        delete(AuditModel).where(AuditModel.actor_id == scenario.admin_id)
                    )
                    await connection.execute(
                        text("ALTER TABLE auditoria ENABLE TRIGGER trg_proteger_auditoria")
                    )
                    user_ids = [
                        scenario.admin_id,
                        scenario.pastor_id,
                        scenario.leader_id,
                        scenario.brother_id,
                    ]
                    await connection.execute(delete(UserModel).where(UserModel.id.in_(user_ids)))
                    await connection.execute(
                        delete(ChurchModel).where(
                            ChurchModel.id.in_([scenario.church_id, *scenario.created_church_ids])
                        )
                    )
                    await connection.execute(
                        delete(DistrictModel).where(
                            DistrictModel.id.in_([scenario.district_id, *scenario.created_district_ids])
                        )
                    )
            finally:
                await engine.dispose()

        asyncio.run(cleanup())


def test_admin_territory_crud_respects_dependencies_and_preserves_audit(
    territory_scenario: TerritoryScenario,
) -> None:
    scenario = territory_scenario
    admin_headers = scenario.headers(scenario.admin_id, UserRole.ADMIN)
    pastor_headers = scenario.headers(scenario.pastor_id, UserRole.PASTOR)
    leader_headers = scenario.headers(scenario.leader_id, UserRole.LIDER)

    with TestClient(app) as client:
        assert client.get("/api/v1/admin/distritos", headers=pastor_headers).status_code == 403
        assert client.get("/api/v1/admin/distritos", headers=leader_headers).status_code == 403
        assert client.post(
            "/api/v1/admin/distritos",
            headers=pastor_headers,
            json={"name": f"{scenario.prefix}-forbidden"},
        ).status_code == 403
        assert client.post(
            "/api/v1/admin/distritos",
            headers=leader_headers,
            json={"name": f"{scenario.prefix}-leader-forbidden"},
        ).status_code == 403

        districts = client.get("/api/v1/admin/distritos", headers=admin_headers)
        assert districts.status_code == 200
        assert any(item["id"] == str(scenario.district_id) for item in districts.json())
        assert not any(
            item["name"] in {
                f"{scenario.prefix}-forbidden",
                f"{scenario.prefix}-leader-forbidden",
            }
            for item in districts.json()
        )

        new_district = client.post(
            "/api/v1/admin/distritos",
            headers=admin_headers,
            json={"name": f"{scenario.prefix}-empty"},
        )
        assert new_district.status_code == 201
        new_district_id = UUID(new_district.json()["id"])
        scenario.created_district_ids.append(new_district_id)
        renamed_district = client.patch(
            f"/api/v1/admin/distritos/{new_district_id}",
            headers=admin_headers,
            json={"name": f"{scenario.prefix}-renamed"},
        )
        assert renamed_district.status_code == 200
        assert renamed_district.json()["name"] == f"{scenario.prefix}-renamed"
        assert client.delete(
            f"/api/v1/admin/distritos/{new_district_id}",
            headers=admin_headers,
        ).status_code == 204

        new_church = client.post(
            "/api/v1/admin/iglesias",
            headers=admin_headers,
            json={
                "district_id": str(scenario.district_id),
                "name": f"{scenario.prefix}-empty-church",
                "address": "  First Street  ",
            },
        )
        assert new_church.status_code == 201
        new_church_id = UUID(new_church.json()["id"])
        scenario.created_church_ids.append(new_church_id)
        assert new_church.json()["address"] == "First Street"
        assert client.patch(
            f"/api/v1/admin/iglesias/{new_church_id}",
            headers=admin_headers,
            json={"address": "Second Street"},
        ).json()["address"] == "Second Street"
        assert client.delete(
            f"/api/v1/admin/iglesias/{new_church_id}",
            headers=admin_headers,
        ).status_code == 204

        filtered = client.get(
            "/api/v1/admin/iglesias",
            headers=admin_headers,
            params={"district_id": str(scenario.district_id)},
        )
        assert filtered.status_code == 200
        assert any(item["id"] == str(new_church_id) and not item["active"] for item in filtered.json())

        assert client.delete(
            f"/api/v1/admin/iglesias/{scenario.church_id}",
            headers=admin_headers,
        ).status_code == 409
        assert client.delete(
            f"/api/v1/admin/distritos/{scenario.district_id}",
            headers=admin_headers,
        ).status_code == 409

        audit_response = client.get("/api/v1/audit", headers=admin_headers)
        assert audit_response.status_code == 200
        assert any(
            item["resource_id"] == str(new_district_id) and item["action"] == "ELIMINADO"
            for item in audit_response.json()
        )
        assert any(
            item["resource_id"] == str(new_church_id) and item["action"] == "DESACTIVADO"
            for item in audit_response.json()
        )