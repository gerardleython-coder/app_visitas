from app.infrastructure.password_service import Argon2PasswordService


def test_password_hash_is_argon2id_and_verifies_only_matching_password() -> None:
    passwords = Argon2PasswordService()

    encoded_hash = passwords.hash("secure-test-password")

    assert encoded_hash.startswith("$argon2id$")
    assert encoded_hash != "secure-test-password"
    assert passwords.verify("secure-test-password", encoded_hash) is True
    assert passwords.verify("wrong-password", encoded_hash) is False


def test_missing_or_invalid_hash_is_rejected_without_raising() -> None:
    passwords = Argon2PasswordService()

    assert passwords.verify("any-password", None) is False
    assert passwords.verify("any-password", "not-an-argon2-hash") is False
