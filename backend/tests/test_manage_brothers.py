from dataclasses import dataclass, field, replace
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.application.manage_brothers import ManageBrothers
from app.domain.audit import AuditRecord
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import ForbiddenException, NotFoundException
from app.domain.operator import OperatorProfile
from app.domain.organization import Church
from app.domain.brother import BrotherProfile


@dataclass
class FakeBrotherRepository:
    brothers: dict[UUID, BrotherProfile] = field(default_factory=dict)
    assignments: list[tuple[UUID, UUID, datetime | None]] = field(default_factory=list)

    async def list_brothers(
        self,
        *,
        church_id: UUID | None = None,
        leader_id: UUID | None = None,
    ) -> list[BrotherProfile]:
        return [
            brother
            for brother in self.brothers.values()
            if (church_id is None or brother.church_id == church_id)
            and (leader_id is None or brother.leader_id == leader_id)
        ]

    async def get_brother(self, brother_id: UUID) -> BrotherProfile | None:
        return self.brothers.get(brother_id)

    async def create_brother(
        self,
        *,
        name: str,
        surname: str,
        phone: str,
        address: str,
        district_id: UUID,
        church_id: UUID,
        leader_id: UUID,
        assigned_by_id: UUID,
        assigned_at: datetime,
    ) -> BrotherProfile:
        brother = BrotherProfile(
            id=uuid4(),
            name=name,
            surname=surname,
            phone=phone,
            address=address,
            district_id=district_id,
            church_id=church_id,
            leader_id=leader_id,
            active=True,
        )
        self.brothers[brother.id] = brother
        self.assignments.append((leader_id, assigned_by_id, None))
        return brother

    async def update_brother(
        self,
        brother_id: UUID,
        changes: dict[str, object],
    ) -> BrotherProfile | None:
        brother = self.brothers.get(brother_id)
        if brother is None:
            return None
        updated = replace(brother, **changes)
        self.brothers[brother_id] = updated
        return updated

    async def deactivate_brother(
        self,
        brother_id: UUID,
        ended_at: datetime,
    ) -> BrotherProfile | None:
        brother = self.brothers.get(brother_id)
        if brother is None:
            return None
        self.brothers[brother_id] = replace(brother, active=False)
        if self.assignments:
            leader_id, actor_id, _ = self.assignments[-1]
            self.assignments[-1] = (leader_id, actor_id, ended_at)
        return self.brothers[brother_id]

    async def reassign_leader(
        self,
        brother_id: UUID,
        *,
        leader_id: UUID,
        assigned_by_id: UUID,
        assigned_at: datetime,
    ) -> BrotherProfile | None:
        brother = self.brothers.get(brother_id)
        if brother is None:
            return None
        if self.assignments:
            old_leader, old_actor, _ = self.assignments[-1]
            self.assignments[-1] = (old_leader, old_actor, assigned_at)
        self.assignments.append((leader_id, assigned_by_id, None))
        updated = replace(brother, leader_id=leader_id)
        self.brothers[brother_id] = updated
        return updated


@dataclass
class FakeOperatorRepository:
    operators: dict[UUID, OperatorProfile] = field(default_factory=dict)

    async def get_operator(self, operator_id: UUID) -> OperatorProfile | None:
        return self.operators.get(operator_id)


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


def make_operator(role: UserRole, church_id: UUID, district_id: UUID) -> OperatorProfile:
    return OperatorProfile(
        id=uuid4(),
        name="Operator",
        surname=role.value,
        email=f"{uuid4().hex}@example.test",
        role=role,
        active=True,
        district_id=district_id,
        church_id=church_id,
    )


def make_account(role: UserRole, account_id: UUID | None = None) -> UserAccount:
    return UserAccount(
        id=account_id or uuid4(),
        email=f"{uuid4().hex}@example.test",
        password_hash="test-only-hash",
        role=role,
        active=True,
    )


async def test_leader_creates_brother_assigned_to_self() -> None:
    district_id = uuid4()
    church_id = uuid4()
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    actor = make_account(UserRole.LIDER, leader.id)
    brothers = FakeBrotherRepository()
    audit = FakeAuditRepository()
    management = ManageBrothers(
        brothers=brothers,
        operators=FakeOperatorRepository({leader.id: leader}),
        churches=FakeChurchRepository(
            {church_id: Church(church_id, district_id, active=True)}
        ),
        audit=audit,
    )

    brother = await management.create_brother(
        actor,
        name="Maria",
        surname="Test",
        phone="3001112233",
        address="Address",
        district_id=district_id,
        church_id=church_id,
    )

    assert brother.leader_id == leader.id
    assert brothers.assignments == [(leader.id, actor.id, None)]
    assert audit.records[0].resource_id == brother.id
    assert audit.records[0].action == "CREADO"


async def test_leader_cannot_create_brother_for_another_leader() -> None:
    district_id = uuid4()
    church_id = uuid4()
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    other_leader = make_operator(UserRole.LIDER, church_id, district_id)
    brothers = FakeBrotherRepository()
    audit = FakeAuditRepository()
    management = ManageBrothers(
        brothers=brothers,
        operators=FakeOperatorRepository(
            {leader.id: leader, other_leader.id: other_leader}
        ),
        churches=FakeChurchRepository(
            {church_id: Church(church_id, district_id, active=True)}
        ),
        audit=audit,
    )

    with pytest.raises(ForbiddenException):
        await management.create_brother(
            make_account(UserRole.LIDER, leader.id),
            name="Maria",
            surname="Test",
            phone="3001112233",
            address="Address",
            district_id=district_id,
            church_id=church_id,
            leader_id=other_leader.id,
        )

    assert brothers.brothers == {}
    assert audit.records == []


async def test_pastor_lists_only_brothers_from_their_church() -> None:
    district_id = uuid4()
    church_id = uuid4()
    other_church_id = uuid4()
    pastor = make_operator(UserRole.PASTOR, church_id, district_id)
    actor = make_account(UserRole.PASTOR, pastor.id)
    own_brother = BrotherProfile(
        id=uuid4(),
        name="Own",
        surname="Brother",
        phone="3000000001",
        address="Address",
        district_id=district_id,
        church_id=church_id,
        leader_id=uuid4(),
        active=True,
    )
    other_brother = replace(own_brother, id=uuid4(), church_id=other_church_id)
    management = ManageBrothers(
        brothers=FakeBrotherRepository(
            brothers={own_brother.id: own_brother, other_brother.id: other_brother}
        ),
        operators=FakeOperatorRepository({pastor.id: pastor}),
        churches=FakeChurchRepository(),
        audit=FakeAuditRepository(),
    )

    result = await management.list_brothers(actor)

    assert result == [own_brother]


async def test_leader_cannot_read_brother_assigned_to_another_leader() -> None:
    district_id = uuid4()
    church_id = uuid4()
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    brother = BrotherProfile(
        id=uuid4(),
        name="Assigned",
        surname="Elsewhere",
        phone="3000000002",
        address="Address",
        district_id=district_id,
        church_id=church_id,
        leader_id=uuid4(),
        active=True,
    )
    management = ManageBrothers(
        brothers=FakeBrotherRepository({brother.id: brother}),
        operators=FakeOperatorRepository({leader.id: leader}),
        churches=FakeChurchRepository(),
        audit=FakeAuditRepository(),
    )

    with pytest.raises(NotFoundException):
        await management.get_brother(make_account(UserRole.LIDER, leader.id), brother.id)


async def test_only_admin_or_pastor_can_reassign_leader() -> None:
    district_id = uuid4()
    church_id = uuid4()
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    replacement = make_operator(UserRole.LIDER, church_id, district_id)
    brother = BrotherProfile(
        id=uuid4(),
        name="Assigned",
        surname="Brother",
        phone="3000000003",
        address="Address",
        district_id=district_id,
        church_id=church_id,
        leader_id=leader.id,
        active=True,
    )
    repository = FakeBrotherRepository(
        brothers={brother.id: brother},
        assignments=[(leader.id, uuid4(), None)],
    )
    pastor = make_operator(UserRole.PASTOR, church_id, district_id)
    operator_repository = FakeOperatorRepository(
        {leader.id: leader, replacement.id: replacement, pastor.id: pastor}
    )
    management = ManageBrothers(
        brothers=repository,
        operators=operator_repository,
        churches=FakeChurchRepository(),
        audit=FakeAuditRepository(),
    )

    with pytest.raises(ForbiddenException):
        await management.reassign_leader(
            make_account(UserRole.LIDER, leader.id),
            brother.id,
            replacement.id,
        )

    reassigned = await management.reassign_leader(
        make_account(UserRole.PASTOR, pastor.id),
        brother.id,
        replacement.id,
    )

    assert reassigned.leader_id == replacement.id
    assert repository.assignments[-1] == (replacement.id, pastor.id, None)