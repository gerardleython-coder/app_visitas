import asyncio
import os
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.authentication import UserAccount, UserRole
from app.infrastructure.database import create_database_engine
from app.infrastructure.models import RefreshSessionModel, UserModel
from app.infrastructure.password_service import Argon2PasswordService
from app.main import app
from app.presentation.dependencies import get_current_account, require_roles


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 to run against configured PostgreSQL",
)


def test_access_token_authentication_uses_current_postgresql_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_key = token_urlsafe(48)
    monkeypatch.setenv("SECRET_KEY", secret_key)
    account_id = uuid4()
    email = f"access-check-{uuid4().hex}@example.invalid"
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
                            surname="Access",
                            email=email,
                            password_hash=Argon2PasswordService().hash(password),
                            role=UserRole.ADMIN,
                            active=True,
                        )
                    )
        finally:
            await engine.dispose()

    async def deactivate_test_user() -> None:
        engine = create_database_engine()
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    update(UserModel)
                    .where(UserModel.id == account_id)
                    .values(active=False)
                )
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

    protected_app = FastAPI()

    @protected_app.get("/authenticated")
    async def authenticated(
        account: UserAccount = Depends(get_current_account),
    ) -> dict[str, str]:
        return {"id": str(account.id), "role": account.role.value}

    @protected_app.get("/pastor-only")
    async def pastor_only(
        account: UserAccount = Depends(require_roles(UserRole.PASTOR)),
    ) -> dict[str, str]:
        return {"id": str(account.id)}

    asyncio.run(create_test_user())
    try:
        with TestClient(app) as login_client:
            login_response = login_client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        now = datetime.now(UTC)
        stale_role_token = jwt.encode(
            {
                "sub": str(account_id),
                "role": UserRole.PASTOR.value,
                "token_type": "access",
                "iat": now,
                "exp": now + timedelta(minutes=15),
            },
            secret_key,
            algorithm="HS256",
        )

        with TestClient(protected_app) as client:
            assert client.get("/authenticated").status_code == 401
            assert client.get(
                "/authenticated", headers={"Authorization": "Bearer invalid"}
            ).status_code == 401
            assert client.get(
                "/authenticated",
                headers={"Authorization": f"Bearer {stale_role_token}"},
            ).status_code == 401

            headers = {"Authorization": f"Bearer {access_token}"}
            authenticated_response = client.get("/authenticated", headers=headers)
            assert authenticated_response.status_code == 200
            assert authenticated_response.json() == {
                "id": str(account_id),
                "role": UserRole.ADMIN.value,
            }
            assert client.get("/pastor-only", headers=headers).status_code == 403

            asyncio.run(deactivate_test_user())
            assert client.get("/authenticated", headers=headers).status_code == 401
    finally:
        asyncio.run(remove_test_user())