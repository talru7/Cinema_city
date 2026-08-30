"""Repository contracts owned by the domain and application layers."""

from typing import Protocol

from cinema.models import (
    Booking,
    BookingRequest,
    BookingSeat,
    Cinema,
    Hall,
    Movie,
    MovieShow,
    Seat,
    User,
)


class CinemaConfigRepository(Protocol):
    """Persistence contract for cinema, hall, and physical-seat configuration."""

    def load(self) -> tuple[Cinema, list[Hall], list[Seat]]: ...


class MovieRepository(Protocol):
    """Persistence contract for movies."""

    def load(self) -> list[Movie]: ...

    def find_by_id(self, movie_id: int) -> Movie | None: ...

    def create(self, movie: Movie) -> int: ...


class ShowRepository(Protocol):
    """Persistence contract for movie shows."""

    def load(
        self,
        valid_hall_ids: set[int],
        valid_movie_ids: set[int],
    ) -> list[MovieShow]: ...

    def find_by_id(self, show_id: int) -> MovieShow | None: ...

    def create_many(self, shows: list[MovieShow]) -> list[int]: ...


class UserRepository(Protocol):
    """Persistence contract for provider-independent local users."""

    def load(self) -> list[User]: ...

    def find_by_id(self, user_id: int) -> User | None: ...

    def find_by_auth_identity(
        self,
        auth_provider: str,
        auth_subject: str,
    ) -> User | None: ...

    def find_by_email(self, email: str) -> User | None: ...

    def find_by_phone(self, phone_number: str) -> User | None: ...

    def create(self, user: User) -> int: ...

    def update(self, user: User) -> None: ...


class BookingRepository(Protocol):
    """Persistence contract for bookings and booking-seat junction rows."""

    def load(
        self,
        valid_show_ids: set[int],
        valid_user_ids: set[int],
        valid_seat_ids: set[int],
    ) -> tuple[list[Booking], list[BookingSeat]]: ...

    def find_by_id(self, booking_id: int) -> Booking | None: ...

    def find_by_user_id(self, user_id: int) -> list[Booking]: ...

    def add(self, request: BookingRequest) -> int: ...

    def delete(self, booking_id: int, user_id: int) -> int: ...
