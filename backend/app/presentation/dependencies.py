from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authenticate_user import AuthenticateUser
from app.application.audit import ListAudit
from app.application.manage_brothers import ManageBrothers
from app.application.create_operator import CreateOperator
from app.application.manage_operators import OperatorManagement
from app.application.manage_visits import ManageVisits
from app.application.logout_user import LogoutUser
from app.application.rotate_refresh_token import RotateRefreshToken
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import UnauthorizedException
from app.infrastructure.access_token_verifier import AccessTokenVerifier
from app.infrastructure.audit_repository import SQLAlchemyAuditRepository
from app.infrastructure.brother_repository import SQLAlchemyBrotherRepository
from app.infrastructure.database import create_database_engine, create_session_factory
from app.infrastructure.organization_repository import (
    SQLAlchemyChurchRepository,
    SQLAlchemyOperatorRepository,
)
from app.infrastructure.password_service import Argon2PasswordService
from app.infrastructure.refresh_session_repository import SQLAlchemyRefreshSessionRepository
from app.infrastructure.security_settings import SecuritySettings
from app.infrastructure.session_issuer import SQLAlchemySessionIssuer
from app.infrastructure.user_repository import SQLAlchemyUserRepository
from app.infrastructure.visit_repository import SQLAlchemyVisitRepository

bearer_scheme = HTTPBearer(auto_error=False)


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


async def get_logout_user(
    session: AsyncSession = Depends(get_db_session),
) -> LogoutUser:
    return LogoutUser(SQLAlchemyRefreshSessionRepository(session))


async def get_create_operator(
    session: AsyncSession = Depends(get_db_session),
) -> CreateOperator:
    return CreateOperator(
        churches=SQLAlchemyChurchRepository(session),
        operators=SQLAlchemyOperatorRepository(session),
        passwords=Argon2PasswordService(),
        audit=SQLAlchemyAuditRepository(session),
    )


async def get_operator_management(
    session: AsyncSession = Depends(get_db_session),
) -> OperatorManagement:
    return OperatorManagement(
        operators=SQLAlchemyOperatorRepository(session),
        churches=SQLAlchemyChurchRepository(session),
        audit=SQLAlchemyAuditRepository(session),
    )


async def get_current_account(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> UserAccount:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Autenticación requerida"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret_key = SecuritySettings().secret_key
    if not secret_key:
        raise RuntimeError("SECRET_KEY debe configurarse en el entorno o en backend/.env")

    try:
        claims = AccessTokenVerifier(secret_key).verify(credentials.credentials)
    except UnauthorizedException as error:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Token de acceso inválido"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    account = await SQLAlchemyUserRepository(session).get_by_id(claims.user_id)
    if (
        account is None
        or not account.active
        or account.role is UserRole.HERMANO
        or account.role is not claims.role
    ):
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Token de acceso inválido"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return account


def require_roles(*allowed_roles: UserRole) -> Callable[..., Awaitable[UserAccount]]:
    if not allowed_roles:
        raise ValueError("Debe especificarse al menos un rol permitido")

    async def check_role(
        account: UserAccount = Depends(get_current_account),
    ) -> UserAccount:
        if account.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail={"code": "forbidden", "message": "Permisos insuficientes"},
            )
        return account

    return check_role


async def get_brother_management(
    session: AsyncSession = Depends(get_db_session),
) -> ManageBrothers:
    return ManageBrothers(
        brothers=SQLAlchemyBrotherRepository(session),
        operators=SQLAlchemyOperatorRepository(session),
        churches=SQLAlchemyChurchRepository(session),
        audit=SQLAlchemyAuditRepository(session),
    )


async def get_visit_management(
    session: AsyncSession = Depends(get_db_session),
) -> ManageVisits:
    return ManageVisits(
        visits=SQLAlchemyVisitRepository(session),
        brothers=SQLAlchemyBrotherRepository(session),
        operators=SQLAlchemyOperatorRepository(session),
    )


async def get_audit_query(
    session: AsyncSession = Depends(get_db_session),
) -> ListAudit:
    return ListAudit(
        audit=SQLAlchemyAuditRepository(session),
        operators=SQLAlchemyOperatorRepository(session),
    )
