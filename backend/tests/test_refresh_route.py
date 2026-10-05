from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.application.authenticate_user import SessionTokens
from app.domain.errors import UnauthorizedException
from app.main import app
from app.presentation.dependencies import get_rotate_refresh_token


@dataclass
class FakeRotateRefreshToken:
    should_reject: bool = False

    async def execute(self, refresh_token: str) -> SessionTokens:
        assert refresh_token == "submitted-refresh-token"
        if self.should_reject:
            raise UnauthorizedException("Refresh token inválido")
        return SessionTokens(
            access_token="rotated-access-token",
            refresh_token="rotated-refresh-token",
            access_expires_in=900,
        )


def test_refresh_returns_rotated_access_and_refresh_tokens() -> None:
    app.dependency_overrides[get_rotate_refresh_token] = lambda: FakeRotateRefreshToken()
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "submitted-refresh-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "rotated-access-token",
        "refresh_token": "rotated-refresh-token",
        "token_type": "bearer",
        "expires_in": 900,
    }


def test_refresh_rejects_invalid_token_with_uniform_error() -> None:
    app.dependency_overrides[get_rotate_refresh_token] = lambda: FakeRotateRefreshToken(
        should_reject=True
    )
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "submitted-refresh-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json() == {
        "detail": {"code": "unauthorized", "message": "Credenciales inválidas"}
    }
