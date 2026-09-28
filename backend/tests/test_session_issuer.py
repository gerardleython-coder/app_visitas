from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.authentication import UserAccount, UserRole
from app.application.authenticate_user import SessionTokens
from app.infrastructure.database import Base
from app.infrastructure.models import RefreshSessionModel
from app.infrastructure.session_issuer import SQLAlchemySessionIssuer


async def test_session_issuer_signs_short_access_token_and_hashes_refresh_token() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    secret_key = "test-only-secret-key-with-enough-entropy"
    account = UserAccount(
        id=uuid4(),
        email="admin@example.test",
        password_hash="argon2-hash",
        role=UserRole.ADMIN,
        active=True,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            tokens = await SQLAlchemySessionIssuer(session, secret_key).issue(
                account,
                access_ttl_seconds=900,
            )
            stored_session = await session.scalar(
                select(RefreshSessionModel).where(
                    RefreshSessionModel.user_id == account.id
                )
            )

        assert isinstance(tokens, SessionTokens)
        claims = jwt.decode(tokens.access_token, secret_key, algorithms=["HS256"])
        assert claims["sub"] == str(account.id)
        assert claims["role"] == UserRole.ADMIN.value
        assert claims["token_type"] == "access"
        assert claims["exp"] - claims["iat"] == 900
        assert stored_session is not None
        assert stored_session.token_hash == sha256(tokens.refresh_token.encode()).hexdigest()
        assert stored_session.token_hash != tokens.refresh_token
        assert tokens.refresh_session_id == stored_session.id
        assert stored_session.family_id == stored_session.id
        expiry = stored_session.expires_at.replace(tzinfo=UTC)
        assert expiry > datetime.now(UTC)
    finally:
        await engine.dispose()


async def test_session_issuer_keeps_refresh_token_in_existing_family() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    account = UserAccount(
        id=uuid4(),
        email="admin@example.test",
        password_hash="argon2-hash",
        role=UserRole.ADMIN,
        active=True,
    )
    family_id = uuid4()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            tokens = await SQLAlchemySessionIssuer(
                session,
                "test-only-signing-key-with-at-least-32-bytes",
            ).issue(
                account,
                access_ttl_seconds=900,
                family_id=family_id,
            )
            stored_session = await session.scalar(
                select(RefreshSessionModel).where(
                    RefreshSessionModel.id == tokens.refresh_session_id
                )
            )

        assert stored_session is not None
        assert stored_session.family_id == family_id
    finally:
        await engine.dispose()
