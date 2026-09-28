from secrets import token_urlsafe

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class Argon2PasswordService:
    def __init__(self) -> None:
        self._hasher = PasswordHasher()
        self._dummy_hash = self._hasher.hash(token_urlsafe(32))

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str | None) -> bool:
        if password_hash is None:
            self._verify_dummy(password)
            return False

        try:
            return self._hasher.verify(password_hash, password)
        except InvalidHashError:
            self._verify_dummy(password)
            return False
        except VerificationError:
            return False

    def _verify_dummy(self, password: str) -> None:
        try:
            self._hasher.verify(self._dummy_hash, password)
        except VerifyMismatchError:
            return