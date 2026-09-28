from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.authentication import UserAccount, UserRole
from app.infrastructure.database import Base
from app.infrastructure.models import RefreshSessionModel, UserModel
from app.infrastructure.session_issuer import SQLAlchemySessionIssuer
from app.infrastructure.refresh_session_repository import SQLAlchemyRefreshSessionRepository


async def test_repository_rotates_and_revokes_refresh_family() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
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
            session.add(
                UserModel(
                    id=account.id,
                    name="Admin",
                    surname="User",
                    email=account.email,
                    password_hash=account.password_hash,
                    role=account.role,
                    active=True,
                )
            )
            await session.flush()
            issuer = SQLAlchemySessionIssuer(session, "test-only-secret-key-long-enough")
            root_tokens = await issuer.issue(account, access_ttl_seconds=900)
            root = await session.get(RefreshSessionModel, root_tokens.refresh_session_id)
            assert root is not None

            repository = SQLAlchemyRefreshSessionRepository(session)
            refresh = await repository.get_by_hash_for_update(root.token_hash)
            assert refresh is not None
            assert refresh.family_id == root.id

            successor_tokens = await issuer.issue(
                account,
                access_ttl_seconds=900,
                family_id=refresh.family_id,
            )
            await repository.mark_rotated(
                refresh.id,
                successor_tokens.refresh_session_id,
                datetime.now(UTC),
            )
            await session.commit()

            old_session = await session.get(RefreshSessionModel, root.id)
            assert old_session is not None
            assert old_session.used_at is not None
            assert old_session.revoked_at is not None
            assert old_session.replaced_by_id == successor_tokens.refresh_session_id

            await repository.revoke_family(refresh.family_id, datetime.now(UTC))
            await session.commit()
            family = (
                await session.scalars(
                    select(RefreshSessionModel).where(
                        RefreshSessionModel.family_id == refresh.family_id
                    )
                )
            ).all()

        assert len(family) == 2
        assert all(item.revoked_at is not None for item in family)
    finally:
        await engine.dispose()
