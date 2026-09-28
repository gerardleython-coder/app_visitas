class DomainException(Exception):
    """Base exception for domain-level failures."""


class UnauthorizedException(DomainException):
    """Raised when credentials do not grant application access."""