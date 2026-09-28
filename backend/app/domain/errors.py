class DomainException(Exception):
    """Base exception for domain-level failures."""


class UnauthorizedException(DomainException):
    """Raised when credentials do not grant application access."""


class ForbiddenException(DomainException):
    """Raised when an authenticated actor lacks permission for an operation."""


class NotFoundException(DomainException):
    """Raised when a resource is missing or outside the actor's visible scope."""


class ConflictException(DomainException):
    """Raised when a requested operation conflicts with a business invariant."""