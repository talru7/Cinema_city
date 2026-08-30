"""Cinema database-oriented domain model."""

from dataclasses import dataclass

from cinema.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class Cinema:
    """Represent one cinema row without nested domain objects."""

    cinema_id: int
    name: str

    def __post_init__(self) -> None:
        if self.cinema_id <= 0:
            raise ValidationError("Cinema ID must be positive")
        if not self.name.strip():
            raise ValidationError("Cinema name cannot be empty")
