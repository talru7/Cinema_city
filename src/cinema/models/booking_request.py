"""Validated booking request awaiting persistence-time ID allocation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BookingRequest:
    """A validated booking request without a persisted booking ID."""

    user_id: int
    show_id: int
    seat_ids: tuple[int, ...]
