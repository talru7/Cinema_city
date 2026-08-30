"""User identity and validation errors."""

from cinema.exceptions.base import BusinessError, ValidationError


class UserValidationError(ValidationError):
    """Raised when user identity details are invalid."""


class UserIdentityConflictError(BusinessError):
    """Raised when email and phone resolve to different existing users."""
