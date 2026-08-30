"""Unit tests for clean database-oriented entities."""

from collections.abc import Callable
from datetime import datetime
from typing import Any, cast

import pytest

from cinema.exceptions import BookingValidationError, ScheduleValidationError, ValidationError
from cinema.models import Booking, BookingSeat, Cinema, Genre, Hall, Movie, MovieShow, Seat, User
from cinema.time_utils import CINEMA_TIMEZONE


def test_database_entities_contain_only_scalar_ids_and_values() -> None:
    cinema = Cinema(1, "Cinema City")
    hall = Hall(1, "Hall Alpha")
    seat = Seat(1, 1, 2, 3)
    movie = Movie(1, "Dune", 120, "Description", Genre.DRAMA, 40)
    show = MovieShow(1, 1, 1, datetime(2026, 9, 1, 18, tzinfo=CINEMA_TIMEZONE), 40)
    booking = Booking(1, 1, 1)
    booking_seat = BookingSeat(1, 1, 1)
    user = User(
        1,
        "clerk",
        "subject-1",
        "Dana Cohen",
        "+972501234567",
        "dana@example.com",
    )

    assert cinema.cinema_id == 1
    assert hall.hall_name == "Hall Alpha"
    assert seat.hall_id == 1
    assert show.movie_id == movie.movie_id
    assert show.hall_id == hall.hall_id
    assert booking.show_id == show.show_id
    assert booking_seat.seat_id == seat.seat_id
    assert user.user_id == booking.user_id

    for entity in (cinema, hall, seat, movie, show, booking, booking_seat, user):
        assert not hasattr(entity, "halls")
        assert not hasattr(entity, "movies")
        assert not hasattr(entity, "movie")
        assert not hasattr(entity, "show")
        assert not hasattr(entity, "seats")


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: Cinema(0, "Cinema"), "Cinema ID"),
        (lambda: Cinema(1, " "), "Cinema name"),
        (lambda: Hall(0, "Hall"), "Hall ID"),
        (lambda: Hall(1, " "), "Hall name"),
        (lambda: Seat(0, 1, 1, 1), "Seat ID"),
        (lambda: Seat(1, 0, 1, 1), "hall ID"),
        (lambda: Seat(1, 1, 0, 1), "row number"),
        (lambda: Seat(1, 1, 1, 0), "Seat number"),
    ],
)
def test_core_entities_reject_invalid_values(
    factory: Callable[[], object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        factory()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"show_id": 0},
        {"movie_id": 0},
        {"hall_id": 0},
        {"ticket_price": 0},
    ],
)
def test_movie_show_rejects_invalid_values(kwargs: dict[str, int]) -> None:
    values = {
        "show_id": 1,
        "movie_id": 1,
        "hall_id": 1,
        "start_time": datetime(2026, 9, 1, 18, tzinfo=CINEMA_TIMEZONE),
        "ticket_price": 40,
    }
    values.update(kwargs)
    with pytest.raises(ScheduleValidationError):
        MovieShow(**cast(Any, values))


def test_movie_show_rejects_naive_datetime() -> None:
    with pytest.raises(ScheduleValidationError, match="timezone-aware"):
        MovieShow(1, 1, 1, datetime(2026, 9, 1, 18), 40)


@pytest.mark.parametrize(
    "booking",
    [
        lambda: Booking(0, 1, 1),
        lambda: Booking(1, 0, 1),
        lambda: Booking(1, 1, 0),
        lambda: BookingSeat(0, 1, 1),
        lambda: BookingSeat(1, 0, 1),
        lambda: BookingSeat(1, 1, 0),
    ],
)
def test_booking_entities_reject_invalid_ids(booking: Callable[[], object]) -> None:
    with pytest.raises(BookingValidationError):
        booking()
