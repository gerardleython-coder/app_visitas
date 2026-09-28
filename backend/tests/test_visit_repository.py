from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.authentication import UserRole
from app.domain.visit import VisitStatus, VisitType
from app.infrastructure.database import Base
from app.infrastructure.models import (
    ChurchModel,
    DistrictModel,
    UserModel,
    VisitModel,
)
from app.infrastructure.visit_repository import SQLAlchemyVisitRepository


async def test_visit_repository_writes_state_and_history_atomically() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    district_id = uuid4()
    church_id = uuid4()
    other_church_id = uuid4()
    leader_id = uuid4()
    other_leader_id = uuid4()
    brother_id = uuid4()
    other_brother_id = uuid4()
    admin_id = uuid4()
    scheduled_at = datetime.now(UTC) + timedelta(days=1)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(DistrictModel(id=district_id, name="Visit district"))
            await session.flush()
            session.add_all(
                [
                    ChurchModel(id=church_id, district_id=district_id, name="Visit church"),
                    ChurchModel(
                        id=other_church_id,
                        district_id=district_id,
                        name="Other visit church",
                    ),
                ]
            )
            await session.flush()
            session.add_all(
                [
                    UserModel(
                        id=leader_id,
                        district_id=district_id,
                        church_id=church_id,
                        name="Leader",
                        surname="A",
                        email="visit-leader-a@example.test",
                        password_hash="test-hash",
                        role=UserRole.LIDER,
                        active=True,
                    ),
                    UserModel(
                        id=other_leader_id,
                        district_id=district_id,
                        church_id=other_church_id,
                        name="Leader",
                        surname="B",
                        email="visit-leader-b@example.test",
                        password_hash="test-hash",
                        role=UserRole.LIDER,
                        active=True,
                    ),
                    UserModel(
                        id=brother_id,
                        district_id=district_id,
                        church_id=church_id,
                        leader_id=leader_id,
                        name="Brother",
                        surname="A",
                        phone="3001112233",
                        address="Address A",
                        role=UserRole.HERMANO,
                        active=True,
                    ),
                    UserModel(
                        id=other_brother_id,
                        district_id=district_id,
                        church_id=other_church_id,
                        leader_id=other_leader_id,
                        name="Brother",
                        surname="B",
                        phone="3001112234",
                        address="Address B",
                        role=UserRole.HERMANO,
                        active=True,
                    ),
                    UserModel(
                        id=admin_id,
                        name="Admin",
                        surname="Visit",
                        email="visit-admin@example.test",
                        password_hash="test-hash",
                        role=UserRole.ADMIN,
                        active=True,
                    ),
                ]
            )
            await session.flush()

            repository = SQLAlchemyVisitRepository(session)
            created_at = datetime.now(UTC)
            visit = await repository.create_visit(
                brother_id=brother_id,
                leader_id=leader_id,
                created_by_id=admin_id,
                visit_type=VisitType.CUIDADO_PASTORAL,
                scheduled_at=scheduled_at,
                duration_minutes=45,
                location="Home",
                observations="Initial visit",
                created_at=created_at,
            )
            visit_id = visit.id

            assert visit.status is VisitStatus.PROGRAMADA
            assert visit.church_id == church_id
            with pytest.raises(IntegrityError):
                async with session.begin_nested():
                    session.add(
                        VisitModel(
                            brother_id=brother_id,
                            leader_id=leader_id,
                            created_by_id=admin_id,
                            visit_type=VisitType.EVANGELISMO.value,
                            scheduled_at=scheduled_at,
                            duration_minutes=30,
                            location="Other home",
                            observations="Duplicate",
                            status=VisitStatus.PROGRAMADA.value,
                        )
                    )
                    await session.flush()

            loaded_visit = await repository.get_visit(visit_id)
            assert loaded_visit is not None
            assert loaded_visit.id == visit.id
            assert loaded_visit.scheduled_at.replace(tzinfo=UTC) == scheduled_at
            assert await repository.get_visit(uuid4()) is None
            assert await repository.list_visits(church_id=other_church_id) == []
            assert await repository.list_visits(leader_id=other_leader_id) == []
            assert await repository.list_visits(brother_id=other_brother_id) == []
            church_visits = await repository.list_visits(church_id=church_id)
            assert len(church_visits) == 1
            assert church_visits[0].id == visit_id
            assert church_visits[0].status is VisitStatus.PROGRAMADA

            initial_history = await repository.list_history(visit_id)
            assert len(initial_history) == 1
            assert initial_history[0].action == "CREADA"
            assert initial_history[0].actor_id == admin_id
            assert initial_history[0].new_values == {
                "visit_type": VisitType.CUIDADO_PASTORAL.value,
                "duration_minutes": 45,
                "location": "Home",
                "observations": "Initial visit",
                "brother_id": str(brother_id),
                "leader_id": str(leader_id),
            }

            rescheduled_at = scheduled_at + timedelta(days=1)
            rescheduled_at_time = datetime.now(UTC)
            rescheduled = await repository.update_visit(
                visit_id,
                changes={"scheduled_at": rescheduled_at},
                actor_id=leader_id,
                action="REPROGRAMADA",
                occurred_at=rescheduled_at_time,
            )
            assert rescheduled is not None
            assert rescheduled.scheduled_at == rescheduled_at

            completed_at = datetime.now(UTC)
            completed = await repository.update_visit(
                visit_id,
                changes={},
                actor_id=leader_id,
                action="COMPLETADA",
                occurred_at=completed_at,
                new_status=VisitStatus.COMPLETADA,
                completed_at=completed_at,
            )
            assert completed is not None
            assert completed.status is VisitStatus.COMPLETADA
            assert completed.completed_at == completed_at

            history = await repository.list_history(visit_id)
            entries_by_action = {entry.action: entry for entry in history}
            assert set(entries_by_action) == {"CREADA", "REPROGRAMADA", "COMPLETADA"}
            reschedule_entry = entries_by_action["REPROGRAMADA"]
            assert reschedule_entry.previous_scheduled_at is not None
            assert reschedule_entry.previous_scheduled_at.replace(tzinfo=UTC) == scheduled_at
            assert reschedule_entry.new_scheduled_at is not None
            assert reschedule_entry.new_scheduled_at.replace(tzinfo=UTC) == rescheduled_at
            completion_entry = entries_by_action["COMPLETADA"]
            assert completion_entry.previous_status is VisitStatus.PROGRAMADA
            assert completion_entry.new_status is VisitStatus.COMPLETADA
            await session.commit()

            rows = await session.scalars(
                select(VisitModel).where(VisitModel.brother_id == brother_id)
            )
            assert len(rows.all()) == 1
    finally:
        await engine.dispose()