from dataclasses import dataclass, field, replace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.domain.authentication import UserAccount, UserRole
from app.domain.operator import OperatorProfile
from app.main import app
from app.presentation.dependencies import (
    get_administrator_management,
    get_bootstrap_administrator,
    get_current_account,
)


def account(role: UserRole = UserRole.ADMIN) -> UserAccount:
    return UserAccount(
        id=uuid4(),
        email=f"{uuid4().hex}@example.test",
        password_hash="test-only-hash",
        role=role,
        active=True,
    )


def profile(
    administrator_id: UUID | None = None,
    *,
    name: str = "Ana",
    active: bool = True,
) -> OperatorProfile:
    return OperatorProfile(
        id=administrator_id or uuid4(),
        name=name,
        surname="Admin",
        email=f"{uuid4().hex}@example.test",
        role=UserRole.ADMIN,
        active=active,
        district_id=None,
        church_id=None,
    )


@dataclass
class FakeAdministratorManagement:
    profiles: dict[UUID, OperatorProfile] = field(default_factory=dict)

    async def list(self, _actor: UserAccount) -> list[OperatorProfile]:
        return list(self.profiles.values())

    async def create(
        self,
        _actor: UserAccount,
        *,
        name: str,
        surname: str,
        email: str,
        password: str,
    ) -> OperatorProfile:
        assert password
        created = OperatorProfile(
            id=uuid4(),
            name=name,
            surname=surname,
            email=email,
            role=UserRole.ADMIN,
            active=True,
            district_id=None,
            church_id=None,
        )
        self.profiles[created.id] = created
        return created

    async def update(
        self,
        _actor: UserAccount,
        administrator_id: UUID,
        changes: dict[str, object],
    ) -> OperatorProfile:
        updated = replace(self.profiles[administrator_id], **changes)
        self.profiles[administrator_id] = updated
        return updated

    async def deactivate(
        self,
        _actor: UserAccount,
        administrator_id: UUID,
    ) -> OperatorProfile:
        deactivated = replace(self.profiles[administrator_id], active=False)
        self.profiles[administrator_id] = deactivated
        return deactivated

    async def reactivate(
        self,
        _actor: UserAccount,
        administrator_id: UUID,
    ) -> OperatorProfile:
        reactivated = replace(self.profiles[administrator_id], active=True)
        self.profiles[administrator_id] = reactivated
        return reactivated


@dataclass
class FakeBootstrapAdministrator:
    created: list[UserAccount] = field(default_factory=list)

    async def execute(
        self,
        *,
        name: str,
        surname: str,
        email: str,
        password: str,
    ) -> UserAccount:
        assert name and surname and email and password
        administrator = UserAccount(
            id=uuid4(),
            email=email,
            password_hash="never-return-this-hash",
            role=UserRole.ADMIN,
            active=True,
        )
        self.created.append(administrator)
        return administrator


def test_admin_routes_create_list_update_and_deactivate_without_credentials() -> None:
    actor = account()
    management = FakeAdministratorManagement()
    app.dependency_overrides[get_current_account] = lambda: actor
    app.dependency_overrides[get_administrator_management] = lambda: management
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/users/administradores",
                json={
                    "name": "Luis",
                    "surname": "Admin",
                    "email": "luis@example.test",
                    "password": "private-password",
                },
            )
            assert created.status_code == 201
            body = created.json()
            assert body["role"] == "ADMIN"
            assert body["district_id"] is None
            assert body["church_id"] is None
            assert "password" not in body
            assert "password_hash" not in body

            listed = client.get("/api/v1/users/administradores")
            assert listed.status_code == 200
            assert listed.json()[0]["id"] == body["id"]

            updated = client.patch(
                f"/api/v1/users/administradores/{body['id']}",
                json={"name": "Luis Alberto"},
            )
            assert updated.status_code == 200
            assert updated.json()["name"] == "Luis Alberto"

            deleted = client.delete(f"/api/v1/users/administradores/{body['id']}")
            assert deleted.status_code == 204

            reactivated = client.post(
                f"/api/v1/users/administradores/{body['id']}/reactivar"
            )
            assert reactivated.status_code == 200
            assert reactivated.json()["active"] is True
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        app.dependency_overrides.pop(get_administrator_management, None)


def test_only_admin_can_access_administrator_crud() -> None:
    app.dependency_overrides[get_current_account] = lambda: account(UserRole.PASTOR)
    app.dependency_overrides[get_administrator_management] = (
        lambda: FakeAdministratorManagement()
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/users/administradores")
            reactivate = client.post(
                f"/api/v1/users/administradores/{uuid4()}/reactivar"
            )
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        app.dependency_overrides.pop(get_administrator_management, None)

    assert response.status_code == 403
    assert reactivate.status_code == 403


def test_bootstrap_requires_secret_and_returns_no_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    configured_secret = "one-time-private-bootstrap-secret"
    monkeypatch.setenv("BOOTSTRAP_TOKEN", configured_secret)
    bootstrap = FakeBootstrapAdministrator()
    app.dependency_overrides[get_bootstrap_administrator] = lambda: bootstrap
    payload = {
        "name": "First",
        "surname": "Admin",
        "email": "first@example.test",
        "password": "first-private-password",
    }
    try:
        with TestClient(app) as client:
            missing = client.post("/api/v1/auth/bootstrap-admin", json=payload)
            invalid = client.post(
                "/api/v1/auth/bootstrap-admin",
                headers={"X-Bootstrap-Token": "wrong-secret"},
                json=payload,
            )
            created = client.post(
                "/api/v1/auth/bootstrap-admin",
                headers={"X-Bootstrap-Token": configured_secret},
                json=payload,
            )
    finally:
        app.dependency_overrides.pop(get_bootstrap_administrator, None)

    assert missing.status_code == 403
    assert invalid.status_code == 403
    assert created.status_code == 201
    assert created.json()["role"] == "ADMIN"
    assert created.json()["district_id"] is None
    assert "password_hash" not in created.json()
    assert len(bootstrap.created) == 1