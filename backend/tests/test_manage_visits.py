from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.manage_visits import ManageVisits
from app.application.visit_commands import CancelVisitCommand, CreateVisitCommand, UpdateVisitCommand
from app.domain.authentication import UserAccount, UserRole
from app.domain.brother import BrotherProfile
from app.domain.errors import ConflictException, DomainException, ForbiddenException, NotFoundException
from app.domain.operator import OperatorProfile
from app.domain.visit import Visit, VisitHistoryEntry, VisitStatus, VisitType


@dataclass
class FakeBrotherRepository:
    brothers: dict[UUID, BrotherProfile]

    async def get_brother(self, brother_id: UUID) -> BrotherProfile | None:
        return self.brothers.get(brother_id)


@dataclass
class FakeOperatorRepository:
    operators: dict[UUID, OperatorProfile]

    async def get_operator(self, operator_id: UUID) -> OperatorProfile | None:
        return self.operators.get(operator_id)


@dataclass
class FakeVisitRepository:
    brothers: dict[UUID, BrotherProfile]
    visits: dict[UUID, Visit] = field(default_factory=dict)
    history_entries: dict[UUID, list[VisitHistoryEntry]] = field(default_factory=dict)
    last_update: tuple[dict[str, object], UUID, str, VisitStatus | None, str | None] | None = None

    async def list_visits(
        self,
        *,
        church_id: UUID | None = None,
        leader_id: UUID | None = None,
        brother_id: UUID | None = None,
    ) -> list[Visit]:
        return [
            visit
            for visit in self.visits.values()
            if (church_id is None or visit.church_id == church_id)
            and (leader_id is None or visit.leader_id == leader_id)
            and (brother_id is None or visit.brother_id == brother_id)
        ]

    async def get_visit(self, visit_id: UUID) -> Visit | None:
        return self.visits.get(visit_id)

    async def create_visit(
        self,
        *,
        brother_id: UUID,
        leader_id: UUID,
        created_by_id: UUID,
        visit_type: VisitType,
        scheduled_at: datetime,
        duration_minutes: int,
        location: str,
        observations: str,
        created_at: datetime,
    ) -> Visit:
        brother = self.brothers[brother_id]
        visit = Visit(
            id=uuid4(),
            brother_id=brother_id,
            leader_id=leader_id,
            church_id=brother.church_id,
            created_by_id=created_by_id,
            visit_type=visit_type,
            scheduled_at=scheduled_at,
            completed_at=None,
            duration_minutes=duration_minutes,
            location=location,
            observations=observations,
            status=VisitStatus.PROGRAMADA,
            cancellation_reason=None,
            created_at=created_at,
            updated_at=created_at,
        )
        self.visits[visit.id] = visit
        return visit

    async def update_visit(
        self,
        visit_id: UUID,
        *,
        changes,
        actor_id: UUID,
        action: str,
        occurred_at: datetime,
        new_status: VisitStatus | None = None,
        completed_at: datetime | None = None,
        cancellation_reason: str | None = None,
    ) -> Visit | None:
        visit = self.visits.get(visit_id)
        if visit is None:
            return None
        normalized = {
            key: value.value if isinstance(value, VisitType) else value
            for key, value in changes.items()
        }
        if "visit_type" in normalized:
            normalized["visit_type"] = VisitType(normalized["visit_type"])
        updated = replace(
            visit,
            **normalized,
            status=new_status or visit.status,
            completed_at=completed_at or visit.completed_at,
            cancellation_reason=cancellation_reason,
            updated_at=occurred_at,
        )
        self.visits[visit_id] = updated
        self.last_update = (dict(changes), actor_id, action, new_status, cancellation_reason)
        return updated

    async def list_history(self, visit_id: UUID) -> list[VisitHistoryEntry]:
        return self.history_entries.get(visit_id, [])


def make_account(role: UserRole, account_id: UUID | None = None) -> UserAccount:
    return UserAccount(
        id=account_id or uuid4(),
        email=f"{uuid4().hex}@example.test",
        password_hash="test-hash",
        role=role,
        active=True,
    )


def make_operator(
    role: UserRole,
    church_id: UUID,
    district_id: UUID,
    *,
    active: bool = True,
) -> OperatorProfile:
    return OperatorProfile(
        id=uuid4(),
        name="Test",
        surname=role.value,
        email=f"{uuid4().hex}@example.test",
        role=role,
        active=active,
        district_id=district_id,
        church_id=church_id,
    )


def make_brother(
    church_id: UUID,
    district_id: UUID,
    leader_id: UUID,
    *,
    active: bool = True,
) -> BrotherProfile:
    return BrotherProfile(
        id=uuid4(),
        name="Maria",
        surname="Test",
        phone="3001112233",
        address="Address",
        district_id=district_id,
        church_id=church_id,
        leader_id=leader_id,
        active=active,
    )


def make_visit(
    brother: BrotherProfile,
    leader_id: UUID,
    *,
    status: VisitStatus = VisitStatus.PROGRAMADA,
    scheduled_at: datetime | None = None,
) -> Visit:
    now = datetime.now(UTC)
    return Visit(
        id=uuid4(),
        brother_id=brother.id,
        leader_id=leader_id,
        church_id=brother.church_id,
        created_by_id=uuid4(),
        visit_type=VisitType.ENSENANZA,
        scheduled_at=scheduled_at or now + timedelta(hours=1),
        completed_at=now if status is VisitStatus.COMPLETADA else None,
        duration_minutes=30,
        location="Address",
        observations="Notes",
        status=status,
        cancellation_reason="Reason" if status is VisitStatus.CANCELADA else None,
        created_at=now,
        updated_at=now,
    )


def make_manager(
    actor: UserAccount,
    brother_profiles: list[BrotherProfile],
    operator_profiles: list[OperatorProfile],
    visits: list[Visit] | None = None,
) -> tuple[ManageVisits, FakeVisitRepository]:
    brothers_by_id = {brother.id: brother for brother in brother_profiles}
    visit_repository = FakeVisitRepository(
        brothers=brothers_by_id,
        visits={visit.id: visit for visit in visits or []},
    )
    manager = ManageVisits(
        visits=visit_repository,
        brothers=FakeBrotherRepository(brothers_by_id),
        operators=FakeOperatorRepository(
            {operator.id: operator for operator in operator_profiles}
        ),
    )
    return manager, visit_repository


def create_command(actor: UserAccount, brother_id: UUID, scheduled_at: datetime | None = None):
    return CreateVisitCommand(
        actor=actor,
        brother_id=brother_id,
        visit_type=VisitType.EVANGELISMO,
        scheduled_at=scheduled_at or datetime.now(UTC) + timedelta(hours=2),
        duration_minutes=45,
        location="  Home  ",
        observations="  Follow up  ",
    )


async def test_admin_creates_visit_and_normalizes_required_text() -> None:
    church_id = uuid4()
    district_id = uuid4()
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    brother = make_brother(church_id, district_id, leader.id)
    admin = make_account(UserRole.ADMIN)
    manager, _ = make_manager(admin, [brother], [leader])

    visit = await manager.create(create_command(admin, brother.id))

    assert visit.status is VisitStatus.PROGRAMADA
    assert visit.leader_id == leader.id
    assert visit.created_by_id == admin.id
    assert visit.location == "Home"
    assert visit.observations == "Follow up"


async def test_pastor_can_create_only_for_brother_in_their_church() -> None:
    district_id = uuid4()
    church_id = uuid4()
    other_church_id = uuid4()
    pastor = make_operator(UserRole.PASTOR, church_id, district_id)
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    brother = make_brother(church_id, district_id, leader.id)
    foreign_brother = make_brother(other_church_id, district_id, uuid4())
    actor = make_account(UserRole.PASTOR, pastor.id)
    manager, _ = make_manager(actor, [brother, foreign_brother], [pastor, leader])

    assert (await manager.create(create_command(actor, brother.id))).brother_id == brother.id
    with pytest.raises(NotFoundException):
        await manager.create(create_command(actor, foreign_brother.id))


async def test_leader_can_create_only_for_assigned_brothers() -> None:
    district_id = uuid4()
    church_id = uuid4()
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    other_leader = make_operator(UserRole.LIDER, church_id, district_id)
    assigned = make_brother(church_id, district_id, leader.id)
    unassigned = make_brother(church_id, district_id, other_leader.id)
    actor = make_account(UserRole.LIDER, leader.id)
    manager, _ = make_manager(actor, [assigned, unassigned], [leader, other_leader])

    assert (await manager.create(create_command(actor, assigned.id))).leader_id == leader.id
    with pytest.raises(NotFoundException):
        await manager.create(create_command(actor, unassigned.id))


@pytest.mark.parametrize(
    "command_changes",
    [
        {"scheduled_at": datetime.now(UTC) - timedelta(minutes=1)},
        {"scheduled_at": datetime.now()},
        {"duration_minutes": 0},
        {"location": "   "},
        {"observations": "   "},
    ],
)
async def test_create_rejects_invalid_visit_data(command_changes: dict[str, object]) -> None:
    church_id = uuid4()
    district_id = uuid4()
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    brother = make_brother(church_id, district_id, leader.id)
    admin = make_account(UserRole.ADMIN)
    manager, repository = make_manager(admin, [brother], [leader])
    command = replace(create_command(admin, brother.id), **command_changes)

    with pytest.raises(DomainException):
        await manager.create(command)
    assert repository.visits == {}


async def test_create_rejects_inactive_brother_or_leader() -> None:
    district_id = uuid4()
    church_id = uuid4()
    leader = make_operator(UserRole.LIDER, church_id, district_id, active=False)
    brother = make_brother(church_id, district_id, leader.id)
    admin = make_account(UserRole.ADMIN)
    manager, _ = make_manager(admin, [brother], [leader])

    with pytest.raises(DomainException, match="líder activo"):
        await manager.create(create_command(admin, brother.id))


async def test_lider_lists_only_own_visits_and_cannot_read_history() -> None:
    district_id = uuid4()
    church_id = uuid4()
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    other_leader = make_operator(UserRole.LIDER, church_id, district_id)
    brother = make_brother(church_id, district_id, leader.id)
    other_brother = make_brother(church_id, district_id, other_leader.id)
    own_visit = make_visit(brother, leader.id)
    other_visit = make_visit(other_brother, other_leader.id)
    actor = make_account(UserRole.LIDER, leader.id)
    manager, _ = make_manager(
        actor,
        [brother, other_brother],
        [leader, other_leader],
        [own_visit, other_visit],
    )

    assert await manager.list_visits(actor) == [own_visit]
    with pytest.raises(NotFoundException):
        await manager.get(actor, other_visit.id)
    with pytest.raises(ForbiddenException):
        await manager.history(actor, own_visit.id)


async def test_reschedule_records_command_and_keeps_status_programada() -> None:
    church_id = uuid4()
    district_id = uuid4()
    pastor = make_operator(UserRole.PASTOR, church_id, district_id)
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    brother = make_brother(church_id, district_id, leader.id)
    visit = make_visit(brother, leader.id)
    actor = make_account(UserRole.PASTOR, pastor.id)
    manager, repository = make_manager(actor, [brother], [pastor, leader], [visit])
    new_date = datetime.now(UTC) + timedelta(days=1)

    updated = await manager.update(
        UpdateVisitCommand(actor, visit.id, {"scheduled_at": new_date})
    )

    assert updated.scheduled_at == new_date
    assert updated.status is VisitStatus.PROGRAMADA
    assert repository.last_update is not None
    assert repository.last_update[2] == "REPROGRAMADA"


async def test_only_due_programada_visit_can_be_completed() -> None:
    church_id = uuid4()
    district_id = uuid4()
    pastor = make_operator(UserRole.PASTOR, church_id, district_id)
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    brother = make_brother(church_id, district_id, leader.id)
    future_visit = make_visit(brother, leader.id)
    actor = make_account(UserRole.PASTOR, pastor.id)
    manager, repository = make_manager(
        actor,
        [brother],
        [pastor, leader],
        [future_visit],
    )

    with pytest.raises(DomainException, match="visita futura"):
        await manager.update(
            UpdateVisitCommand(actor, future_visit.id, {"status": VisitStatus.COMPLETADA})
        )
    assert repository.last_update is None

    due_visit = replace(
        future_visit,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    repository.visits[due_visit.id] = due_visit
    completed = await manager.update(
        UpdateVisitCommand(actor, due_visit.id, {"status": VisitStatus.COMPLETADA})
    )
    assert completed.status is VisitStatus.COMPLETADA
    assert completed.completed_at is not None
    assert repository.last_update is not None
    assert repository.last_update[2] == "COMPLETADA"


async def test_cancel_requires_reason_and_only_programada_state() -> None:
    church_id = uuid4()
    district_id = uuid4()
    admin = make_account(UserRole.ADMIN)
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    brother = make_brother(church_id, district_id, leader.id)
    scheduled = make_visit(brother, leader.id)
    completed = make_visit(brother, leader.id, status=VisitStatus.COMPLETADA)
    cancelled = make_visit(brother, leader.id, status=VisitStatus.CANCELADA)
    manager, repository = make_manager(
        admin,
        [brother],
        [leader],
        [scheduled, completed, cancelled],
    )

    with pytest.raises(DomainException, match="motivo"):
        await manager.cancel(CancelVisitCommand(admin, scheduled.id, "   "))
    with pytest.raises(ConflictException):
        await manager.cancel(CancelVisitCommand(admin, completed.id, "Reason"))
    with pytest.raises(ConflictException):
        await manager.cancel(CancelVisitCommand(admin, cancelled.id, "Reason"))

    result = await manager.cancel(CancelVisitCommand(admin, scheduled.id, "Not available"))
    assert result.status is VisitStatus.CANCELADA
    assert result.cancellation_reason == "Not available"
    assert repository.last_update is not None
    assert repository.last_update[2] == "CANCELADA"


async def test_completed_visit_is_admin_only_and_cannot_be_rescheduled() -> None:
    church_id = uuid4()
    district_id = uuid4()
    admin = make_account(UserRole.ADMIN)
    pastor = make_operator(UserRole.PASTOR, church_id, district_id)
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    brother = make_brother(church_id, district_id, leader.id)
    completed = make_visit(brother, leader.id, status=VisitStatus.COMPLETADA)
    pastor_actor = make_account(UserRole.PASTOR, pastor.id)
    manager, _ = make_manager(
        pastor_actor,
        [brother],
        [pastor, leader],
        [completed],
    )

    with pytest.raises(ForbiddenException):
        await manager.update(
            UpdateVisitCommand(pastor_actor, completed.id, {"observations": "Edit"})
        )

    admin_manager, _ = make_manager(admin, [brother], [leader], [completed])
    with pytest.raises(ConflictException):
        await admin_manager.update(
            UpdateVisitCommand(
                admin,
                completed.id,
                {"scheduled_at": datetime.now(UTC) + timedelta(days=1)},
            )
        )
    assert (await admin_manager.update(
        UpdateVisitCommand(admin, completed.id, {"observations": "Admin edit"})
    )).observations == "Admin edit"


async def test_history_is_visible_to_admin_and_pastor_only_in_scope() -> None:
    district_id = uuid4()
    church_id = uuid4()
    other_church_id = uuid4()
    admin = make_account(UserRole.ADMIN)
    pastor = make_operator(UserRole.PASTOR, church_id, district_id)
    foreign_pastor = make_operator(UserRole.PASTOR, other_church_id, district_id)
    leader = make_operator(UserRole.LIDER, church_id, district_id)
    brother = make_brother(church_id, district_id, leader.id)
    visit = make_visit(brother, leader.id)
    entry = VisitHistoryEntry(
        id=uuid4(),
        visit_id=visit.id,
        actor_id=admin.id,
        action="CREADA",
        previous_status=None,
        new_status=VisitStatus.PROGRAMADA,
        previous_scheduled_at=None,
        new_scheduled_at=visit.scheduled_at,
        previous_values=None,
        new_values={"location": visit.location},
        reason=None,
        created_at=visit.created_at,
    )
    admin_manager, admin_repo = make_manager(admin, [brother], [leader], [visit])
    admin_repo.history_entries[visit.id] = [entry]
    pastor_manager, pastor_repo = make_manager(
        make_account(UserRole.PASTOR, pastor.id),
        [brother],
        [pastor, leader],
        [visit],
    )
    pastor_repo.history_entries[visit.id] = [entry]
    foreign_manager, _ = make_manager(
        make_account(UserRole.PASTOR, foreign_pastor.id),
        [brother],
        [foreign_pastor, leader],
        [visit],
    )

    assert await admin_manager.history(admin, visit.id) == [entry]
    pastor_actor = make_account(UserRole.PASTOR, pastor.id)
    assert await pastor_manager.history(pastor_actor, visit.id) == [entry]
    with pytest.raises(NotFoundException):
        await foreign_manager.history(make_account(UserRole.PASTOR, foreign_pastor.id), visit.id)