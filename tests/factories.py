"""Factories used by multiple tests for the ID-only domain model."""

from datetime import datetime

from cinema.models import Cinema, Genre, Hall, Movie, MovieShow, Seat, User
from cinema.time_utils import CINEMA_TIMEZONE


def make_cinema(
    cinema_id: int = 1,
    name: str = "Cinema City",
) -> Cinema:
    return Cinema(cinema_id=cinema_id, name=name)


def make_halls(count: int = 3) -> list[Hall]:
    return [Hall(hall_id=index, hall_name=f"Hall {index}") for index in range(1, count + 1)]


def make_seats(
    halls: list[Hall],
    rows: int = 20,
    seats_per_row: int = 20,
) -> list[Seat]:
    seats: list[Seat] = []
    seat_id = 1
    for hall in halls:
        for row_number in range(1, rows + 1):
            for seat_number in range(1, seats_per_row + 1):
                seats.append(
                    Seat(
                        seat_id=seat_id,
                        hall_id=hall.hall_id,
                        row_number=row_number,
                        seat_number=seat_number,
                    )
                )
                seat_id += 1
    return seats


def make_movie(
    movie_id: int = 1,
    title: str = "Back to the Future",
    duration_minutes: int = 120,
    genre: Genre = Genre.DRAMA,
    ticket_price: int = 40,
) -> Movie:
    return Movie(
        movie_id=movie_id,
        title=title,
        duration_minutes=duration_minutes,
        description="A short movie description.",
        genre=genre,
        ticket_price=ticket_price,
    )


def make_show(
    *,
    show_id: int = 1,
    movie_id: int = 1,
    hall_id: int = 1,
    hour: int = 18,
    minute: int = 0,
    ticket_price: int = 40,
    **_: object,
) -> MovieShow:
    return MovieShow(
        show_id=show_id,
        movie_id=movie_id,
        hall_id=hall_id,
        start_time=datetime(2026, 8, 23, hour, minute, tzinfo=CINEMA_TIMEZONE),
        ticket_price=ticket_price,
    )


def make_small_hall(hall_id: int = 1) -> Hall:
    return Hall(hall_id=hall_id, hall_name=f"Hall {hall_id}")


def make_small_seats(hall_id: int = 1) -> list[Seat]:
    return [
        Seat(
            seat_id=index,
            hall_id=hall_id,
            row_number=row_number,
            seat_number=seat_number,
        )
        for index, (row_number, seat_number) in enumerate(
            ((1, 1), (1, 2), (2, 1), (2, 2)),
            start=1,
        )
    ]


def make_user(
    user_id: int = 1,
    full_name: str = "Dana Cohen",
    phone_number: str = "+972501234567",
    email: str = "dana@example.com",
) -> User:
    return User(
        user_id=user_id,
        auth_provider="local",
        auth_subject=email,
        full_name=full_name,
        phone_number=phone_number,
        email=email,
    )
