from dataclasses import dataclass, field, replace
from uuid import UUID, uuid4

import pytest

from app.application.manage_territories import ManageTerritories
from app.domain.audit import AuditRecord
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import (
    ConflictException,
    DomainException,
    ForbiddenException,
    NotFoundException,
)
from app.domain.organization import Church, District


@dataclass
class FakeTerritoryRepository:
    districts: dict[UUID, District] = field(default_factory=dict)
    churches: dict[UUID, Church] = field(default_factory=dict)
    active_user_church_ids: set[UUID] = field(default_factory=set)

    async def list_districts(self) -> list[District]:
        return list(self.districts.values())

    async def get_district(self, district_id: UUID) -> District | None:
        return self.districts.get(district_id)

    async def create_district(self, name: str) -> District:
        district = District(id=uuid4(), name=name)
        self.districts[district.id] = district
        return district

    async def update_district(
        self,
        district_id: UUID,
        changes: dict[str, object],
    ) -> District | None:
        district = self.districts.get(district_id)
        if district is None:
            return None
        updated = replace(district, **changes)
        self.districts[district_id] = updated
        return updated

    async def district_has_churches(self, district_id: UUID) -> bool:
        return any(church.district_id == district_id for church in self.churches.values())

    async def delete_district(self, district_id: UUID) -> bool:
        return self.districts.pop(district_id, None) is not None

    async def list_churches(self, district_id: UUID | None = None) -> list[Church]:
        return [
            church
            for church in self.churches.values()
            if district_id is None or church.district_id == district_id
        ]

    async def get_church(self, church_id: UUID) -> Church | None:
        return self.churches.get(church_id)

    async def create_church(
        self,
        *,
        district_id: UUID,
        name: str,
        address: str | None,
    ) -> Church:
        church = Church(
            id=uuid4(),
            district_id=district_id,
            name=name,
            address=address,
        )
        self.churches[church.id] = church
        return church

    async def update_church(
        self,
        church_id: UUID,
        changes: dict[str, object],
    ) -> Church | None:
        church = self.churches.get(church_id)
        if church is None:
            return None
        updated = replace(church, **changes)
        self.churches[church_id] = updated
        return updated

    async def church_has_active_users(self, church_id: UUID) -> bool:
        return church_id in self.active_user_church_ids

    async def deactivate_church(self, church_id: UUID) -> Church | None:
        church = self.churches.get(church_id)
        if church is None:
            return None
        deactivated = replace(church, active=False)
        self.churches[church_id] = deactivated
        return deactivated


@dataclass
class FakeAuditRepository:
    records: list[AuditRecord] = field(default_factory=list)

    async def record_event(self, record: AuditRecord) -> None:
        self.records.append(record)


def admin() -> UserAccount:
    return UserAccount(
        id=uuid4(),
        email="admin@example.test",
        password_hash="test-only-hash",
        role=UserRole.ADMIN,
        active=True,
    )


async def test_admin_can_create_update_list_and_delete_empty_district() -> None:
    actor = admin()
    repository = FakeTerritoryRepository()
    audit = FakeAuditRepository()
    manager = ManageTerritories(repository, audit)

    created = await manager.create_district(actor, "  Norte  ")
    updated = await manager.update_district(actor, created.id, {"name": "Norte Central"})

    assert updated is not None
    assert updated.name == "Norte Central"
    assert await manager.list_districts(actor) == [updated]
    await manager.delete_district(actor, created.id)

    assert await repository.get_district(created.id) is None
    assert [record.action for record in audit.records] == ["CREADO", "MODIFICADO", "ELIMINADO"]


async def test_district_with_churches_cannot_be_deleted() -> None:
    actor = admin()
    district = District(id=uuid4(), name="Centro")
    church = Church(id=uuid4(), district_id=district.id, name="Central")
    repository = FakeTerritoryRepository(
        districts={district.id: district},
        churches={church.id: church},
    )
    audit = FakeAuditRepository()
    manager = ManageTerritories(repository, audit)

    with pytest.raises(ConflictException, match="iglesias"):
        await manager.delete_district(actor, district.id)

    assert await repository.get_district(district.id) == district
    assert audit.records == []


async def test_admin_can_manage_churches_but_cannot_deactivate_with_active_users() -> None:
    actor = admin()
    district = District(id=uuid4(), name="Sur")
    repository = FakeTerritoryRepository(districts={district.id: district})
    audit = FakeAuditRepository()
    manager = ManageTerritories(repository, audit)

    church = await manager.create_church(
        actor,
        district_id=district.id,
        name="  Sur Central  ",
        address="  Calle 1  ",
    )
    repository.active_user_church_ids.add(church.id)
    with pytest.raises(ConflictException, match="usuarios activos"):
        await manager.delete_church(actor, church.id)
    repository.active_user_church_ids.clear()

    updated = await manager.update_church(actor, church.id, {"address": "Avenida 2"})
    deactivated = await manager.delete_church(actor, church.id)

    assert updated is not None and updated.address == "Avenida 2"
    assert deactivated.active is False
    assert await manager.list_churches(actor, district_id=district.id) == [deactivated]
    assert [record.action for record in audit.records] == ["CREADO", "MODIFICADO", "DESACTIVADO"]


async def test_non_admin_cannot_manage_territories() -> None:
    repository = FakeTerritoryRepository()
    manager = ManageTerritories(repository, FakeAuditRepository())
    pastor = UserAccount(
        id=uuid4(),
        email="pastor@example.test",
        password_hash="test-only-hash",
        role=UserRole.PASTOR,
        active=True,
    )

    with pytest.raises(ForbiddenException):
        await manager.create_district(pastor, "Unauthorized")

    assert repository.districts == {}


@pytest.mark.parametrize(
    "actor",
    [
        UserAccount(uuid4(), "leader@example.test", "hash", UserRole.LIDER, True),
        UserAccount(uuid4(), "brother@example.test", None, UserRole.HERMANO, True),
        UserAccount(uuid4(), "inactive@example.test", "hash", UserRole.ADMIN, False),
    ],
)
async def test_inactive_or_non_admin_cannot_list_territories(actor: UserAccount) -> None:
    manager = ManageTerritories(FakeTerritoryRepository(), FakeAuditRepository())

    with pytest.raises(ForbiddenException):
        await manager.list_districts(actor)


async def test_district_update_rejects_empty_unknown_and_invalid_names() -> None:
    actor = admin()
    district = District(id=uuid4(), name="North")
    repository = FakeTerritoryRepository(districts={district.id: district})
    audit = FakeAuditRepository()
    manager = ManageTerritories(repository, audit)

    for changes in ({}, {"district_id": uuid4()}, {"name": None}, {"name": "   "}, {"name": 7}):
        with pytest.raises(DomainException):
            await manager.update_district(actor, district.id, changes)

    assert await repository.get_district(district.id) == district
    assert audit.records == []


async def test_district_mutations_report_missing_resources() -> None:
    actor = admin()
    district = District(id=uuid4(), name="North")

    class VanishingDistrictRepository(FakeTerritoryRepository):
        async def update_district(
            self,
            district_id: UUID,
            changes: dict[str, object],
        ) -> District | None:
            return None

        async def delete_district(self, district_id: UUID) -> bool:
            return False

    repository = VanishingDistrictRepository(districts={district.id: district})
    manager = ManageTerritories(repository, FakeAuditRepository())

    with pytest.raises(NotFoundException):
        await manager.update_district(actor, district.id, {"name": "Renamed"})
    with pytest.raises(NotFoundException):
        await manager.delete_district(actor, district.id)
    with pytest.raises(NotFoundException):
        await manager.delete_district(actor, uuid4())


async def test_church_creation_requires_existing_district_and_nonblank_name() -> None:
    actor = admin()
    district = District(id=uuid4(), name="South")
    repository = FakeTerritoryRepository(districts={district.id: district})
    manager = ManageTerritories(repository, FakeAuditRepository())

    with pytest.raises(NotFoundException):
        await manager.create_church(
            actor,
            district_id=uuid4(),
            name="Central",
            address=None,
        )
    with pytest.raises(DomainException):
        await manager.create_church(
            actor,
            district_id=district.id,
            name="   ",
            address="   ",
        )


async def test_church_update_rejects_invalid_changes_and_inactive_churches() -> None:
    actor = admin()
    district = District(id=uuid4(), name="South")
    church = Church(id=uuid4(), district_id=district.id, name="Central")
    repository = FakeTerritoryRepository(
        districts={district.id: district},
        churches={church.id: church},
    )
    audit = FakeAuditRepository()
    manager = ManageTerritories(repository, audit)

    for changes in ({}, {"district_id": uuid4()}, {"name": None}, {"name": " "}, {"name": 7}, {"address": 7}):
        with pytest.raises(DomainException):
            await manager.update_church(actor, church.id, changes)

    repository.churches[church.id] = replace(church, active=False)
    with pytest.raises(NotFoundException):
        await manager.update_church(actor, church.id, {"name": "Renamed"})
    with pytest.raises(NotFoundException):
        await manager.update_church(actor, uuid4(), {"name": "Missing"})
    assert audit.records == []


async def test_inactive_church_delete_is_idempotent_without_duplicate_audit() -> None:
    actor = admin()
    church = Church(id=uuid4(), district_id=uuid4(), name="Closed", active=False)
    repository = FakeTerritoryRepository(churches={church.id: church})
    audit = FakeAuditRepository()

    result = await ManageTerritories(repository, audit).delete_church(actor, church.id)

    assert result == church
    assert audit.records == []