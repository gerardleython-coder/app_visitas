from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.authentication import UserRole
from app.infrastructure.brother_repository import SQLAlchemyBrotherRepository
from app.infrastructure.database import Base
from app.infrastructure.models import (
    BrotherAssignmentModel,
    ChurchModel,
    DistrictModel,
    UserModel,
)


async def test_brother_repository_preserves_assignment_history_and_soft_delete() -> None:
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
    replacement_leader_id = uuid4()
    admin_id = uuid4()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(DistrictModel(id=district_id, name="Brother repository district"))
            await session.flush()
            session.add_all(
                [
                    ChurchModel(
                        id=church_id,
                        district_id=district_id,
                        name="Brother repository church",
                    ),
                    ChurchModel(
                        id=other_church_id,
                        district_id=district_id,
                        name="Brother repository other church",
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
                        surname="One",
                        email="brother-repository-leader@example.test",
                        password_hash="test-hash",
                        role=UserRole.LIDER,
                        active=True,
                    ),
                    UserModel(
                        id=replacement_leader_id,
                        district_id=district_id,
                        church_id=church_id,
                        name="Leader",
                        surname="Two",
                        email="brother-repository-leader-two@example.test",
                        password_hash="test-hash",
                        role=UserRole.LIDER,
                        active=True,
                    ),
                    UserModel(
                        id=uuid4(),
                        district_id=district_id,
                        church_id=other_church_id,
                        name="Leader",
                        surname="Foreign",
                        email="brother-repository-foreign@example.test",
                        password_hash="test-hash",
                        role=UserRole.LIDER,
                        active=True,
                    ),
                    UserModel(
                        id=admin_id,
                        name="Admin",
                        surname="Actor",
                        email="brother-repository-admin@example.test",
                        password_hash="test-hash",
                        role=UserRole.ADMIN,
                        active=True,
                    ),
                ]
            )
            await session.flush()

            repository = SQLAlchemyBrotherRepository(session)
            assigned_at = datetime.now(UTC)
            created = await repository.create_brother(
                name="Maria",
                surname="Test",
                phone="3001112233",
                address="Address",
                district_id=district_id,
                church_id=church_id,
                leader_id=leader_id,
                assigned_by_id=admin_id,
                assigned_at=assigned_at,
            )
            assert created.active is True
            assert await repository.get_brother(created.id) == created
            assert await repository.get_brother(uuid4()) is None
            assert await repository.list_brothers(church_id=other_church_id) == []
            assert await repository.list_brothers(leader_id=replacement_leader_id) == []
            assert await repository.list_brothers() == [created]

            updated = await repository.update_brother(
                created.id,
                {"phone": "3009998877", "address": "Updated address"},
            )
            assert updated is not None
            assert updated.phone == "3009998877"
            assert updated.address == "Updated address"

            reassigned_at = assigned_at + timedelta(seconds=1)
            reassigned = await repository.reassign_leader(
                created.id,
                leader_id=replacement_leader_id,
                assigned_by_id=admin_id,
                assigned_at=reassigned_at,
            )
            assert reassigned is not None
            assert reassigned.leader_id == replacement_leader_id

            assignments = list(
                (
                    await session.scalars(
                        select(BrotherAssignmentModel)
                        .where(BrotherAssignmentModel.brother_id == created.id)
                        .order_by(BrotherAssignmentModel.assigned_at)
                    )
                ).all()
            )
            assert len(assignments) == 2
            assert assignments[0].leader_id == leader_id
            assert assignments[0].ended_at is not None
            assert assignments[0].ended_at.replace(tzinfo=UTC) == reassigned_at
            assert assignments[1].leader_id == replacement_leader_id
            assert assignments[1].assigned_by_id == admin_id
            assert assignments[1].ended_at is None

            deactivated_at = reassigned_at + timedelta(seconds=1)
            deactivated = await repository.deactivate_brother(created.id, deactivated_at)
            assert deactivated is not None
            assert deactivated.active is False
            assert await repository.deactivate_brother(created.id, deactivated_at) == deactivated
            assert await repository.update_brother(created.id, {"phone": "3000000000"}) is None
            assert (
                await repository.reassign_leader(
                    created.id,
                    leader_id=leader_id,
                    assigned_by_id=admin_id,
                    assigned_at=deactivated_at + timedelta(seconds=1),
                )
                is None
            )

            assignments = list(
                (
                    await session.scalars(
                        select(BrotherAssignmentModel)
                        .where(BrotherAssignmentModel.brother_id == created.id)
                        .order_by(BrotherAssignmentModel.assigned_at)
                    )
                ).all()
            )
            assert assignments[-1].ended_at == deactivated_at
            await session.commit()
    finally:
        await engine.dispose()