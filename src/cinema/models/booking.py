"""Booking database-oriented domain model."""

from dataclasses import dataclass

from cinema.exceptions import BookingValidationError


@dataclass(frozen=True, slots=True)
class Booking:
    """Represent one booking row using foreign-key IDs only."""

    booking_id: int | None
    user_id: int
    show_id: int

    def __post_init__(self) -> None:
        if self.booking_id is not None and self.booking_id <= 0:
            raise BookingValidationError("Booking ID must be positive")
        if self.user_id <= 0:
            raise BookingValidationError("Booking user ID must be positive")
        if self.show_id <= 0:
            raise BookingValidationError("Booking show ID must be positive")
