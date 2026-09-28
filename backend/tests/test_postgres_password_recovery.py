import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
import os
from secrets import token_urlsafe
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.authentication import UserRole
from app.domain.password_recovery import PasswordResetEmail
from app.infrastructure.database import create_database_engine
from app.infrastructure.models import (
    PasswordRecoveryTokenModel,
    RefreshSessionModel,
    UserModel,
)
from app.infrastructure.password_service import Argon2PasswordService
from app.main import app
from app.presentation.dependencies import get_password_reset_email_sender


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 to run against configured PostgreSQL",
)


@dataclass
class FakePasswordResetEmailSender:
    sent: list[PasswordResetEmail] = field(default_factory=list)

    async def send_password_reset(self, recovery_email: PasswordResetEmail) -> None:
        self.sent.append(recovery_email)


def test_postgres_password_recovery_is_neutral_one_time_and_revokes_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRET_KEY", token_urlsafe(48))
    user_id = uuid4()
    email = f"hu08-{uuid4().hex}@example.invalid"
    original_password = token_urlsafe(24)
    new_password = token_urlsafe(24)
    sender = FakePasswordResetEmailSender()
    app.dependency_overrides[get_password_reset_email_sender] = lambda: sender

    async def create_test_user() -> None:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                async with session.begin():
                    session.add(
                        UserModel(
                            id=user_id,
                            name="Password",
                            surname="Recovery",
                            email=email,
                            password_hash=Argon2PasswordService().hash(original_password),
                            role=UserRole.ADMIN,
                            active=True,
                        )
                    )
        finally:
            await engine.dispose()

    async def inspect_recovery_and_session(
        raw_token: str,
        refresh_token: str,
    ) -> tuple[PasswordRecoveryTokenModel | None, RefreshSessionModel | None, UserModel | None]:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                recovery = await session.scalar(
                    select(PasswordRecoveryTokenModel).where(
                        PasswordRecoveryTokenModel.user_id == user_id
                    )
                )
                refresh_session = await session.scalar(
                    select(RefreshSessionModel).where(
                        RefreshSessionModel.token_hash
                        == sha256(refresh_token.encode("utf-8")).hexdigest()
                    )
                )
                user = await session.get(UserModel, user_id)
                if recovery is not None:
                    assert recovery.token_hash == sha256(raw_token.encode("utf-8")).hexdigest()
                    assert raw_token != recovery.token_hash
                return recovery, refresh_session, user
        finally:
            await engine.dispose()

    async def cleanup() -> None:
        engine = create_database_engine()
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    delete(PasswordRecoveryTokenModel).where(
                        PasswordRecoveryTokenModel.user_id == user_id
                    )
                )
                await connection.execute(
                    delete(RefreshSessionModel).where(RefreshSessionModel.user_id == user_id)
                )
                await connection.execute(delete(UserModel).where(UserModel.id == user_id))
        finally:
            await engine.dispose()

    asyncio.run(create_test_user())
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": original_password},
            )
            assert login.status_code == 200
            original_refresh = login.json()["refresh_token"]

            unknown = client.post(
                "/api/v1/auth/password/forgot",
                json={"email": "unknown@example.invalid"},
            )
            known = client.post(
                "/api/v1/auth/password/forgot",
                json={"email": email},
            )
            assert unknown.status_code == known.status_code == 202
            assert unknown.content == known.content == b""
            assert len(sender.sent) == 1
            reset_token = sender.sent[0].token
            assert reset_token.encode("utf-8") not in known.content

            recovery, old_session, _ = asyncio.run(
                inspect_recovery_and_session(reset_token, original_refresh)
            )
            assert recovery is not None
            assert recovery.used_at is None
            assert recovery.expires_at > datetime.now(UTC)
            assert old_session is not None
            assert old_session.revoked_at is None

            reset = client.post(
                "/api/v1/auth/password/reset",
                json={"token": reset_token, "new_password": new_password},
            )
            assert reset.status_code == 204
            assert reset.content == b""

            _, revoked_session, user = asyncio.run(
                inspect_recovery_and_session(reset_token, original_refresh)
            )
            assert revoked_session is not None
            assert revoked_session.revoked_at is not None
            assert user is not None
            assert user.password_hash is not None
            assert user.password_hash != original_password
            assert Argon2PasswordService().verify(new_password, user.password_hash)

            replay = client.post(
                "/api/v1/auth/password/reset",
                json={"token": reset_token, "new_password": token_urlsafe(24)},
            )
            assert replay.status_code == 400

            old_login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": original_password},
            )
            new_login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": new_password},
            )
            assert old_login.status_code == 401
            assert new_login.status_code == 200
    finally:
        app.dependency_overrides.pop(get_password_reset_email_sender, None)
        asyncio.run(cleanup())