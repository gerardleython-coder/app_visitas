from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.dependencies import get_logout_user


@dataclass
class FakeLogoutUser:
    revoked: bool

    async def execute(self, refresh_token: str) -> bool:
        assert refresh_token == "submitted-refresh-token"
        return self.revoked


@pytest.mark.parametrize("revoked", [True, False])
def test_logout_returns_no_content_without_revealing_token_existence(
    revoked: bool,
) -> None:
    app.dependency_overrides[get_logout_user] = lambda: FakeLogoutUser(revoked)
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "submitted-refresh-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""
