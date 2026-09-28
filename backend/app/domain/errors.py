class DomainException(Exception):
    """Base exception for domain-level failures."""


class UnauthorizedException(DomainException):
    """Raised when credentials do not grant application access."""


class ForbiddenException(DomainException):
    """Raised when an authenticated actor lacks permission for an operation."""