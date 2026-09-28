from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.application.authenticate_user import SessionTokens
from app.domain.errors import UnauthorizedException
from app.main import app
from app.presentation.dependencies import get_authenticate_user


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
