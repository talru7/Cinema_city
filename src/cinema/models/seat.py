"""Seat database-oriented domain model."""

from dataclasses import dataclass

from cinema.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class Seat:
    """Represent one physical seat row."""

    seat_id: int
    hall_id: int
    row_number: int
    seat_number: int

    def __post_init__(self) -> None:
        if self.seat_id <= 0:
            raise ValidationError("Seat ID must be positive")
        if self.hall_id <= 0:
            raise ValidationError("Seat hall ID must be positive")
        if self.row_number <= 0:
            raise ValidationError("Seat row number must be positive")
        if self.seat_number <= 0:
            raise ValidationError("Seat number must be positive")
