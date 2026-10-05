from dataclasses import dataclass, field, replace
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.application.manage_administrators import (
    AdministratorManagement,
    BootstrapAdministrator,
)
from app.domain.audit import AuditRecord
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import (
    ConflictException,
    DomainException,
    ForbiddenException,
    NotFoundException,
)
from app.domain.operator import OperatorProfile


@dataclass
class FakeAdministratorRepository:
    profiles: dict[UUID, OperatorProfile] = field(default_factory=dict)
    bootstrap_locks: int = 0
    admin_locks: int = 0

    async def lock_bootstrap(self) -> None:
        self.bootstrap_locks += 1

    async def count_administrators(self) -> int:
        return sum(profile.role is UserRole.ADMIN for profile in self.profiles.values())

    async def create_administrator(
        self,
        *,
        name: str,
        surname: str,
        email: str,
        password_hash: str,
    ) -> UserAccount:
        account = UserAccount(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            role=UserRole.ADMIN,
            active=True,
        )
        self.profiles[account.id] = OperatorProfile(
            id=account.id,
            name=name,
            surname=surname,
            email=email,
            role=UserRole.ADMIN,
            active=True,
            district_id=None,
            church_id=None,
        )
        return account

    async def list_administrators(self) -> list[OperatorProfile]:
        return sorted(
            (item for item in self.profiles.values() if item.role is UserRole.ADMIN),
            key=lambda item: item.email,
        )

    async def get_operator(self, operator_id: UUID) -> OperatorProfile | None:
        return self.profiles.get(operator_id)

    async def update_operator(
        self,
        operator_id: UUID,
        changes: dict[str, object],
    ) -> OperatorProfile | None:
        profile = self.profiles.get(operator_id)
        if profile is None:
            return None
        updated = replace(profile, **changes)
        self.profiles[operator_id] = updated
        return updated

    async def lock_administrators(self) -> None:
        self.admin_locks += 1

    async def has_active_administrator(self, *, excluding_id: UUID) -> bool:
        return any(
            profile.role is UserRole.ADMIN
            and profile.active
            and profile.id != excluding_id
            for profile in self.profiles.values()
        )

    async def deactivate_operator(self, operator_id: UUID) -> OperatorProfile | None:
        profile = self.profiles.get(operator_id)
        if profile is None:
            return None
        inactive = replace(profile, active=False)
        self.profiles[operator_id] = inactive
        return inactive

    async def activate_operator(self, operator_id: UUID) -> OperatorProfile | None:
        profile = self.profiles.get(operator_id)
        if profile is None:
            return None
        active = replace(profile, active=True)
        self.profiles[operator_id] = active
        return active


@dataclass
class FakeAuditRepository:
    records: list[AuditRecord] = field(default_factory=list)

    async def record_event(self, record: AuditRecord) -> None:
        self.records.append(record)


@dataclass
class FakePasswordHasher:
    async def unused(self) -> None:
        return None

    def hash(self, password: str) -> str:
        return f"hashed:{password}"


@dataclass
class FakeRefreshSessions:
    revoked: list[tuple[UUID, datetime]] = field(default_factory=list)

    async def revoke_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        self.revoked.append((user_id, revoked_at))


def account(role: UserRole, user_id: UUID | None = None) -> UserAccount:
    return UserAccount(
        id=user_id or uuid4(),
        email=f"{uuid4().hex}@example.test",
        password_hash="test-only-hash",
        role=role,
        active=True,
    )


def administrator(
    *,
    active: bool = True,
    admin_id: UUID | None = None,
) -> OperatorProfile:
    return OperatorProfile(
        id=admin_id or uuid4(),
        name="Ana",
        surname="Admin",
        email=f"{uuid4().hex}@example.test",
        role=UserRole.ADMIN,
        active=active,
        district_id=None,
        church_id=None,
    )


async def test_bootstrap_creates_and_audits_first_admin_without_territory_or_secrets() -> None:
    repository = FakeAdministratorRepository()
    audit = FakeAuditRepository()
    use_case = BootstrapAdministrator(repository, FakePasswordHasher(), audit)

    created = await use_case.execute(
        name="Ana",
        surname="Admin",
        email="ana@example.test",
        password="a-private-password",
    )

    assert created.role is UserRole.ADMIN
    assert created.active is True
    profile = repository.profiles[created.id]
    assert profile.district_id is None
    assert profile.church_id is None
    assert repository.bootstrap_locks == 1
    assert audit.records[0].actor_id == created.id
    assert audit.records[0].resource == "USUARIO"
    assert audit.records[0].action == "ADMIN_INICIAL_CREADO"
    assert "password" not in str(audit.records[0].new_values).lower()
    assert "hash" not in str(audit.records[0].new_values).lower()


@pytest.mark.parametrize("active", [True, False])
async def test_bootstrap_rejects_when_any_admin_already_exists(active: bool) -> None:
    existing = administrator(active=active)
    repository = FakeAdministratorRepository(profiles={existing.id: existing})
    use_case = BootstrapAdministrator(
        repository,
        FakePasswordHasher(),
        FakeAuditRepository(),
    )

    with pytest.raises(ConflictException):
        await use_case.execute(
            name="Other",
            surname="Admin",
            email="other@example.test",
            password="another-private-password",
        )

    assert repository.bootstrap_locks == 1
    assert len(repository.profiles) == 1


async def test_admin_can_list_create_and_update_other_admins() -> None:
    actor = account(UserRole.ADMIN)
    repository = FakeAdministratorRepository()
    audit = FakeAuditRepository()
    management = AdministratorManagement(
        repository,
        FakePasswordHasher(),
        audit,
        FakeRefreshSessions(),
    )

    created = await management.create(
        actor,
        name="Luis",
        surname="Admin",
        email="luis@example.test",
        password="another-private-password",
    )
    listed = await management.list(actor)
    updated = await management.update(actor, created.id, {"name": "Luis Alberto"})

    assert listed == [created]
    assert updated.name == "Luis Alberto"
    assert updated.district_id is None
    assert updated.church_id is None
    assert [record.action for record in audit.records] == ["CREADO", "MODIFICADO"]


@pytest.mark.parametrize(
    "operation",
    ["list", "create", "update", "deactivate", "reactivate"],
)
async def test_non_admin_cannot_manage_admin_accounts(operation: str) -> None:
    actor = account(UserRole.PASTOR)
    target = administrator()
    repository = FakeAdministratorRepository(profiles={target.id: target})
    management = AdministratorManagement(
        repository,
        FakePasswordHasher(),
        FakeAuditRepository(),
        FakeRefreshSessions(),
    )

    async def invoke() -> object:
        if operation == "list":
            return await management.list(actor)
        if operation == "create":
            return await management.create(
                actor,
                name="Other",
                surname="Admin",
                email="other@example.test",
                password="another-private-password",
            )
        if operation == "update":
            return await management.update(actor, target.id, {"name": "Changed"})
        if operation == "reactivate":
            return await management.reactivate(actor, target.id)
        return await management.deactivate(actor, target.id)

    with pytest.raises(ForbiddenException):
        await invoke()

    assert repository.profiles[target.id] == target


async def test_admin_cannot_deactivate_self_or_the_last_active_admin() -> None:
    sole = administrator()
    repository = FakeAdministratorRepository(profiles={sole.id: sole})
    sessions = FakeRefreshSessions()
    audit = FakeAuditRepository()
    management = AdministratorManagement(
        repository,
        FakePasswordHasher(),
        audit,
        sessions,
    )
    actor = account(UserRole.ADMIN, sole.id)

    with pytest.raises(ConflictException, match="sí mismo"):
        await management.deactivate(actor, sole.id)

    sole_target = administrator()
    repository = FakeAdministratorRepository(profiles={sole_target.id: sole_target})
    management = AdministratorManagement(
        repository,
        FakePasswordHasher(),
        audit,
        sessions,
    )
    with pytest.raises(ConflictException, match="último ADMIN"):
        await management.deactivate(actor, sole_target.id)

    assert repository.profiles[sole_target.id].active is True
    assert sessions.revoked == []
    assert audit.records == []


async def test_admin_deactivation_is_logical_audited_and_revokes_refresh_sessions() -> None:
    actor_profile = administrator()
    target = administrator()
    repository = FakeAdministratorRepository(
        profiles={actor_profile.id: actor_profile, target.id: target}
    )
    sessions = FakeRefreshSessions()
    audit = FakeAuditRepository()
    management = AdministratorManagement(
        repository,
        FakePasswordHasher(),
        audit,
        sessions,
    )

    deactivated = await management.deactivate(
        account(UserRole.ADMIN, actor_profile.id), target.id
    )

    assert deactivated.active is False
    assert repository.admin_locks == 1
    assert sessions.revoked[0][0] == target.id
    assert sessions.revoked[0][1].tzinfo is not None
    assert audit.records[0].actor_id == actor_profile.id
    assert audit.records[0].resource_id == target.id
    assert audit.records[0].action == "DESACTIVADO"


async def test_admin_can_reactivate_another_inactive_admin_and_audit_it() -> None:
    actor = administrator()
    target = administrator(active=False)
    repository = FakeAdministratorRepository(
        profiles={actor.id: actor, target.id: target}
    )
    audit = FakeAuditRepository()
    management = AdministratorManagement(
        repository,
        FakePasswordHasher(),
        audit,
        FakeRefreshSessions(),
    )

    reactivated = await management.reactivate(
        account(UserRole.ADMIN, actor.id),
        target.id,
    )

    assert reactivated.active is True
    assert repository.admin_locks == 1
    assert audit.records[0].actor_id == actor.id
    assert audit.records[0].resource_id == target.id
    assert audit.records[0].action == "REACTIVADO"
    assert audit.records[0].previous_values["active"] is False
    assert audit.records[0].new_values["active"] is True


async def test_reactivating_active_admin_is_idempotent_without_extra_audit() -> None:
    actor = administrator()
    target = administrator()
    repository = FakeAdministratorRepository(
        profiles={actor.id: actor, target.id: target}
    )
    audit = FakeAuditRepository()
    management = AdministratorManagement(
        repository,
        FakePasswordHasher(),
        audit,
        FakeRefreshSessions(),
    )

    reactivated = await management.reactivate(
        account(UserRole.ADMIN, actor.id),
        target.id,
    )

    assert reactivated == target
    assert audit.records == []


async def test_admin_update_rejects_unknown_fields_missing_and_inactive_accounts() -> None:
    inactive = administrator(active=False)
    repository = FakeAdministratorRepository(profiles={inactive.id: inactive})
    management = AdministratorManagement(
        repository,
        FakePasswordHasher(),
        FakeAuditRepository(),
        FakeRefreshSessions(),
    )
    actor = account(UserRole.ADMIN)

    with pytest.raises(DomainException):
        await management.update(actor, inactive.id, {"role": UserRole.ADMIN})
    with pytest.raises(NotFoundException):
        await management.update(actor, inactive.id, {"name": "Updated"})
    with pytest.raises(NotFoundException):
        await management.update(actor, uuid4(), {"name": "Updated"})