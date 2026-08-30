"""Application use-case tests for authorization and failure paths."""

from datetime import timedelta
from pathlib import Path

import pytest

from cinema.auth import RequestCredentials
from cinema.composition import create_container
from cinema.config import AppEnvironment, Settings
from cinema.exceptions import BookingNotFoundError, BookingValidationError, ScheduleValidationError
from cinema.models import Genre
from cinema.time_utils import local_now


def test_catalog_filters_and_booking_failure_paths(tmp_path: Path) -> None:
    container = create_container(
        Settings(app_env=AppEnvironment.TEST, cinema_data_dir=tmp_path / "data")
    )
    manager = container.auth.manager.authenticate(RequestCredentials())
    customer = container.auth.customer.authenticate(RequestCredentials())
    movie = container.manager.add_movie(
        manager,
        title="Dune",
        duration_minutes=120,
        description="Description",
        genre=Genre.DRAMA,
        ticket_price=40,
    )
    assert container.catalog.list_movies() == [movie]
    assert container.catalog.list_upcoming_shows(genre=Genre.COMEDY) == []
    with pytest.raises(ScheduleValidationError, match="does not exist"):
        container.catalog.list_seats(999)
    with pytest.raises(BookingValidationError, match="does not exist"):
        container.bookings.create_booking(customer, 999, ((1, 1),))
    with pytest.raises(BookingNotFoundError):
        container.bookings.cancel_booking(customer, 999)


def test_past_show_cannot_be_booked(tmp_path: Path) -> None:
    container = create_container(
        Settings(app_env=AppEnvironment.TEST, cinema_data_dir=tmp_path / "data")
    )
    manager = container.auth.manager.authenticate(RequestCredentials())
    customer = container.auth.customer.authenticate(RequestCredentials())
    movie = container.manager.add_movie(
        manager,
        title="Dune",
        duration_minutes=120,
        description="Description",
        genre=Genre.DRAMA,
        ticket_price=40,
    )
    show = container.manager.schedule_movie(
        manager,
        movie_id=movie.movie_id or 0,
        screening_date=(local_now() - timedelta(days=1)).date(),
        hall_id=1,
        shows_count=1,
    )[0]
    with pytest.raises(BookingValidationError, match="already started"):
        container.bookings.create_booking(customer, show.show_id or 0, ((1, 1),))


def test_manager_rejects_missing_movie(tmp_path: Path) -> None:
    container = create_container(
        Settings(app_env=AppEnvironment.TEST, cinema_data_dir=tmp_path / "data")
    )
    manager = container.auth.manager.authenticate(RequestCredentials())
    with pytest.raises(ScheduleValidationError, match="does not exist"):
        container.manager.schedule_movie(
            manager,
            movie_id=999,
            screening_date=local_now().date(),
            hall_id=None,
            shows_count=1,
        )
