from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.authentication import UserRole
from app.infrastructure.database import Base
from app.infrastructure.leader_ranking_repository import SQLAlchemyLeaderRankingRepository
from app.infrastructure.models import ChurchModel, DistrictModel, UserModel, VisitModel


async def test_ranking_counts_only_completed_visits_in_church_and_period() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    district_id = uuid4()
    church_id = uuid4()
    other_church_id = uuid4()
    admin_id = uuid4()
    leader_ids = [uuid4(), uuid4(), uuid4(), uuid4()]
    brother_ids = [uuid4(), uuid4(), uuid4(), uuid4()]

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(DistrictModel(id=district_id, name="Ranking district"))
            await session.flush()
            session.add_all(
                [
                    ChurchModel(id=church_id, district_id=district_id, name="Ranking A"),
                    ChurchModel(
                        id=other_church_id,
                        district_id=district_id,
                        name="Ranking B",
                    ),
                ]
            )
            await session.flush()
            session.add(
                UserModel(
                    id=admin_id,
                    name="Admin",
                    surname="Ranking",
                    email="ranking-admin@example.test",
                    password_hash="test-only-hash",
                    role=UserRole.ADMIN,
                    active=True,
                )
            )
            names = [("Ana", "Uno"), ("Beto", "Dos"), ("Carla", "Tres"), ("Dario", "Cuatro")]
            session.add_all(
                [
                    UserModel(
                        id=leader_ids[index],
                        district_id=district_id,
                        church_id=other_church_id if index == 3 else church_id,
                        name=name,
                        surname=surname,
                        email=f"ranking-leader-{index}@example.test",
                        password_hash="test-only-hash",
                        role=UserRole.LIDER,
                        active=True,
                    )
                    for index, (name, surname) in enumerate(names)
                ]
            )
            await session.flush()
            session.add_all(
                [
                    UserModel(
                        id=brother_ids[index],
                        district_id=district_id,
                        church_id=other_church_id if index == 3 else church_id,
                        leader_id=leader_ids[index],
                        name=f"Brother {index}",
                        surname="Ranking",
                        phone=f"300000000{index}",
                        address="Test address",
                        role=UserRole.HERMANO,
                        active=True,
                    )
                    for index in range(4)
                ]
            )
            await session.flush()

            async def add_visit(
                leader_index: int,
                *,
                completed_at: datetime | None,
                status: str,
                scheduled_at: datetime,
            ) -> None:
                session.add(
                    VisitModel(
                        brother_id=brother_ids[leader_index],
                        leader_id=leader_ids[leader_index],
                        created_by_id=admin_id,
                        visit_type="CUIDADO_PASTORAL",
                        scheduled_at=scheduled_at,
                        completed_at=completed_at,
                        duration_minutes=30,
                        location="Church",
                        observations="Ranking test",
                        status=status,
                    )
                )

            for day in (2, 8, 14):
                await add_visit(
                    0,
                    completed_at=datetime(2026, 9, day, tzinfo=UTC),
                    scheduled_at=datetime(2026, 9, day, tzinfo=UTC),
                    status="COMPLETADA",
                )
            for day in (3, 9):
                await add_visit(
                    1,
                    completed_at=datetime(2026, 9, day, tzinfo=UTC),
                    scheduled_at=datetime(2026, 9, day, tzinfo=UTC),
                    status="COMPLETADA",
                )
            for day in (4, 10):
                await add_visit(
                    2,
                    completed_at=datetime(2026, 9, day, tzinfo=UTC),
                    scheduled_at=datetime(2026, 9, day, tzinfo=UTC),
                    status="COMPLETADA",
                )
            await add_visit(
                0,
                completed_at=None,
                scheduled_at=datetime(2026, 9, 20, tzinfo=UTC),
                status="PROGRAMADA",
            )
            await add_visit(
                0,
                completed_at=datetime(2026, 10, 1, tzinfo=UTC),
                scheduled_at=datetime(2026, 9, 25, tzinfo=UTC),
                status="COMPLETADA",
            )
            for day in range(1, 12):
                await add_visit(
                    3,
                    completed_at=datetime(2026, 9, day, tzinfo=UTC),
                    scheduled_at=datetime(2026, 9, day, tzinfo=UTC),
                    status="COMPLETADA",
                )
            await session.flush()

            rows = await SQLAlchemyLeaderRankingRepository(session).list_leader_ranking(
                church_id=church_id,
                starts_at=datetime(2026, 9, 1, tzinfo=UTC),
                ends_at=datetime(2026, 10, 1, tzinfo=UTC),
            )

        assert [
            (row.leader_name, row.completed_visits, row.position)
            for row in rows
        ] == [("Ana Uno", 3, 1), ("Beto Dos", 2, 2), ("Carla Tres", 2, 2)]
    finally:
        await engine.dispose()