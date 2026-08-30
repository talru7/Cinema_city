"""End-to-end lifecycle through composition, auth, application, and JSON adapters."""

from datetime import timedelta
from pathlib import Path

import pytest

from cinema.auth import RequestCredentials
from cinema.composition import create_container
from cinema.config import AppEnvironment, Settings
from cinema.exceptions import SeatAlreadyBookedError
from cinema.models import Genre
from cinema.time_utils import local_now


def test_full_lifecycle_survives_restart(tmp_path: Path) -> None:
    settings = Settings(app_env=AppEnvironment.TEST, cinema_data_dir=tmp_path / "data")
    app = create_container(settings)
    manager_auth = app.auth.manager.authenticate(RequestCredentials())
    customer_auth = app.auth.customer.authenticate(RequestCredentials())
    movie = app.manager.add_movie(
        manager_auth,
        title="Dune",
        duration_minutes=120,
        description="Description",
        genre=Genre.DRAMA,
        ticket_price=40,
    )
    shows = app.manager.schedule_movie(
        manager_auth,
        movie_id=movie.movie_id or 0,
        screening_date=(local_now() + timedelta(days=1)).date(),
        hall_id=1,
        shows_count=1,
    )
    booking = app.bookings.create_booking(
        customer_auth,
        shows[0].show_id or 0,
        ((1, 1), (1, 2)),
    )
    assert booking.total_price == 80

    restarted = create_container(settings)
    same_customer = restarted.auth.customer.authenticate(RequestCredentials())
    assert restarted.bookings.list_my_bookings(same_customer)[0].booking_id == booking.booking_id
    with pytest.raises(SeatAlreadyBookedError):
        restarted.bookings.create_booking(
            same_customer,
            shows[0].show_id or 0,
            ((1, 1),),
        )
    assert restarted.bookings.cancel_booking(same_customer, booking.booking_id) == 2
    assert restarted.bookings.list_my_bookings(same_customer) == []
