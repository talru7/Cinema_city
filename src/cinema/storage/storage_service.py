"""Repository-coordinating read service using injected abstractions."""

from cinema.models import (
    Booking,
    BookingSeat,
    Cinema,
    Hall,
    Movie,
    MovieShow,
    Seat,
    User,
)
from cinema.storage.interfaces import (
    BookingRepository,
    CinemaConfigRepository,
    MovieRepository,
    ShowRepository,
    UserRepository,
)


class StorageService:
    """Coordinate reads without constructing concrete persistence implementations."""

    def __init__(
        self,
        config_repository: CinemaConfigRepository,
        movie_repository: MovieRepository,
        show_repository: ShowRepository,
        booking_repository: BookingRepository,
        user_repository: UserRepository,
    ) -> None:
        self.config_repository = config_repository
        self.movie_repository = movie_repository
        self.show_repository = show_repository
        self.booking_repository = booking_repository
        self.user_repository = user_repository

    def load_catalog(
        self,
    ) -> tuple[
        Cinema,
        list[Hall],
        list[Seat],
        list[Movie],
        list[MovieShow],
    ]:
        """Load the complete read-only catalog using explicit entity collections."""
        cinema, halls, seats = self.config_repository.load()
        movies = self.movie_repository.load()
        shows = self.show_repository.load(
            valid_hall_ids={hall.hall_id for hall in halls},
            valid_movie_ids={movie.movie_id for movie in movies if movie.movie_id is not None},
        )
        return cinema, halls, seats, movies, shows

    def load_bookings(
        self,
        shows: list[MovieShow] | tuple[MovieShow, ...],
        seats: list[Seat] | tuple[Seat, ...],
        users: list[User] | None = None,
    ) -> tuple[list[Booking], list[BookingSeat]]:
        """Load bookings and junction rows against explicit valid foreign keys."""
        loaded_users = users if users is not None else self.user_repository.load()
        return self.booking_repository.load(
            valid_show_ids={show.show_id for show in shows if show.show_id is not None},
            valid_user_ids={user.user_id for user in loaded_users if user.user_id is not None},
            valid_seat_ids={seat.seat_id for seat in seats},
        )

    def load(
        self,
    ) -> tuple[
        Cinema,
        list[Hall],
        list[Seat],
        list[Movie],
        list[MovieShow],
        list[User],
        list[Booking],
        list[BookingSeat],
    ]:
        """Load complete persisted application state."""
        cinema, halls, seats, movies, shows = self.load_catalog()
        users = self.user_repository.load()
        bookings, booking_seats = self.load_bookings(shows, seats, users)
        return (
            cinema,
            halls,
            seats,
            movies,
            shows,
            users,
            bookings,
            booking_seats,
        )
