from uuid import uuid4

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.authentication import UserRole
from app.infrastructure.database import Base
from app.infrastructure.models import DistrictModel, UserModel
from app.infrastructure.territory_repository import SQLAlchemyTerritoryRepository


async def test_territory_repository_persists_crud_and_dependency_checks() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    district_id = uuid4()
    user_id = uuid4()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            repository = SQLAlchemyTerritoryRepository(session)
            created_district = await repository.create_district("North")
            assert created_district.name == "North"
            assert await repository.get_district(created_district.id) == created_district
            assert await repository.list_districts() == [created_district]

            updated_district = await repository.update_district(
                created_district.id,
                {"name": "North District"},
            )
            assert updated_district is not None
            assert updated_district.name == "North District"

            session.add(DistrictModel(id=district_id, name="South District"))
            await session.flush()
            created_church = await repository.create_church(
                district_id=district_id,
                name="South Church",
                address="First Street",
            )
            assert created_church.address == "First Street"
            assert await repository.get_church(created_church.id) == created_church
            assert await repository.list_churches(district_id=district_id) == [created_church]
            assert await repository.district_has_churches(district_id) is True

            updated_church = await repository.update_church(
                created_church.id,
                {"address": "Second Street"},
            )
            assert updated_church is not None
            assert updated_church.address == "Second Street"

            session.add(
                UserModel(
                    id=user_id,
                    district_id=district_id,
                    church_id=created_church.id,
                    name="Leader",
                    surname="Active",
                    email="active-leader@example.test",
                    password_hash="test-only-hash",
                    role=UserRole.LIDER,
                    active=True,
                )
            )
            await session.flush()
            assert await repository.church_has_active_users(created_church.id) is True
            persisted_user = await session.get(UserModel, user_id)
            assert persisted_user is not None
            persisted_user.active = False
            await session.flush()
            assert await repository.church_has_active_users(created_church.id) is False

            deactivated = await repository.deactivate_church(created_church.id)
            assert deactivated is not None
            assert deactivated.active is False
            await session.commit()
    finally:
        await engine.dispose()