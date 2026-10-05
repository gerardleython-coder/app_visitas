from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from app.application.authenticate_user import AuthenticateUser, SessionTokens
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import UnauthorizedException


@dataclass
class FakeUserRepository:
    account: UserAccount | None

    async def get_by_email(self, email: str) -> UserAccount | None:
        return self.account if self.account and self.account.email == email else None


@dataclass
class FakePasswordVerifier:
    valid_password: str
    verified_hashes: list[str | None] = field(default_factory=list)

    def verify(self, password: str, password_hash: str | None) -> bool:
        self.verified_hashes.append(password_hash)
        return password == self.valid_password and password_hash == "stored-hash"


@dataclass
class FakeSessionIssuer:
    tokens: SessionTokens
    account_id: UUID | None = None
    access_ttl_seconds: int | None = None

    async def issue(self, account: UserAccount, *, access_ttl_seconds: int) -> SessionTokens:
        self.account_id = account.id
        self.access_ttl_seconds = access_ttl_seconds
        return self.tokens


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER])
async def test_active_operational_user_receives_session_tokens(role: UserRole) -> None:
    account = UserAccount(
        id=uuid4(),
        email="user@example.com",
        password_hash="stored-hash",
        role=role,
        active=True,
    )
    expected_tokens = SessionTokens(
        access_token="access-token",
        refresh_token="refresh-token",
        access_expires_in=900,
    )
    session_issuer = FakeSessionIssuer(expected_tokens)
    use_case = AuthenticateUser(
        users=FakeUserRepository(account),
        passwords=FakePasswordVerifier("correct-password"),
        sessions=session_issuer,
    )

    tokens = await use_case.execute("user@example.com", "correct-password")

    assert tokens == expected_tokens
    assert session_issuer.account_id == account.id
    assert session_issuer.access_ttl_seconds == 900


@pytest.mark.parametrize(
    ("account", "password"),
    [
        (
            UserAccount(uuid4(), "user@example.com", "stored-hash", UserRole.HERMANO, True),
            "correct-password",
        ),
        (
            UserAccount(uuid4(), "user@example.com", "stored-hash", UserRole.ADMIN, False),
            "correct-password",
        ),
        (
            UserAccount(uuid4(), "user@example.com", "stored-hash", UserRole.ADMIN, True),
            "wrong-password",
        ),
        (None, "correct-password"),
    ],
)
async def test_invalid_or_unauthorized_login_has_uniform_error(
    account: UserAccount | None,
    password: str,
) -> None:
    password_verifier = FakePasswordVerifier("correct-password")
    session_issuer = FakeSessionIssuer(
        SessionTokens("access-token", "refresh-token", access_expires_in=900)
    )
    use_case = AuthenticateUser(
        users=FakeUserRepository(account),
        passwords=password_verifier,
        sessions=session_issuer,
    )

    with pytest.raises(UnauthorizedException, match="Credenciales inválidas"):
        await use_case.execute("user@example.com", password)

    assert len(password_verifier.verified_hashes) == 1
    assert session_issuer.account_id is None
    if account is None or account.role is UserRole.HERMANO:
        assert password_verifier.verified_hashes == [None]
