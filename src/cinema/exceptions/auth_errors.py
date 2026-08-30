"""Authentication and authorization failures."""

from cinema.exceptions.base import CinemaError


class AuthenticationError(CinemaError):
    """Raised when request credentials cannot be authenticated."""


class AuthorizationError(CinemaError):
    """Raised when an authenticated user lacks a required permission."""


class ConfigurationError(CinemaError):
    """Raised when application configuration is incomplete or inconsistent."""
