from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID, uuid4

import pytest

from app.application.password_recovery import RequestPasswordReset, ResetPassword
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import UnauthorizedException
from app.domain.password_recovery import PasswordResetEmail
from app.infrastructure.email_service import SMTPEmailSender, SMTPSettings


@dataclass
class FakeUsers:
    accounts: dict[str, UserAccount] = field(default_factory=dict)
    by_id: dict[UUID, UserAccount] = field(default_factory=dict)
    password_hashes: dict[UUID, str] = field(default_factory=dict)

    async def get_by_email(self, email: str) -> UserAccount | None:
        return self.accounts.get(email)

    async def get_by_id(self, user_id: UUID) -> UserAccount | None:
        return self.by_id.get(user_id)

    async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
        self.password_hashes[user_id] = password_hash


@dataclass
class FakePasswordRecoveryRepository:
    tokens: dict[str, tuple[UUID, datetime]] = field(default_factory=dict)
    consumed: set[str] = field(default_factory=set)

    async def create_token(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        self.tokens[token_hash] = (user_id, expires_at)

    async def consume_token(self, token_hash: str, consumed_at: datetime) -> UUID | None:
        token_record = self.tokens.get(token_hash)
        if (
            token_record is None
            or token_hash in self.consumed
            or token_record[1] <= consumed_at
        ):
            return None
        self.consumed.add(token_hash)
        return token_record[0]


@dataclass
class FakeRefreshSessions:
    revoked_user_ids: list[UUID] = field(default_factory=list)

    async def revoke_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        self.revoked_user_ids.append(user_id)


@dataclass
class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"test-hash-{password}"


def make_account(role: UserRole = UserRole.ADMIN, *, active: bool = True) -> UserAccount:
    return UserAccount(
        id=uuid4(),
        email=f"{uuid4().hex}@example.test",
        password_hash="test-only-existing-hash",
        role=role,
        active=active,
    )


async def test_request_password_reset_persists_only_hash_for_active_operational_user() -> None:
    user = make_account()
    users = FakeUsers(accounts={user.email: user})
    recovery = FakePasswordRecoveryRepository()
    raw_token = token_urlsafe(32)
    use_case = RequestPasswordReset(
        users=users,
        recovery=recovery,
        token_factory=lambda: raw_token,
    )
    before = datetime.now(UTC)

    result = await use_case.execute(user.email)

    assert result == PasswordResetEmail(recipient_email=user.email, token=raw_token)
    assert raw_token not in repr(result)
    token_hash = sha256(raw_token.encode("utf-8")).hexdigest()
    assert set(recovery.tokens) == {token_hash}
    assert raw_token not in recovery.tokens
    saved_user_id, expires_at = recovery.tokens[token_hash]
    assert saved_user_id == user.id
    assert before + timedelta(minutes=29) < expires_at < before + timedelta(minutes=31)


@pytest.mark.parametrize(
    "account",
    [None, "inactive", "brother"],
)
async def test_request_password_reset_is_neutral_for_unknown_or_ineligible_accounts(
    account: UserAccount | str | None,
) -> None:
    user = None
    if account == "inactive":
        user = make_account(active=False)
    elif account == "brother":
        user = make_account(role=UserRole.HERMANO)
    users = FakeUsers(accounts={user.email: user} if user else {})
    recovery = FakePasswordRecoveryRepository()
    use_case = RequestPasswordReset(
        users=users,
        recovery=recovery,
        token_factory=token_urlsafe,
    )

    result = await use_case.execute(user.email if user else "missing@example.test")

    assert result is None
    assert recovery.tokens == {}


async def test_reset_password_hashes_new_password_and_revokes_all_user_sessions() -> None:
    user = make_account()
    raw_token = token_urlsafe(32)
    token_hash = sha256(raw_token.encode("utf-8")).hexdigest()
    recovery = FakePasswordRecoveryRepository(
        tokens={token_hash: (user.id, datetime.now(UTC) + timedelta(minutes=30))}
    )
    users = FakeUsers(by_id={user.id: user})
    sessions = FakeRefreshSessions()
    password = token_urlsafe(24)
    use_case = ResetPassword(
        users=users,
        recovery=recovery,
        sessions=sessions,
        passwords=FakePasswordHasher(),
    )

    await use_case.execute(raw_token, password)

    assert users.password_hashes == {user.id: f"test-hash-{password}"}
    assert sessions.revoked_user_ids == [user.id]
    assert token_hash in recovery.consumed


@pytest.mark.parametrize("token_state", ["unknown", "expired", "used", "inactive-user"])
async def test_reset_password_rejects_invalid_expired_reused_or_inactive_token(
    token_state: str,
) -> None:
    user = make_account(active=token_state != "inactive-user")
    raw_token = token_urlsafe(32)
    token_hash = sha256(raw_token.encode("utf-8")).hexdigest()
    token_records = {}
    consumed = set()
    if token_state != "unknown":
        expiration = (
            datetime.now(UTC) - timedelta(seconds=1)
            if token_state == "expired"
            else datetime.now(UTC) + timedelta(minutes=30)
        )
        token_records[token_hash] = (user.id, expiration)
    if token_state == "used":
        consumed.add(token_hash)
    recovery = FakePasswordRecoveryRepository(tokens=token_records, consumed=consumed)
    users = FakeUsers(by_id={user.id: user})
    sessions = FakeRefreshSessions()
    use_case = ResetPassword(
        users=users,
        recovery=recovery,
        sessions=sessions,
        passwords=FakePasswordHasher(),
    )

    with pytest.raises(UnauthorizedException):
        await use_case.execute(raw_token, token_urlsafe(24))

    assert users.password_hashes == {}
    assert sessions.revoked_user_ids == []


async def test_smtp_sender_delivers_reset_token_only_to_recipient(monkeypatch) -> None:
    class FakeSMTP:
        def __init__(self, *_args, **_kwargs) -> None:
            self.message = None

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def ehlo(self) -> None:
            return None

        def starttls(self, *, context) -> None:
            assert context is not None

        def login(self, *_args) -> None:
            return None

        def send_message(self, message) -> None:
            self.message = message

    smtp = FakeSMTP()
    monkeypatch.setattr(
        "app.infrastructure.email_service.smtplib.SMTP",
        lambda *args, **kwargs: smtp,
    )
    reset_token = token_urlsafe(32)
    sender = SMTPEmailSender(
        SMTPSettings(
            _env_file=None,
            smtp_host="smtp.example.test",
            smtp_port=587,
            emails_from_email="no-reply@example.test",
        )
    )

    await sender.send_password_reset(
        PasswordResetEmail("pastor@example.test", reset_token)
    )

    assert smtp.message["To"] == "pastor@example.test"
    assert reset_token in smtp.message.get_content()