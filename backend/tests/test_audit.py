from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.audit import ListAudit
from app.domain.audit import AuditEvent, AuditRecord
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import ForbiddenException
from app.domain.operator import OperatorProfile
from app.infrastructure.database import Base
from app.infrastructure.models import ChurchModel, DistrictModel, UserModel
from app.infrastructure.audit_repository import SQLAlchemyAuditRepository


class FakeAuditRepository:
    def __init__(self) -> None:
        self.arguments: tuple[object, ...] | None = None

    async def record_event(self, record: AuditRecord) -> AuditEvent:
        raise NotImplementedError

    async def list_events(
        self,
        *,
        church_id: object,
        offset: int,
        limit: int,
    ) -> list[AuditEvent]:
        self.arguments = (church_id, offset, limit)
        return []


class FakeOperatorRepository:
    def __init__(self, profile: OperatorProfile | None) -> None:
        self.profile = profile

    async def get_operator(self, operator_id: object) -> OperatorProfile | None:
        return self.profile if self.profile and self.profile.id == operator_id else None


def account(role: UserRole, account_id: object | None = None) -> UserAccount:
    return UserAccount(
        id=account_id or uuid4(),
        email="audit@example.test",
        password_hash="test-only-hash",
        role=role,
        active=True,
    )


def profile(
    account_id: object,
    *,
    role: UserRole = UserRole.PASTOR,
    active: bool = True,
    church_id: object | None = None,
) -> OperatorProfile:
    return OperatorProfile(
        id=account_id,
        name="Pastor",
        surname="Audit",
        email="pastor@example.test",
        role=role,
        active=active,
        district_id=uuid4(),
        church_id=church_id,
    )


async def test_list_audit_uses_global_admin_scope_and_forwards_pagination() -> None:
    audit = FakeAuditRepository()
    query = ListAudit(audit, FakeOperatorRepository(None))

    await query.execute(account(UserRole.ADMIN), offset=12, limit=25)

    assert audit.arguments == (None, 12, 25)


async def test_list_audit_scopes_active_pastor_to_assigned_church() -> None:
    pastor_id = uuid4()
    church_id = uuid4()
    audit = FakeAuditRepository()
    query = ListAudit(
        audit,
        FakeOperatorRepository(profile(pastor_id, church_id=church_id)),
    )

    await query.execute(account(UserRole.PASTOR, pastor_id), offset=3, limit=10)

    assert audit.arguments == (church_id, 3, 10)


@pytest.mark.parametrize(
    "role,operator_profile",
    [
        (UserRole.LIDER, None),
        (UserRole.PASTOR, None),
        (UserRole.PASTOR, "inactive"),
        (UserRole.PASTOR, "wrong-role"),
        (UserRole.PASTOR, "unassigned"),
    ],
)
async def test_list_audit_rejects_roles_or_profiles_without_active_church(
    role: UserRole,
    operator_profile: str | None,
) -> None:
    actor_id = uuid4()
    audit = FakeAuditRepository()
    candidate = None
    if operator_profile == "inactive":
        candidate = profile(actor_id, active=False, church_id=uuid4())
    elif operator_profile == "wrong-role":
        candidate = profile(actor_id, role=UserRole.LIDER, church_id=uuid4())
    elif operator_profile == "unassigned":
        candidate = profile(actor_id, church_id=None)
    query = ListAudit(audit, FakeOperatorRepository(candidate))

    with pytest.raises(ForbiddenException):
        await query.execute(account(role, actor_id))

    assert audit.arguments is None


async def test_sqlalchemy_audit_repository_filters_orders_and_paginates() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    district_id = uuid4()
    church_a_id = uuid4()
    church_b_id = uuid4()
    actor_id = uuid4()
    base_time = datetime.now(UTC)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(DistrictModel(id=district_id, name="Audit district"))
            await session.flush()
            session.add_all(
                [
                    ChurchModel(id=church_a_id, district_id=district_id, name="Audit A"),
                    ChurchModel(id=church_b_id, district_id=district_id, name="Audit B"),
                    UserModel(
                        id=actor_id,
                        name="Audit",
                        surname="Actor",
                        email="audit-actor@example.test",
                        password_hash="test-only-hash",
                        role=UserRole.ADMIN,
                        active=True,
                    ),
                ]
            )
            await session.flush()
            repository = SQLAlchemyAuditRepository(session)
            resource_ids = [uuid4(), uuid4(), uuid4()]
            for index, (church_id, resource_id) in enumerate(
                [
                    (church_a_id, resource_ids[0]),
                    (church_b_id, resource_ids[1]),
                    (church_a_id, resource_ids[2]),
                ]
            ):
                await repository.record_event(
                    AuditRecord(
                        actor_id=actor_id,
                        resource="USUARIO",
                        resource_id=resource_id,
                        action="CREADO",
                        church_id=church_id,
                        new_values={"index": index},
                        created_at=base_time + timedelta(seconds=index),
                    )
                )

            global_page = await repository.list_events(church_id=None, offset=1, limit=1)
            church_page = await repository.list_events(
                church_id=church_a_id,
                offset=0,
                limit=1,
            )

            assert len(global_page) == 1
            assert global_page[0].resource_id == resource_ids[1]
            assert len(church_page) == 1
            assert church_page[0].resource_id == resource_ids[2]
            assert church_page[0].church_id == church_a_id
            assert church_page[0].new_values == {"index": 2}
    finally:
        await engine.dispose()