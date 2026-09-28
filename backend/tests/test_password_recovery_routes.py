from dataclasses import dataclass, field
from secrets import token_urlsafe

from fastapi.testclient import TestClient

from app.domain.errors import UnauthorizedException
from app.domain.password_recovery import PasswordResetEmail
from app.main import app
from app.presentation.dependencies import (
    get_password_reset_email_sender,
    get_request_password_reset,
    get_reset_password,
)


@dataclass
class FakeRequestPasswordReset:
    reset_email: PasswordResetEmail | None

    async def execute(self, email: str) -> PasswordResetEmail | None:
        return self.reset_email if email == "known@example.test" else None


@dataclass
class FakeResetPassword:
    expected_token: str
    reset_calls: list[tuple[str, str]] = field(default_factory=list)

    async def execute(self, token: str, new_password: str) -> None:
        if token != self.expected_token:
            raise UnauthorizedException("Token de recuperación inválido o expirado")
        self.reset_calls.append((token, new_password))


@dataclass
class FakePasswordResetEmailSender:
    sent: list[PasswordResetEmail] = field(default_factory=list)

    async def send_password_reset(self, email: PasswordResetEmail) -> None:
        self.sent.append(email)


def test_forgot_password_response_is_neutral_and_never_contains_reset_token() -> None:
    token = token_urlsafe(32)
    request = PasswordResetEmail("known@example.test", token)
    sender = FakePasswordResetEmailSender()
    app.dependency_overrides[get_request_password_reset] = lambda: FakeRequestPasswordReset(
        request
    )
    app.dependency_overrides[get_password_reset_email_sender] = lambda: sender
    try:
        with TestClient(app) as client:
            known = client.post(
                "/api/v1/auth/password/forgot",
                json={"email": "known@example.test"},
            )
            unknown = client.post(
                "/api/v1/auth/password/forgot",
                json={"email": "unknown@example.test"},
            )
    finally:
        app.dependency_overrides.pop(get_request_password_reset, None)
        app.dependency_overrides.pop(get_password_reset_email_sender, None)

    assert known.status_code == unknown.status_code == 202
    assert known.content == unknown.content == b""
    assert token.encode() not in known.content
    assert sender.sent == [request]


def test_reset_password_returns_no_data_on_success_and_generic_error_for_invalid_token() -> None:
    token = token_urlsafe(32)
    use_case = FakeResetPassword(expected_token=token)
    app.dependency_overrides[get_reset_password] = lambda: use_case
    try:
        with TestClient(app) as client:
            success = client.post(
                "/api/v1/auth/password/reset",
                json={"token": token, "new_password": token_urlsafe(24)},
            )
            invalid = client.post(
                "/api/v1/auth/password/reset",
                json={"token": token_urlsafe(32), "new_password": token_urlsafe(24)},
            )
            short_token = client.post(
                "/api/v1/auth/password/reset",
                json={"token": "x", "new_password": token_urlsafe(24)},
            )
    finally:
        app.dependency_overrides.pop(get_reset_password, None)

    assert success.status_code == 204
    assert success.content == b""
    assert invalid.status_code == 400
    assert invalid.json() == {
        "detail": {"code": "invalid_token", "message": "Token inválido o expirado"}
    }
    assert short_token.status_code == 400
    assert short_token.json() == invalid.json()
    assert len(use_case.reset_calls) == 1