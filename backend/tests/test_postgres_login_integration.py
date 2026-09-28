import asyncio
from hashlib import sha256
import os
from secrets import token_urlsafe
from uuid import uuid4

import jwt
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


def test_login_flow_against_postgresql(monkeypatch: pytest.MonkeyPatch) -> None:
    secret_key = token_urlsafe(48)
    monkeypatch.setenv("SECRET_KEY", secret_key)
    account_id = uuid4()
    email = f"login-check-{uuid4().hex}@example.invalid"
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
                            name="Integration",
                            surname="Temporary",
                            email=email,
                            password_hash=Argon2PasswordService().hash(password),
                            role=UserRole.ADMIN,
                            active=True,
                        )
                    )
        finally:
            await engine.dispose()

    async def assert_refresh_is_hashed(refresh_token: str) -> None:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                stored_session = await session.scalar(
                    select(RefreshSessionModel).where(
                        RefreshSessionModel.user_id == account_id
                    )
                )
            assert stored_session is not None
            assert stored_session.token_hash == sha256(refresh_token.encode()).hexdigest()
            assert stored_session.token_hash != refresh_token
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
            response = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            assert response.status_code == 200
            tokens = response.json()
            claims = jwt.decode(
                tokens["access_token"], secret_key, algorithms=["HS256"]
            )
            assert claims["sub"] == str(account_id)
            assert claims["role"] == UserRole.ADMIN.value
            assert claims["exp"] - claims["iat"] == 900
            asyncio.run(assert_refresh_is_hashed(tokens["refresh_token"]))

            rejected = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "wrong-password"},
            )
            assert rejected.status_code == 401
            assert rejected.json()["detail"]["message"] == "Credenciales inválidas"
    finally:
        asyncio.run(remove_test_user())
