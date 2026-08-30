"""Exceptions related to persistent storage."""

from cinema.exceptions.base import CinemaError


class StorageError(CinemaError):
    """Raised when persisted cinema data cannot be loaded or saved."""
