from __future__ import annotations

from typing import ClassVar


class DomainError(Exception):
    """Base class for business rule violations.

    Every subclass carries a stable machine-readable ``code`` that crosses the
    API boundary unchanged, so clients can rely on it across releases.
    """

    code: ClassVar[str] = "domain_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.code)
        self.message = message


class NotFoundError(DomainError):
    code = "not_found"


class AccessDeniedError(DomainError):
    code = "access_denied"


class ConflictError(DomainError):
    code = "conflict"


class ValidationError(DomainError):
    code = "validation_failed"


class InvalidStateError(DomainError):
    code = "invalid_state"


class TooLargeError(DomainError):
    code = "too_large"
