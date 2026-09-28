from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.authentication import UserAccount, UserRole
from app.infrastructure.database import Base
from app.infrastructure.models import UserModel
from app.infrastructure.user_repository import SQLAlchemyUserRepository


async def test_get_by_email_maps_persisted_user_account() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    account_id = uuid4()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(
                UserModel(
                    id=account_id,
                    name="Admin",
                    surname="User",
                    email="admin@example.com",
                    password_hash="argon2-hash",
                    role=UserRole.ADMIN.value,
                    active=True,
                )
            )
            await session.commit()

            repository = SQLAlchemyUserRepository(session)
            account = await repository.get_by_email("admin@example.com")
            missing_account = await repository.get_by_email("missing@example.com")

        assert account == UserAccount(
            id=account_id,
            email="admin@example.com",
            password_hash="argon2-hash",
            role=UserRole.ADMIN,
            active=True,
        )
        assert missing_account is None
    finally:
        await engine.dispose()


async def test_database_rejects_user_with_blank_name() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(
                UserModel(
                    id=uuid4(),
                    name=" ",
                    surname="User",
                    email="admin@example.com",
                    password_hash="argon2-hash",
                    role=UserRole.ADMIN,
                    active=True,
                )
            )

            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()