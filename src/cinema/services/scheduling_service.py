"""Stateless screening scheduling business service."""

from datetime import date, datetime, time, timedelta

from cinema.exceptions import (
    NotEnoughScheduleSlotsError,
    ScheduleValidationError,
)
from cinema.models import Hall, Movie, MovieShow
from cinema.storage.interfaces import (
    CinemaConfigRepository,
    MovieRepository,
    ShowRepository,
)
from cinema.time_utils import local_datetime

DEFAULT_OPENING_TIME = time(hour=10)
DEFAULT_CLOSING_TIME = time(hour=23, minute=59)
DEFAULT_SHOWS_PER_HALL = 3
DEFAULT_INTERVAL_MINUTES = 30
CLEANING_TIME = timedelta(minutes=20)


class SchedulingService:
    """Plan shows from repository snapshots without keeping scheduling state."""

    def __init__(
        self,
        config_repository: CinemaConfigRepository,
        movie_repository: MovieRepository,
        show_repository: ShowRepository,
        opening_time: time = DEFAULT_OPENING_TIME,
        closing_time: time = DEFAULT_CLOSING_TIME,
    ) -> None:
        if opening_time >= closing_time:
            raise ScheduleValidationError("Opening time must be earlier than closing time")
        self._config_repository = config_repository
        self._movie_repository = movie_repository
        self._show_repository = show_repository
        self._opening_time = opening_time
        self._closing_time = closing_time

    def schedule_movie(
        self,
        hall_id: int,
        movie: Movie,
        screening_date: date,
        shows_count: int = DEFAULT_SHOWS_PER_HALL,
    ) -> list[MovieShow]:
        """Schedule a movie in one hall and persist the planned shows."""
        halls, movies, existing_shows = self._load_state()
        self._require_hall(hall_id, halls)
        self._require_movie(movie.movie_id, movies)

        planned = self._plan_for_hall(
            hall_id=hall_id,
            movie=movie,
            screening_date=screening_date,
            shows_count=shows_count,
            existing_shows=existing_shows,
            movies_by_id={item.movie_id: item for item in movies if item.movie_id is not None},
        )
        return self._persist(planned)

    def schedule_movie_for_all_halls(
        self,
        movie: Movie,
        screening_date: date,
        shows_per_hall: int = DEFAULT_SHOWS_PER_HALL,
    ) -> tuple[MovieShow, ...]:
        """Plan a movie for every hall and persist all shows together."""
        if shows_per_hall <= 0:
            raise ScheduleValidationError("Shows per hall must be positive")

        halls, movies, existing_shows = self._load_state()
        self._require_movie(movie.movie_id, movies)
        movies_by_id = {item.movie_id: item for item in movies if item.movie_id is not None}

        planned_shows: list[MovieShow] = []

        for hall in halls:
            shows = self._plan_for_hall(
                hall_id=hall.hall_id,
                movie=movie,
                screening_date=screening_date,
                shows_count=shows_per_hall,
                existing_shows=existing_shows,
                movies_by_id=movies_by_id,
            )
            planned_shows.extend(shows)

        return tuple(self._persist(planned_shows))

    def _load_state(self) -> tuple[list[Hall], list[Movie], list[MovieShow]]:
        _, halls, _ = self._config_repository.load()
        movies = self._movie_repository.load()
        shows = self._show_repository.load(
            valid_hall_ids={hall.hall_id for hall in halls},
            valid_movie_ids={movie.movie_id for movie in movies if movie.movie_id is not None},
        )
        return halls, movies, shows

    def _plan_for_hall(
        self,
        *,
        hall_id: int,
        movie: Movie,
        screening_date: date,
        shows_count: int,
        existing_shows: list[MovieShow],
        movies_by_id: dict[int, Movie],
    ) -> list[MovieShow]:
        if shows_count <= 0:
            raise ScheduleValidationError("Shows per hall must be positive")

        available_times = self._find_available_start_times(
            hall_id=hall_id,
            movie=movie,
            screening_date=screening_date,
            count=shows_count,
            existing_shows=existing_shows,
            movies_by_id=movies_by_id,
        )
        if len(available_times) < shows_count:
            raise NotEnoughScheduleSlotsError(
                f"Hall {hall_id} does not have {shows_count} available slots"
            )

        return [
            MovieShow(
                show_id=None,
                movie_id=self._require_persisted_movie_id(movie),
                hall_id=hall_id,
                start_time=start_time,
                ticket_price=movie.ticket_price,
            )
            for start_time in available_times
        ]

    def _find_available_start_times(
        self,
        *,
        hall_id: int,
        movie: Movie,
        screening_date: date,
        count: int,
        existing_shows: list[MovieShow],
        movies_by_id: dict[int, Movie],
        interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    ) -> tuple[datetime, ...]:
        if count <= 0:
            raise ScheduleValidationError("Requested number of start times must be positive")
        if interval_minutes <= 0:
            raise ScheduleValidationError("Interval must be positive")

        current_time = local_datetime(screening_date, self._opening_time)
        closing_datetime = local_datetime(screening_date, self._closing_time)
        movie_duration = timedelta(minutes=movie.duration_minutes)
        interval = timedelta(minutes=interval_minutes)
        existing = [show for show in existing_shows if show.hall_id == hall_id]
        planned_ranges: list[tuple[datetime, datetime]] = []
        available_times: list[datetime] = []

        while current_time + movie_duration <= closing_datetime:
            candidate_end = current_time + movie_duration
            candidate_ready_time = candidate_end + CLEANING_TIME
            conflicts_with_existing = any(
                self._time_ranges_overlap(
                    current_time,
                    candidate_ready_time,
                    show.start_time,
                    self._show_end(show, movies_by_id),
                )
                for show in existing
            )
            conflicts_with_planned = any(
                self._time_ranges_overlap(
                    current_time,
                    candidate_ready_time,
                    planned_start,
                    planned_end,
                )
                for planned_start, planned_end in planned_ranges
            )

            if not conflicts_with_existing and not conflicts_with_planned:
                available_times.append(current_time)
                planned_ranges.append((current_time, candidate_ready_time))
                if len(available_times) == count:
                    break

            current_time += interval

        return tuple(available_times)

    @staticmethod
    def _show_end(show: MovieShow, movies_by_id: dict[int, Movie]) -> datetime:
        try:
            movie = movies_by_id[show.movie_id]
        except KeyError as error:
            raise ScheduleValidationError(
                f"Show {show.show_id} references unknown movie {show.movie_id}"
            ) from error
        return show.start_time + timedelta(minutes=movie.duration_minutes) + CLEANING_TIME

    @staticmethod
    def _require_hall(hall_id: int, halls: list[Hall]) -> Hall:
        hall = next((item for item in halls if item.hall_id == hall_id), None)
        if hall is None:
            raise ScheduleValidationError(f"Hall {hall_id} does not exist")
        return hall

    @staticmethod
    def _require_movie(movie_id: int | None, movies: list[Movie]) -> Movie:
        movie = next((item for item in movies if item.movie_id == movie_id), None)
        if movie is None:
            raise ScheduleValidationError("Movie must belong to the cinema catalog")
        return movie

    def _persist(self, shows: list[MovieShow]) -> list[MovieShow]:
        show_ids = self._show_repository.create_many(shows)
        return [
            MovieShow(
                show_id=show_id,
                movie_id=show.movie_id,
                hall_id=show.hall_id,
                start_time=show.start_time,
                ticket_price=show.ticket_price,
            )
            for show_id, show in zip(show_ids, shows, strict=True)
        ]

    @staticmethod
    def _require_persisted_movie_id(movie: Movie) -> int:
        if movie.movie_id is None:
            raise ScheduleValidationError("Movie must be persisted before scheduling")
        return movie.movie_id

    @staticmethod
    def _time_ranges_overlap(
        first_start: datetime,
        first_end: datetime,
        second_start: datetime,
        second_end: datetime,
    ) -> bool:
        return first_start < second_end and second_start < first_end
