from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PasswordResetEmail:
    recipient_email: str
    token: str = field(repr=False)