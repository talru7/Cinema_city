"""Booking-seat junction-table domain model."""

from dataclasses import dataclass

from cinema.exceptions import BookingValidationError


@dataclass(frozen=True, slots=True)
class BookingSeat:
    """Represent one booking_seats junction-table row."""

    booking_id: int
    show_id: int
    seat_id: int

    def __post_init__(self) -> None:
        if self.booking_id <= 0:
            raise BookingValidationError("Booking-seat booking ID must be positive")
        if self.show_id <= 0:
            raise BookingValidationError("Booking-seat show ID must be positive")
        if self.seat_id <= 0:
            raise BookingValidationError("Booking-seat seat ID must be positive")
