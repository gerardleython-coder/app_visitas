from dataclasses import dataclass
from uuid import uuid4

from fastapi.testclient import TestClient

from app.application.authenticate_user import SessionTokens
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import UnauthorizedException
from app.main import app
from app.presentation.dependencies import get_authenticate_user, get_current_account


@dataclass
class FakeAuthenticateUser:
    should_reject: bool = False

    async def execute(self, email: str, password: str) -> SessionTokens:
        if self.should_reject:
            raise UnauthorizedException("Credenciales inválidas")
        return SessionTokens(
            access_token="signed-access-token",
            refresh_token="opaque-refresh-token",
            access_expires_in=900,
        )


def test_login_returns_access_and_refresh_tokens() -> None:
    app.dependency_overrides[get_authenticate_user] = lambda: FakeAuthenticateUser()
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.test", "password": "valid-test-password"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "signed-access-token",
        "refresh_token": "opaque-refresh-token",
        "token_type": "bearer",
        "expires_in": 900,
    }


def test_login_uses_uniform_authentication_error() -> None:
    app.dependency_overrides[get_authenticate_user] = lambda: FakeAuthenticateUser(
        should_reject=True
    )
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.test", "password": "wrong-test-password"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json() == {
        "detail": {"code": "unauthorized", "message": "Credenciales inválidas"}
    }


def test_current_account_returns_only_safe_profile_fields() -> None:
    district_id = uuid4()
    church_id = uuid4()
    actor = UserAccount(
        id=uuid4(),
        email="admin@example.test",
        password_hash="never-return-this-hash",
        role=UserRole.ADMIN,
        active=True,
        district_id=district_id,
        church_id=church_id,
    )
    app.dependency_overrides[get_current_account] = lambda: actor
    try:
        response = TestClient(app).get("/api/v1/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": str(actor.id),
        "email": actor.email,
        "role": "ADMIN",
        "active": True,
        "district_id": str(district_id),
        "church_id": str(church_id),
    }
    assert "password_hash" not in response.json()


def test_flutter_web_origin_passes_cors_preflight() -> None:
    response = TestClient(app).options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5000"
