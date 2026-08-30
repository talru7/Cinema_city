"""Stateless administrative service for a cinema."""

from datetime import date

from cinema.exceptions import MovieAlreadyExistsError
from cinema.models import Genre, Movie, MovieShow
from cinema.services.scheduling_service import (
    DEFAULT_SHOWS_PER_HALL,
    SchedulingService,
)
from cinema.storage.interfaces import MovieRepository

DEFAULT_TICKET_PRICE = 40


class CinemaManager:
    """Perform manager operations through injected repository abstractions."""

    def __init__(
        self,
        movie_repository: MovieRepository,
        scheduling_service: SchedulingService,
    ) -> None:
        self._movie_repository = movie_repository
        self._scheduling_service = scheduling_service

    def add_movie(
        self,
        title: str,
        duration_minutes: int,
        description: str,
        genre: Genre,
        ticket_price: int = DEFAULT_TICKET_PRICE,
    ) -> Movie:
        """Validate title uniqueness and persist a new movie."""
        normalized_title = title.strip().casefold()
        if any(
            movie.title.strip().casefold() == normalized_title
            for movie in self._movie_repository.load()
        ):
            raise MovieAlreadyExistsError(f'Movie "{title.strip()}" already exists')

        new_movie = Movie(
            movie_id=None,
            title=title,
            duration_minutes=duration_minutes,
            description=description,
            genre=genre,
            ticket_price=ticket_price,
        )
        movie_id = self._movie_repository.create(new_movie)
        persisted = self._movie_repository.find_by_id(movie_id)
        if persisted is None:
            raise RuntimeError("Movie repository did not return the created movie")
        return persisted

    def schedule_movie(
        self,
        movie: Movie,
        screening_date: date,
        shows_per_hall: int = DEFAULT_SHOWS_PER_HALL,
    ) -> tuple[MovieShow, ...]:
        """Schedule a persisted movie in every configured hall."""
        return self._scheduling_service.schedule_movie_for_all_halls(
            movie=movie,
            screening_date=screening_date,
            shows_per_hall=shows_per_hall,
        )
