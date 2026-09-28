from dataclasses import dataclass
from uuid import UUID

import jwt

from app.domain.authentication import UserRole
from app.domain.errors import UnauthorizedException


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: UUID
    role: UserRole


class AccessTokenVerifier:
    def __init__(self, secret_key: str) -> None:
        self._secret_key = secret_key

    def verify(self, token: str) -> AccessTokenClaims:
        try:
            claims = jwt.decode(
                token,
                self._secret_key,
                algorithms=["HS256"],
                options={"require": ["sub", "role", "token_type", "iat", "exp"]},
            )
            if claims["token_type"] != "access":
                raise ValueError("Wrong token type")

            return AccessTokenClaims(
                user_id=UUID(claims["sub"]),
                role=UserRole(claims["role"]),
            )
        except (jwt.InvalidTokenError, ValueError) as error:
            raise UnauthorizedException("Token de acceso inválido") from error