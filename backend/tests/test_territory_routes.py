from dataclasses import dataclass, field
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.domain.authentication import UserAccount, UserRole
from app.domain.organization import Church, District
from app.main import app
from app.presentation.dependencies import get_current_account, get_territory_management


@dataclass
class FakeTerritoryManagement:
    districts: list[District] = field(default_factory=list)
    churches: list[Church] = field(default_factory=list)

    async def list_districts(self, _actor: UserAccount) -> list[District]:
        return self.districts

    async def create_district(self, _actor: UserAccount, name: str) -> District:
        district = District(uuid4(), name)
        self.districts.append(district)
        return district

    async def update_district(
        self,
        _actor: UserAccount,
        district_id: UUID,
        changes: dict[str, object],
    ) -> District:
        district = next(item for item in self.districts if item.id == district_id)
        updated = District(district.id, str(changes.get("name", district.name)))
        self.districts[self.districts.index(district)] = updated
        return updated

    async def delete_district(self, _actor: UserAccount, district_id: UUID) -> None:
        self.districts = [item for item in self.districts if item.id != district_id]

    async def list_churches(
        self,
        _actor: UserAccount,
        *,
        district_id: UUID | None = None,
    ) -> list[Church]:
        return [
            church
            for church in self.churches
            if district_id is None or church.district_id == district_id
        ]

    async def create_church(
        self,
        _actor: UserAccount,
        *,
        district_id: UUID,
        name: str,
        address: str | None,
    ) -> Church:
        church = Church(uuid4(), district_id, True, name, address)
        self.churches.append(church)
        return church

    async def update_church(
        self,
        _actor: UserAccount,
        church_id: UUID,
        changes: dict[str, object],
    ) -> Church:
        church = next(item for item in self.churches if item.id == church_id)
        updated = Church(
            church.id,
            church.district_id,
            church.active,
            str(changes.get("name", church.name)),
            changes.get("address", church.address),
        )
        self.churches[self.churches.index(church)] = updated
        return updated

    async def delete_church(self, _actor: UserAccount, church_id: UUID) -> Church:
        church = next(item for item in self.churches if item.id == church_id)
        deactivated = Church(
            church.id,
            church.district_id,
            False,
            church.name,
            church.address,
        )
        self.churches[self.churches.index(church)] = deactivated
        return deactivated


def account(role: UserRole) -> UserAccount:
    return UserAccount(
        id=uuid4(),
        email=f"{role.value.lower()}@example.test",
        password_hash="test-only-hash",
        role=role,
        active=True,
    )


def test_admin_can_create_list_update_and_delete_territories() -> None:
    admin = account(UserRole.ADMIN)
    management = FakeTerritoryManagement()
    app.dependency_overrides[get_current_account] = lambda: admin
    app.dependency_overrides[get_territory_management] = lambda: management
    try:
        with TestClient(app) as client:
            district = client.post("/api/v1/admin/distritos", json={"name": "North"})
            assert district.status_code == 201
            district_id = district.json()["id"]
            assert client.get("/api/v1/admin/distritos").json()[0]["name"] == "North"
            assert client.patch(
                f"/api/v1/admin/distritos/{district_id}",
                json={"name": "North Central"},
            ).json()["name"] == "North Central"

            church = client.post(
                "/api/v1/admin/iglesias",
                json={"district_id": district_id, "name": "Central", "address": "Street"},
            )
            assert church.status_code == 201
            church_id = church.json()["id"]
            assert client.get(
                "/api/v1/admin/iglesias",
                params={"district_id": district_id},
            ).json()[0]["id"] == church_id
            assert client.patch(
                f"/api/v1/admin/iglesias/{church_id}",
                json={"address": "New Street"},
            ).json()["address"] == "New Street"
            assert client.delete(f"/api/v1/admin/iglesias/{church_id}").status_code == 204
            assert client.delete(f"/api/v1/admin/distritos/{district_id}").status_code == 204
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        app.dependency_overrides.pop(get_territory_management, None)


def test_only_admin_can_manage_territories() -> None:
    app.dependency_overrides[get_current_account] = lambda: account(UserRole.PASTOR)
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/admin/distritos")
    finally:
        app.dependency_overrides.pop(get_current_account, None)

    assert response.status_code == 403