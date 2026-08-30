"""Movie genre definitions."""

from enum import StrEnum


class Genre(StrEnum):
    """Supported movie genres."""

    COMEDY = "comedy"
    DRAMA = "drama"
    THRILLER = "thriller"
    CRIME = "crime"
    FAMILY = "family"
