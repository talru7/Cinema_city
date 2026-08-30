"""Exceptions related to cinema scheduling."""

from cinema.exceptions.base import BusinessError


class ScheduleError(BusinessError):
    """Base exception for scheduling-related errors."""


class ScheduleValidationError(ScheduleError):
    """Raised when a scheduling request violates a scheduling rule."""


class NotEnoughScheduleSlotsError(ScheduleError):
    """Raised when not enough available screening slots can be found."""
