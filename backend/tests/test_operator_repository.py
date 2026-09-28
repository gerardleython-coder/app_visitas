from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.authentication import UserRole
from app.infrastructure.database import Base
from app.infrastructure.models import ChurchModel, DistrictModel, UserModel
from app.infrastructure.organization_repository import (
    SQLAlchemyChurchRepository,
    SQLAlchemyOperatorRepository,
)


async def test_operator_repository_persists_territorial_assignment() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    district_id = uuid4()
    church_id = uuid4()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(DistrictModel(id=district_id, name="Distrito Centro"))
            await session.flush()
            session.add(
                ChurchModel(
                    id=church_id,
                    district_id=district_id,
                    name="Iglesia Central",
                )
            )
            await session.commit()

            church = await SQLAlchemyChurchRepository(session).get_by_id(church_id)
            account = await SQLAlchemyOperatorRepository(session).create_operator(
                name="Ana",
                surname="Gomez",
                email="ana@example.test",
                password_hash="argon2-test-hash",
                role=UserRole.LIDER,
                district_id=district_id,
                church_id=church_id,
            )
            await session.commit()
            persisted_user = await session.scalar(
                select(UserModel).where(UserModel.id == account.id)
            )

        assert church is not None
        assert church.district_id == district_id
        assert account.role is UserRole.LIDER
        assert account.active is True
        assert persisted_user is not None
        assert persisted_user.district_id == district_id
        assert persisted_user.church_id == church_id
        assert persisted_user.password_hash == "argon2-test-hash"
    finally:
        await engine.dispose()


async def test_database_rejects_operator_with_mismatched_district_and_church() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    selected_district_id = uuid4()
    church_district_id = uuid4()
    church_id = uuid4()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add_all(
                [
                    DistrictModel(id=selected_district_id, name="Distrito A"),
                    DistrictModel(id=church_district_id, name="Distrito B"),
                ]
            )
            await session.flush()
            session.add(
                ChurchModel(
                    id=church_id,
                    district_id=church_district_id,
                    name="Iglesia B",
                )
            )
            await session.commit()

            with pytest.raises(IntegrityError):
                async with session.begin():
                    session.add(
                        UserModel(
                            name="Ana",
                            surname="Gomez",
                            email="ana@example.test",
                            password_hash="argon2-test-hash",
                            role=UserRole.LIDER,
                            district_id=selected_district_id,
                            church_id=church_id,
                        )
                    )
                    await session.flush()
    finally:
        await engine.dispose()
