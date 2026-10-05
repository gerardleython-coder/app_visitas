import asyncio
from hashlib import sha256
import os
from secrets import token_urlsafe
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.authentication import UserRole
from app.infrastructure.database import create_database_engine
from app.infrastructure.models import RefreshSessionModel, UserModel
from app.infrastructure.password_service import Argon2PasswordService
from app.main import app


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 to run against configured PostgreSQL",
)


def test_refresh_rotation_replay_revokes_entire_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRET_KEY", token_urlsafe(48))
    account_id = uuid4()
    email = f"refresh-check-{uuid4().hex}@example.invalid"
    password = token_urlsafe(24)

    async def create_test_user() -> None:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                async with session.begin():
                    session.add(
                        UserModel(
                            id=account_id,
                            name="Refresh",
                            surname="Temporary",
                            email=email,
                            password_hash=Argon2PasswordService().hash(password),
                            role=UserRole.ADMIN,
                            active=True,
                        )
                    )
        finally:
            await engine.dispose()

    async def find_family_tokens(
        refresh_token: str,
    ) -> tuple[UUID, list[RefreshSessionModel]]:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                original = await session.scalar(
                    select(RefreshSessionModel).where(
                        RefreshSessionModel.token_hash
                        == sha256(refresh_token.encode()).hexdigest()
                    )
                )
                assert original is not None
                family = (
                    await session.scalars(
                        select(RefreshSessionModel).where(
                            RefreshSessionModel.family_id == original.family_id
                        )
                    )
                ).all()
                return original.family_id, list(family)
        finally:
            await engine.dispose()

    async def remove_test_user() -> None:
        engine = create_database_engine()
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    delete(RefreshSessionModel).where(
                        RefreshSessionModel.user_id == account_id
                    )
                )
                await connection.execute(
                    delete(UserModel).where(UserModel.id == account_id)
                )
        finally:
            await engine.dispose()

    asyncio.run(create_test_user())
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            assert login.status_code == 200
            original_refresh = login.json()["refresh_token"]

            rotated = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": original_refresh},
            )
            assert rotated.status_code == 200
            replacement_refresh = rotated.json()["refresh_token"]
            family_id, sessions = asyncio.run(find_family_tokens(original_refresh))
            assert len(sessions) == 2
            original_session = next(
                item
                for item in sessions
                if item.token_hash == sha256(original_refresh.encode()).hexdigest()
            )
            replacement_session = next(
                item
                for item in sessions
                if item.token_hash == sha256(replacement_refresh.encode()).hexdigest()
            )
            assert original_session.family_id == family_id
            assert original_session.replaced_by_id == replacement_session.id
            assert original_session.used_at is not None

            replay = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": original_refresh},
            )
            assert replay.status_code == 401

            replacement_replay = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": replacement_refresh},
            )
            assert replacement_replay.status_code == 401
            _, revoked_sessions = asyncio.run(find_family_tokens(original_refresh))
            assert all(item.revoked_at is not None for item in revoked_sessions)

            second_login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            assert second_login.status_code == 200
            logout_token = second_login.json()["refresh_token"]
            logout = client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": logout_token},
            )
            assert logout.status_code == 204
            assert logout.content == b""

            after_logout = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": logout_token},
            )
            assert after_logout.status_code == 401
            _, logout_sessions = asyncio.run(find_family_tokens(logout_token))
            assert len(logout_sessions) == 1
            assert logout_sessions[0].revoked_at is not None
    finally:
        asyncio.run(remove_test_user())
