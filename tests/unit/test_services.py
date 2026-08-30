"""Unit tests for stateless business services."""

from datetime import date, datetime, time, timedelta

import pytest

from cinema.exceptions import (
    BookingValidationError,
    MovieAlreadyExistsError,
    NotEnoughScheduleSlotsError,
    ScheduleValidationError,
    SeatAlreadyBookedError,
    SeatNotFoundError,
)
from cinema.models import Booking, BookingSeat, Genre, Movie, MovieShow
from cinema.services import BookingService, CinemaManager, SchedulingService
from cinema.storage import JsonMovieRepository
from cinema.time_utils import CINEMA_TIMEZONE
from tests.conftest import CinemaEnvironment


def build_manager(environment: CinemaEnvironment) -> tuple[CinemaManager, SchedulingService]:
    storage = environment.storage()
    scheduler = SchedulingService(
        storage.config_repository,
        storage.movie_repository,
        storage.show_repository,
    )
    return CinemaManager(storage.movie_repository, scheduler), scheduler


def test_cinema_manager_is_stateless_and_repository_driven(
    environment: CinemaEnvironment,
) -> None:
    manager, _ = build_manager(environment)
    movie = manager.add_movie("Dune", 120, "Description", Genre.DRAMA, 40)

    assert movie.movie_id == 1
    assert not hasattr(manager, "_cinema")
    assert not hasattr(manager, "_next_movie_id")
    assert JsonMovieRepository(environment.movies_file).load() == [movie]


def test_cinema_manager_rejects_duplicate_title(
    environment: CinemaEnvironment,
) -> None:
    manager, _ = build_manager(environment)
    manager.add_movie("Dune", 120, "Description", Genre.DRAMA, 40)
    with pytest.raises(MovieAlreadyExistsError):
        manager.add_movie(" dune ", 90, "Other", Genre.DRAMA, 40)


def test_scheduling_service_is_stateless_and_persists_shows(
    environment: CinemaEnvironment,
) -> None:
    manager, scheduler = build_manager(environment)
    movie = manager.add_movie("Dune", 120, "Description", Genre.DRAMA, 40)

    shows = scheduler.schedule_movie(1, movie, date(2026, 9, 1), shows_count=2)

    assert [show.show_id for show in shows] == [1, 2]
    assert all(show.hall_id == 1 for show in shows)
    assert all(show.movie_id == movie.movie_id for show in shows)
    assert not hasattr(scheduler, "_shows")
    assert not hasattr(scheduler, "_next_show_id")


def test_manager_schedules_movie_in_all_halls(
    environment: CinemaEnvironment,
) -> None:
    manager, _ = build_manager(environment)
    movie = manager.add_movie("Dune", 120, "Description", Genre.DRAMA, 40)

    shows = manager.schedule_movie(movie, date(2026, 9, 1), shows_per_hall=2)

    assert len(shows) == 6
    assert {show.hall_id for show in shows} == {1, 2, 3}


def test_scheduling_avoids_existing_show(
    environment: CinemaEnvironment,
) -> None:
    manager, scheduler = build_manager(environment)
    movie = manager.add_movie("Dune", 120, "Description", Genre.DRAMA, 40)
    first = scheduler.schedule_movie(1, movie, date(2026, 9, 1), shows_count=1)[0]
    second = scheduler.schedule_movie(1, movie, date(2026, 9, 1), shows_count=1)[0]

    assert second.start_time >= first.start_time + timedelta(minutes=140)


@pytest.mark.parametrize("count", [0, -1])
def test_scheduling_rejects_invalid_count(
    environment: CinemaEnvironment,
    count: int,
) -> None:
    manager, scheduler = build_manager(environment)
    movie = manager.add_movie("Dune", 120, "Description", Genre.DRAMA, 40)
    with pytest.raises(ScheduleValidationError):
        scheduler.schedule_movie(1, movie, date(2026, 9, 1), shows_count=count)


def test_scheduling_rejects_unknown_hall(environment: CinemaEnvironment) -> None:
    manager, scheduler = build_manager(environment)
    movie = manager.add_movie("Dune", 120, "Description", Genre.DRAMA, 40)
    with pytest.raises(ScheduleValidationError, match="does not exist"):
        scheduler.schedule_movie(99, movie, date(2026, 9, 1))


def test_scheduling_rejects_movie_not_in_repository(
    environment: CinemaEnvironment,
) -> None:
    _, scheduler = build_manager(environment)
    external = Movie(99, "External", 90, "Description", Genre.DRAMA, 40)
    with pytest.raises(ScheduleValidationError, match="catalog"):
        scheduler.schedule_movie(1, external, date(2026, 9, 1))


def test_scheduling_reports_not_enough_slots(
    environment: CinemaEnvironment,
) -> None:
    storage = environment.storage()
    scheduler = SchedulingService(
        storage.config_repository,
        storage.movie_repository,
        storage.show_repository,
        opening_time=time(10),
        closing_time=time(11),
    )
    movie = CinemaManager(storage.movie_repository, scheduler).add_movie(
        "Long Movie", 120, "Description", Genre.DRAMA, 40
    )
    with pytest.raises(NotEnoughScheduleSlotsError):
        scheduler.schedule_movie(1, movie, date(2026, 9, 1), shows_count=1)


def test_scheduling_rejects_invalid_opening_hours(
    environment: CinemaEnvironment,
) -> None:
    storage = environment.storage()
    with pytest.raises(ScheduleValidationError, match="Opening"):
        SchedulingService(
            storage.config_repository,
            storage.movie_repository,
            storage.show_repository,
            opening_time=time(12),
            closing_time=time(10),
        )


def test_booking_service_creates_id_only_request(
    environment: CinemaEnvironment,
) -> None:
    storage = environment.storage()
    _, _, seats, _, _ = storage.load_catalog()
    show = MovieShow(
        1,
        1,
        1,
        datetime(2026, 9, 1, 18, tzinfo=CINEMA_TIMEZONE),
        40,
    )

    request = BookingService.prepare_booking(
        show=show,
        requested_seats=((1, 1), (1, 2)),
        user_id=7,
        seats=seats,
    )

    assert request.user_id == 7
    assert request.show_id == 1
    assert request.seat_ids == (1, 2)
    assert not hasattr(request, "show")
    assert not hasattr(request, "seats")


def test_booking_service_detects_already_booked_seat(
    environment: CinemaEnvironment,
) -> None:
    storage = environment.storage()
    _, _, seats, _, _ = storage.load_catalog()
    show = MovieShow(
        1,
        1,
        1,
        datetime(2026, 9, 1, 18, tzinfo=CINEMA_TIMEZONE),
        40,
    )
    bookings = [Booking(1, 1, 1)]
    booking_seats = [BookingSeat(1, 1, 1)]

    with pytest.raises(SeatAlreadyBookedError):
        BookingService.prepare_booking(
            show=show,
            requested_seats=((1, 1),),
            user_id=2,
            seats=seats,
            bookings=bookings,
            booking_seats=booking_seats,
        )


@pytest.mark.parametrize(
    "requested",
    [
        (),
        ((1, 1), (1, 1)),
        ((1, 1), (1, 3)),
        ((1, 1), (2, 1)),
        ((1, 1), (1, 2), (1, 3), (1, 4), (2, 1), (2, 2)),
    ],
)
def test_booking_service_rejects_invalid_seat_requests(
    environment: CinemaEnvironment,
    requested: tuple[tuple[int, int], ...],
) -> None:
    storage = environment.storage()
    _, _, seats, _, _ = storage.load_catalog()
    show = MovieShow(
        1,
        1,
        1,
        datetime(2026, 9, 1, 18, tzinfo=CINEMA_TIMEZONE),
        40,
    )
    with pytest.raises(BookingValidationError):
        BookingService.prepare_booking(
            show=show,
            requested_seats=requested,
            user_id=1,
            seats=seats,
        )


def test_booking_service_rejects_missing_seat(
    environment: CinemaEnvironment,
) -> None:
    storage = environment.storage()
    _, _, seats, _, _ = storage.load_catalog()
    show = MovieShow(
        1,
        1,
        1,
        datetime(2026, 9, 1, 18, tzinfo=CINEMA_TIMEZONE),
        40,
    )
    with pytest.raises(SeatNotFoundError):
        BookingService.prepare_booking(
            show=show,
            requested_seats=((99, 99),),
            user_id=1,
            seats=seats,
        )


def test_booking_service_cancellation_boundary_and_total() -> None:
    show = MovieShow(
        1,
        1,
        1,
        datetime(2026, 9, 1, 18, tzinfo=CINEMA_TIMEZONE),
        45,
    )
    booking = Booking(1, 1, 1)
    rows = [BookingSeat(1, 1, 10), BookingSeat(1, 1, 11)]

    BookingService.validate_cancellation(
        booking,
        show,
        show.start_time - timedelta(hours=1),
    )
    assert BookingService.total_price(booking, show, rows) == 90

    with pytest.raises(BookingValidationError):
        BookingService.validate_cancellation(
            booking,
            show,
            show.start_time - timedelta(minutes=59),
        )
