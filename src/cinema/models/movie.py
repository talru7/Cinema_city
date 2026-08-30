"""Movie domain model."""

from dataclasses import dataclass

from cinema.exceptions import ValidationError
from cinema.models.genre import Genre

MAX_DESCRIPTION_LENGTH = 300
MAX_DURATION_LENGTH = 240
MIN_TICKET_PRICE = 1
MAX_TICKET_PRICE = 99


@dataclass(frozen=True, slots=True)
class Movie:
    """A movie that may be screened at different times and halls."""

    movie_id: int | None
    title: str
    duration_minutes: int
    description: str
    genre: Genre
    ticket_price: int

    def __post_init__(self) -> None:
        """Validate movie data after object creation."""
        if self.movie_id is not None and self.movie_id <= 0:
            raise ValidationError("Movie ID must be positive")

        if not self.title.strip():
            raise ValidationError("Movie title cannot be empty")

        if not 1 <= self.duration_minutes <= MAX_DURATION_LENGTH:
            raise ValidationError(
                f"Movie duration must be between 1 and {MAX_DURATION_LENGTH} minutes"
            )

        if not self.description.strip():
            raise ValidationError("Movie description cannot be empty")

        if len(self.description) > MAX_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"Movie description cannot exceed {MAX_DESCRIPTION_LENGTH} characters"
            )

        if not MIN_TICKET_PRICE <= self.ticket_price <= MAX_TICKET_PRICE:
            raise ValidationError(
                f"Ticket price must be between {MIN_TICKET_PRICE} and {MAX_TICKET_PRICE} NIS"
            )
