from dataclasses import dataclass, field, replace
from uuid import UUID, uuid4

import pytest

from app.application.manage_operators import OperatorManagement
from app.domain.audit import AuditRecord
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import (
    ConflictException,
    DomainException,
    ForbiddenException,
    NotFoundException,
)
from app.domain.operator import OperatorProfile
from app.domain.organization import Church


@dataclass
class FakeOperatorRepository:
    profiles: dict[UUID, OperatorProfile] = field(default_factory=dict)
    church_ids: set[UUID] = field(default_factory=set)

    async def list_operators(
        self,
        role: UserRole,
        *,
        church_id: UUID | None = None,
    ) -> list[OperatorProfile]:
        return [
            profile
            for profile in self.profiles.values()
            if profile.role is role and (church_id is None or profile.church_id == church_id)
        ]

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

    async def lock_church(self, church_id: UUID) -> bool:
        return church_id in self.church_ids

    async def has_active_primary_pastor(
        self,
        church_id: UUID,
        *,
        excluding_id: UUID,
    ) -> bool:
        return any(
            profile.id != excluding_id
            and profile.church_id == church_id
            and profile.role is UserRole.PASTOR
            and profile.active
            and profile.is_primary_pastor
            for profile in self.profiles.values()
        )

    async def set_primary_pastor(
        self,
        church_id: UUID,
        pastor_id: UUID,
    ) -> OperatorProfile | None:
        for profile_id, profile in list(self.profiles.items()):
            if profile.church_id == church_id and profile.role is UserRole.PASTOR:
                self.profiles[profile_id] = replace(
                    profile,
                    is_primary_pastor=profile_id == pastor_id,
                )
        return self.profiles.get(pastor_id)

    async def deactivate_operator(self, operator_id: UUID) -> OperatorProfile | None:
        profile = self.profiles.get(operator_id)
        if profile is None:
            return None
        deactivated = replace(profile, active=False, is_primary_pastor=False)
        self.profiles[operator_id] = deactivated
        return deactivated


@dataclass
class FakeChurchRepository:
    churches: dict[UUID, Church] = field(default_factory=dict)

    async def get_by_id(self, church_id: UUID) -> Church | None:
        return self.churches.get(church_id)


@dataclass
class FakeAuditRepository:
    records: list[AuditRecord] = field(default_factory=list)

    async def record_event(self, record: AuditRecord) -> None:
        self.records.append(record)


def operator(
    *,
    role: UserRole,
    church_id: UUID,
    is_primary_pastor: bool = False,
) -> OperatorProfile:
    return OperatorProfile(
        id=uuid4(),
        name="Test",
        surname=role.value,
        email=f"{uuid4().hex}@example.test",
        role=role,
        active=True,
        district_id=uuid4(),
        church_id=church_id,
        is_primary_pastor=is_primary_pastor,
    )


def account(role: UserRole, user_id: UUID | None = None) -> UserAccount:
    return UserAccount(
        id=user_id or uuid4(),
        email=f"{uuid4().hex}@example.test",
        password_hash="test-only-hash",
        role=role,
        active=True,
    )


async def test_pastor_lists_only_leaders_from_their_church() -> None:
    church_id = uuid4()
    other_church_id = uuid4()
    pastor = operator(role=UserRole.PASTOR, church_id=church_id)
    assigned_leader = operator(role=UserRole.LIDER, church_id=church_id)
    other_leader = operator(role=UserRole.LIDER, church_id=other_church_id)
    repository = FakeOperatorRepository(
        profiles={
            pastor.id: pastor,
            assigned_leader.id: assigned_leader,
            other_leader.id: other_leader,
        }
    )
    management = OperatorManagement(repository, FakeChurchRepository(), FakeAuditRepository())

    result = await management.list_operators(
        account(UserRole.PASTOR, pastor.id),
        UserRole.LIDER,
    )

    assert result == [assigned_leader]


async def test_pastor_cannot_list_or_edit_pastors() -> None:
    church_id = uuid4()
    pastor = operator(role=UserRole.PASTOR, church_id=church_id)
    other_pastor = operator(role=UserRole.PASTOR, church_id=church_id)
    repository = FakeOperatorRepository(
        profiles={pastor.id: pastor, other_pastor.id: other_pastor}
    )
    management = OperatorManagement(repository, FakeChurchRepository(), FakeAuditRepository())
    actor = account(UserRole.PASTOR, pastor.id)

    with pytest.raises(ForbiddenException):
        await management.list_operators(actor, UserRole.PASTOR)
    with pytest.raises(ForbiddenException):
        await management.update_operator(
            actor,
            other_pastor.id,
            UserRole.PASTOR,
            {"name": "Changed"},
        )


async def test_pastor_cannot_edit_leader_from_another_church() -> None:
    pastor = operator(role=UserRole.PASTOR, church_id=uuid4())
    other_leader = operator(role=UserRole.LIDER, church_id=uuid4())
    repository = FakeOperatorRepository(
        profiles={pastor.id: pastor, other_leader.id: other_leader}
    )
    management = OperatorManagement(repository, FakeChurchRepository(), FakeAuditRepository())

    with pytest.raises(NotFoundException):
        await management.update_operator(
            account(UserRole.PASTOR, pastor.id),
            other_leader.id,
            UserRole.LIDER,
            {"surname": "Changed"},
        )


async def test_sole_primary_pastor_requires_replacement_before_deactivation() -> None:
    church_id = uuid4()
    primary = operator(
        role=UserRole.PASTOR,
        church_id=church_id,
        is_primary_pastor=True,
    )
    replacement = operator(role=UserRole.PASTOR, church_id=church_id)
    repository = FakeOperatorRepository(
        profiles={primary.id: primary, replacement.id: replacement},
        church_ids={church_id},
    )
    audit = FakeAuditRepository()
    management = OperatorManagement(
        repository,
        FakeChurchRepository({church_id: Church(church_id, uuid4())}),
        audit,
    )
    admin = account(UserRole.ADMIN)

    with pytest.raises(ConflictException, match="otro pastor principal"):
        await management.deactivate_operator(admin, primary.id, UserRole.PASTOR)

    await management.set_primary_pastor(admin, church_id, replacement.id)
    deactivated = await management.deactivate_operator(admin, primary.id, UserRole.PASTOR)

    assert deactivated.active is False
    assert deactivated.is_primary_pastor is False
    assert repository.profiles[replacement.id].is_primary_pastor is True
    assert [event.action for event in audit.records] == [
        "PASTOR_PRINCIPAL_ASIGNADO",
        "DESACTIVADO",
    ]


async def test_admin_cannot_assign_pastor_from_another_church_as_primary() -> None:
    church_id = uuid4()
    pastor = operator(role=UserRole.PASTOR, church_id=uuid4())
    repository = FakeOperatorRepository(
        profiles={pastor.id: pastor},
        church_ids={church_id},
    )
    management = OperatorManagement(
        repository,
        FakeChurchRepository({church_id: Church(church_id, uuid4())}),
        FakeAuditRepository(),
    )

    with pytest.raises(NotFoundException):
        await management.set_primary_pastor(
            account(UserRole.ADMIN),
            church_id,
            pastor.id,
        )


async def test_operator_listing_rejects_invalid_role_and_unassigned_pastor() -> None:
    repository = FakeOperatorRepository()
    management = OperatorManagement(repository, FakeChurchRepository(), FakeAuditRepository())

    with pytest.raises(DomainException):
        await management.list_operators(account(UserRole.ADMIN), UserRole.HERMANO)
    with pytest.raises(ForbiddenException):
        await management.list_operators(account(UserRole.PASTOR), UserRole.LIDER)

    unassigned_pastor = replace(operator(role=UserRole.PASTOR, church_id=uuid4()), church_id=None)
    repository.profiles[unassigned_pastor.id] = unassigned_pastor
    with pytest.raises(ForbiddenException):
        await management.list_operators(
            account(UserRole.PASTOR, unassigned_pastor.id),
            UserRole.LIDER,
        )


async def test_operator_update_rejects_invalid_fields_inactive_and_missing_target() -> None:
    target = operator(role=UserRole.LIDER, church_id=uuid4())

    class VanishingOperatorRepository(FakeOperatorRepository):
        async def update_operator(
            self,
            operator_id: UUID,
            changes: dict[str, object],
        ) -> OperatorProfile | None:
            return None

    repository = VanishingOperatorRepository(profiles={target.id: target})
    audit = FakeAuditRepository()
    management = OperatorManagement(repository, FakeChurchRepository(), audit)
    admin = account(UserRole.ADMIN)

    for changes in ({}, {"role": UserRole.ADMIN}):
        with pytest.raises(DomainException):
            await management.update_operator(admin, target.id, UserRole.LIDER, changes)
    with pytest.raises(NotFoundException):
        await management.update_operator(admin, target.id, UserRole.LIDER, {"name": "Updated"})

    repository.profiles[target.id] = replace(target, active=False)
    with pytest.raises(NotFoundException):
        await management.update_operator(admin, target.id, UserRole.LIDER, {"name": "Updated"})
    assert audit.records == []


async def test_operator_deactivation_is_idempotent_and_requires_existing_church_lock() -> None:
    church_id = uuid4()
    inactive_leader = replace(
        operator(role=UserRole.LIDER, church_id=church_id),
        active=False,
    )
    primary_pastor = operator(
        role=UserRole.PASTOR,
        church_id=church_id,
        is_primary_pastor=True,
    )
    repository = FakeOperatorRepository(
        profiles={inactive_leader.id: inactive_leader, primary_pastor.id: primary_pastor}
    )
    audit = FakeAuditRepository()
    management = OperatorManagement(repository, FakeChurchRepository(), audit)

    result = await management.deactivate_operator(
        account(UserRole.ADMIN),
        inactive_leader.id,
        UserRole.LIDER,
    )
    assert result == inactive_leader
    with pytest.raises(NotFoundException):
        await management.deactivate_operator(
            account(UserRole.ADMIN),
            primary_pastor.id,
            UserRole.PASTOR,
        )
    assert audit.records == []


async def test_pastor_cannot_deactivate_a_leader_in_their_church() -> None:
    church_id = uuid4()
    pastor = operator(role=UserRole.PASTOR, church_id=church_id)
    leader = operator(role=UserRole.LIDER, church_id=church_id)
    repository = FakeOperatorRepository(profiles={pastor.id: pastor, leader.id: leader})
    audit = FakeAuditRepository()
    management = OperatorManagement(repository, FakeChurchRepository(), audit)

    with pytest.raises(ForbiddenException):
        await management.deactivate_operator(
            account(UserRole.PASTOR, pastor.id),
            leader.id,
            UserRole.LIDER,
        )

    assert repository.profiles[leader.id] == leader
    assert audit.records == []


async def test_setting_primary_pastor_rejects_non_admin_and_inactive_church() -> None:
    church_id = uuid4()
    pastor = operator(role=UserRole.PASTOR, church_id=church_id)
    repository = FakeOperatorRepository(profiles={pastor.id: pastor}, church_ids={church_id})
    management = OperatorManagement(
        repository,
        FakeChurchRepository({church_id: Church(church_id, uuid4(), active=False)}),
        FakeAuditRepository(),
    )

    with pytest.raises(ForbiddenException):
        await management.set_primary_pastor(account(UserRole.PASTOR), church_id, pastor.id)
    with pytest.raises(NotFoundException):
        await management.set_primary_pastor(account(UserRole.ADMIN), church_id, pastor.id)