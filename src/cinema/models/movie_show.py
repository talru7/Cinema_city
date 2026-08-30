"""Movie-show database-oriented domain model."""

from dataclasses import dataclass
from datetime import datetime

from cinema.exceptions import ScheduleValidationError
from cinema.models.movie import MAX_TICKET_PRICE, MIN_TICKET_PRICE


@dataclass(frozen=True, slots=True)
class MovieShow:
    """Represent one movie-show row using foreign-key IDs only."""

    show_id: int | None
    movie_id: int
    hall_id: int
    start_time: datetime
    ticket_price: int

    def __post_init__(self) -> None:
        if self.show_id is not None and self.show_id <= 0:
            raise ScheduleValidationError("Show ID must be positive")
        if self.movie_id <= 0:
            raise ScheduleValidationError("Movie ID must be positive")
        if self.hall_id <= 0:
            raise ScheduleValidationError("Hall ID must be positive")
        if self.start_time.tzinfo is None or self.start_time.utcoffset() is None:
            raise ScheduleValidationError("Movie show start time must be timezone-aware")
        if not MIN_TICKET_PRICE <= self.ticket_price <= MAX_TICKET_PRICE:
            raise ScheduleValidationError(
                f"Ticket price must be between {MIN_TICKET_PRICE} and {MAX_TICKET_PRICE} NIS"
            )
