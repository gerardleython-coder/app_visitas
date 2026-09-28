from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authenticate_user import AuthenticateUser
from app.application.rotate_refresh_token import RotateRefreshToken
from app.infrastructure.database import create_database_engine, create_session_factory
from app.infrastructure.password_service import Argon2PasswordService
from app.infrastructure.refresh_session_repository import SQLAlchemyRefreshSessionRepository
from app.infrastructure.security_settings import SecuritySettings
from app.infrastructure.session_issuer import SQLAlchemySessionIssuer
from app.infrastructure.user_repository import SQLAlchemyUserRepository


async def get_db_session() -> AsyncIterator[AsyncSession]:
    engine = create_database_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await engine.dispose()


async def get_authenticate_user(
    session: AsyncSession = Depends(get_db_session),
) -> AuthenticateUser:
    secret_key = SecuritySettings().secret_key
    if not secret_key:
        raise RuntimeError("SECRET_KEY debe configurarse en el entorno o en backend/.env")

    return AuthenticateUser(
        users=SQLAlchemyUserRepository(session),
        passwords=Argon2PasswordService(),
        sessions=SQLAlchemySessionIssuer(session, secret_key),
    )


async def get_rotate_refresh_token(
    session: AsyncSession = Depends(get_db_session),
) -> RotateRefreshToken:
    secret_key = SecuritySettings().secret_key
    if not secret_key:
        raise RuntimeError("SECRET_KEY debe configurarse en el entorno o en backend/.env")

    return RotateRefreshToken(
        sessions=SQLAlchemyRefreshSessionRepository(session),
        users=SQLAlchemyUserRepository(session),
        issuer=SQLAlchemySessionIssuer(session, secret_key),
        unit_of_work=session,
    )