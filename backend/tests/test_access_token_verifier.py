from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.domain.authentication import UserRole
from app.domain.errors import UnauthorizedException
from app.infrastructure.access_token_verifier import AccessTokenVerifier


SECRET_KEY = "test-only-access-signing-key-with-32-bytes-minimum"


def make_token(
    *,
    token_type: str = "access",
    expires_at: datetime | None = None,
    secret_key: str = SECRET_KEY,
) -> tuple[str, str]:
    user_id = str(uuid4())
    issued_at = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": user_id,
            "role": UserRole.ADMIN.value,
            "token_type": token_type,
            "iat": issued_at,
            "exp": expires_at or issued_at + timedelta(minutes=15),
        },
        secret_key,
        algorithm="HS256",
    )
    return user_id, token


def test_verifier_accepts_valid_access_token_and_returns_claims() -> None:
    user_id, token = make_token()

    claims = AccessTokenVerifier(SECRET_KEY).verify(token)

    assert str(claims.user_id) == user_id
    assert claims.role is UserRole.ADMIN


def test_verifier_rejects_refresh_token_as_access_credential() -> None:
    _, token = make_token(token_type="refresh")

    with pytest.raises(UnauthorizedException, match="Token de acceso inválido"):
        AccessTokenVerifier(SECRET_KEY).verify(token)


def test_verifier_rejects_expired_token_and_invalid_signature() -> None:
    _, expired_token = make_token(
        expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )
    _, wrong_signature_token = make_token(secret_key="another-signing-key-that-is-also-long-enough")
    verifier = AccessTokenVerifier(SECRET_KEY)

    with pytest.raises(UnauthorizedException, match="Token de acceso inválido"):
        verifier.verify(expired_token)

    with pytest.raises(UnauthorizedException, match="Token de acceso inválido"):
        verifier.verify(wrong_signature_token)
