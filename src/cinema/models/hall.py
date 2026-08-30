"""Cinema hall database-oriented domain model."""

from dataclasses import dataclass

from cinema.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class Hall:
    """Represent one cinema hall row."""

    hall_id: int
    hall_name: str

    def __post_init__(self) -> None:
        if self.hall_id <= 0:
            raise ValidationError("Hall ID must be positive")
        if not self.hall_name.strip():
            raise ValidationError("Hall name cannot be empty")
