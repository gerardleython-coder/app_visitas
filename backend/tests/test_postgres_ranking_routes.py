import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import os
from secrets import token_urlsafe
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.authentication import UserRole
from app.infrastructure.database import create_database_engine
from app.infrastructure.models import ChurchModel, DistrictModel, UserModel, VisitModel
from app.main import app


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 to run against configured PostgreSQL",
)


@dataclass
class RankingScenario:
    prefix: str
    secret_key: str
    district_id: UUID
    church_a_id: UUID
    church_b_id: UUID
    admin_id: UUID
    pastor_a_id: UUID
    pastor_b_id: UUID
    leader_a1_id: UUID
    leader_a2_id: UUID
    leader_a3_id: UUID
    leader_b_id: UUID
    brother_ids: list[UUID]

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
def ranking_scenario(monkeypatch: pytest.MonkeyPatch) -> RankingScenario:
    scenario = RankingScenario(
        prefix=f"hu07-{uuid4().hex}",
        secret_key=token_urlsafe(48),
        district_id=uuid4(),
        church_a_id=uuid4(),
        church_b_id=uuid4(),
        admin_id=uuid4(),
        pastor_a_id=uuid4(),
        pastor_b_id=uuid4(),
        leader_a1_id=uuid4(),
        leader_a2_id=uuid4(),
        leader_a3_id=uuid4(),
        leader_b_id=uuid4(),
        brother_ids=[uuid4() for _ in range(4)],
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
                    users = [
                        UserModel(
                            id=scenario.admin_id,
                            name="Admin",
                            surname="Ranking",
                            email=f"{scenario.prefix}-admin@example.invalid",
                            password_hash="test-only-hash",
                            role=UserRole.ADMIN,
                            active=True,
                        ),
                        UserModel(
                            id=scenario.pastor_a_id,
                            district_id=scenario.district_id,
                            church_id=scenario.church_a_id,
                            name="Pastor",
                            surname="A",
                            email=f"{scenario.prefix}-pastor-a@example.invalid",
                            password_hash="test-only-hash",
                            role=UserRole.PASTOR,
                            active=True,
                        ),
                        UserModel(
                            id=scenario.pastor_b_id,
                            district_id=scenario.district_id,
                            church_id=scenario.church_b_id,
                            name="Pastor",
                            surname="B",
                            email=f"{scenario.prefix}-pastor-b@example.invalid",
                            password_hash="test-only-hash",
                            role=UserRole.PASTOR,
                            active=True,
                        ),
                    ]
                    leader_specs = [
                        (scenario.leader_a1_id, scenario.church_a_id, "Ana", "Uno"),
                        (scenario.leader_a2_id, scenario.church_a_id, "Beto", "Dos"),
                        (scenario.leader_a3_id, scenario.church_a_id, "Carla", "Tres"),
                        (scenario.leader_b_id, scenario.church_b_id, "Dario", "Cuatro"),
                    ]
                    users.extend(
                        UserModel(
                            id=leader_id,
                            district_id=scenario.district_id,
                            church_id=church_id,
                            name=name,
                            surname=surname,
                            email=f"{scenario.prefix}-{name.lower()}@example.invalid",
                            password_hash="test-only-hash",
                            role=UserRole.LIDER,
                            active=True,
                        )
                        for leader_id, church_id, name, surname in leader_specs
                    )
                    users.extend(
                        UserModel(
                            id=brother_id,
                            district_id=scenario.district_id,
                            church_id=church_id,
                            leader_id=leader_id,
                            name=f"Brother {index}",
                            surname="Ranking",
                            phone=f"30000000{index:02d}",
                            address="Test address",
                            role=UserRole.HERMANO,
                            active=True,
                        )
                        for index, (brother_id, (leader_id, church_id, *_)) in enumerate(
                            zip(scenario.brother_ids, leader_specs, strict=True)
                        )
                    )
                    session.add_all(users)
                    await session.flush()

                    async def add_visits(leader_index: int, days: list[int]) -> None:
                        leader_id, church_id, *_ = leader_specs[leader_index]
                        brother_id = scenario.brother_ids[leader_index]
                        created_visits = []
                        for day in days:
                            completed_at = datetime(2026, 9, day, 16, tzinfo=UTC)
                            visit = VisitModel(
                                    brother_id=brother_id,
                                    leader_id=leader_id,
                                    created_by_id=scenario.admin_id,
                                    visit_type="CUIDADO_PASTORAL",
                                    scheduled_at=completed_at,
                                    duration_minutes=30,
                                    location="Church",
                                    observations="Ranking integration",
                                    status="PROGRAMADA",
                                )
                            session.add(visit)
                            created_visits.append((visit, completed_at))
                        await session.flush()
                        for visit, completed_at in created_visits:
                            visit.completed_at = completed_at
                            visit.status = "COMPLETADA"
                        await session.flush()

                    await add_visits(0, [2, 8, 14])
                    await add_visits(1, [3, 9])
                    await add_visits(2, [4, 10])
                    await add_visits(3, list(range(1, 13)))
                    upper_bound_visit = VisitModel(
                            brother_id=scenario.brother_ids[0],
                            leader_id=scenario.leader_a1_id,
                            created_by_id=scenario.admin_id,
                            visit_type="CUIDADO_PASTORAL",
                            scheduled_at=datetime(2026, 9, 25, tzinfo=UTC),
                            duration_minutes=30,
                            location="Church",
                            observations="Outside period by completion date",
                            status="PROGRAMADA",
                        )
                    session.add(upper_bound_visit)
                    await session.flush()
                    upper_bound_visit.completed_at = datetime(2026, 10, 1, 5, tzinfo=UTC)
                    upper_bound_visit.status = "COMPLETADA"
                    session.add(
                        VisitModel(
                            brother_id=scenario.brother_ids[0],
                            leader_id=scenario.leader_a1_id,
                            created_by_id=scenario.admin_id,
                            visit_type="CUIDADO_PASTORAL",
                            scheduled_at=datetime(2026, 9, 20, tzinfo=UTC),
                            duration_minutes=30,
                            location="Church",
                            observations="Not completed",
                            status="PROGRAMADA",
                        )
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
                    visit_ids = select(VisitModel.id).where(
                        VisitModel.brother_id.in_(scenario.brother_ids)
                    )
                    await connection.execute(
                        text("ALTER TABLE visitas DISABLE TRIGGER trg_impedir_eliminar_visita")
                    )
                    await connection.execute(delete(VisitModel).where(VisitModel.id.in_(visit_ids)))
                    await connection.execute(
                        text("ALTER TABLE visitas ENABLE TRIGGER trg_impedir_eliminar_visita")
                    )
                    await connection.execute(
                        delete(UserModel).where(
                            UserModel.id.in_(
                                [
                                    scenario.admin_id,
                                    scenario.pastor_a_id,
                                    scenario.pastor_b_id,
                                    scenario.leader_a1_id,
                                    scenario.leader_a2_id,
                                    scenario.leader_a3_id,
                                    scenario.leader_b_id,
                                    *scenario.brother_ids,
                                ]
                            )
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


def test_ranking_routes_enforce_scope_and_dense_rank(
    ranking_scenario: RankingScenario,
) -> None:
    scenario = ranking_scenario

    with TestClient(app) as client:
        admin_headers = scenario.headers(scenario.admin_id, UserRole.ADMIN)
        pastor_headers = scenario.headers(scenario.pastor_a_id, UserRole.PASTOR)
        response = client.get(
            "/api/v1/reports/ranking",
            headers=admin_headers,
            params={
                "church_id": str(scenario.church_a_id),
                "period": "MES",
                "reference_date": "2026-09-30",
            },
        )
        assert response.status_code == 200
        assert [
            (row["leader_name"], row["completed_visits"], row["position"])
            for row in response.json()
        ] == [("Ana Uno", 3, 1), ("Beto Dos", 2, 2), ("Carla Tres", 2, 2)]

        pastor_response = client.get(
            "/api/v1/reports/ranking",
            headers=pastor_headers,
            params={"period": "MES", "reference_date": "2026-09-30"},
        )
        assert pastor_response.status_code == 200
        assert [row["leader_id"] for row in pastor_response.json()] == [
            str(scenario.leader_a1_id),
            str(scenario.leader_a2_id),
            str(scenario.leader_a3_id),
        ]

        foreign_church_response = client.get(
            "/api/v1/reports/ranking",
            headers=pastor_headers,
            params={
                "church_id": str(scenario.church_b_id),
                "period": "MES",
                "reference_date": "2026-09-30",
            },
        )
        assert foreign_church_response.status_code == 403

        leader_headers = scenario.headers(scenario.leader_a1_id, UserRole.LIDER)
        assert client.get(
            "/api/v1/reports/ranking",
            headers=leader_headers,
            params={
                "church_id": str(scenario.church_a_id),
                "period": "MES",
                "reference_date": "2026-09-30",
            },
        ).status_code == 403

        assert client.get(
            "/api/v1/reports/ranking",
            headers=admin_headers,
            params={"period": "MES"},
        ).status_code == 422