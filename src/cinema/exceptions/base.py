"""Base exceptions for the cinema application."""


class CinemaError(Exception):
    """Base class for expected cinema application errors."""


class BusinessError(CinemaError):
    """Base class for expected business-rule errors."""


class ValidationError(BusinessError):
    """Raised when user-supplied or domain data violates a validation rule."""


class MovieAlreadyExistsError(BusinessError):
    """Raised when a movie title already exists in the cinema catalog."""
