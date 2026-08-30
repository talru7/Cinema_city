"""Boundary tests for shared CLI behavior and interactive use cases."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cinema.cli import customer_cli, manager_cli
from cinema.cli.error_handling import run_cli_safely
from cinema.exceptions import StorageError
from cinema.models import Genre
from cinema.services import (
    BookingService,
    CinemaManager,
    LocalUserService,
    SchedulingService,
)
from cinema.storage import StorageService
from cinema.time_utils import CINEMA_TIMEZONE
from tests.conftest import CinemaEnvironment


def test_customer_show_filters_and_prints(
    environment: CinemaEnvironment,
    capsys: pytest.CaptureFixture[str],
) -> None:
    storage = environment.storage()
    manager, scheduler = _manager(storage)
    movie = manager.add_movie("Dune", 120, "Description", Genre.DRAMA, 40)
    shows = scheduler.schedule_movie(1, movie, date(2026, 9, 1), 1)
    _, halls, _, movies, _ = storage.load_catalog()
    now = datetime(2026, 9, 1, 10, tzinfo=CINEMA_TIMEZONE)
    assert customer_cli.list_upcoming_shows(shows, movies, halls, now) == tuple(shows)
    assert customer_cli.get_upcoming_shows_by_genre(shows, movies, now, Genre.DRAMA)
    assert "Dune" in capsys.readouterr().out


def test_cli_input_validation_retries(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    values = iter(["bad", "0", "2"])
    monkeypatch.setattr("builtins.input", lambda _: next(values))
    assert customer_cli.read_positive_int("Number: ") == 2
    prices = iter(["bad", "120", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(prices))
    assert manager_cli.read_ticket_price() == 40
    assert "whole number" in capsys.readouterr().out


def test_manager_helpers_add_find_and_schedule(
    environment: CinemaEnvironment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = environment.storage()
    manager, _ = _manager(storage)
    answers = iter(["Dune", "120", "Description", "2", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    movie = manager_cli.add_movie_interactively(manager)
    assert manager_cli.find_movie_by_id_or_title([movie], "dune") == movie
    monkeypatch.setattr("builtins.input", lambda _: str(movie.movie_id))
    assert manager_cli.schedule_movie_interactively([movie], manager)


def test_customer_booking_and_cancellation_flow(
    environment: CinemaEnvironment,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    storage = environment.storage()
    manager, scheduler = _manager(storage)
    movie = manager.add_movie("Dune", 120, "Description", Genre.DRAMA, 40)
    show = scheduler.schedule_movie(1, movie, date(2026, 9, 1), 1)[0]
    _, halls, seats, movies, shows = storage.load_catalog()
    now = show.start_time - timedelta(hours=2)
    answers = iter(
        [str(show.show_id), "Dana Cohen", "0501234567", "dana@example.com", "2", "1", "1"]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    customer_cli.book_show_interactively(
        halls=halls,
        seats=seats,
        movies=movies,
        shows=shows,
        booking_repository=storage.booking_repository,
        user_repository=storage.user_repository,
        current_time=now,
    )
    assert "confirmed" in capsys.readouterr().out
    cancel = iter(["1", "0501234567"])
    monkeypatch.setattr("builtins.input", lambda _: next(cancel))
    customer_cli.cancel_booking_interactively(
        seats=seats,
        shows=shows,
        booking_repository=storage.booking_repository,
        user_repository=storage.user_repository,
        current_time=now,
    )
    assert "cancelled" in capsys.readouterr().out


def test_safe_wrapper_reports_expected_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("cinema.cli.error_handling.configure_logging", lambda: None)
    with pytest.raises(SystemExit):
        run_cli_safely(lambda: (_ for _ in ()).throw(StorageError("disk")))
    assert "Application error" in capsys.readouterr().out


def test_manager_listing_and_report_helpers(
    environment: CinemaEnvironment,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    storage = environment.storage()
    manager, scheduler = _manager(storage)
    movie = manager.add_movie("Dune", 120, "Description", Genre.DRAMA, 40)
    scheduler.schedule_movie(1, movie, date(2026, 9, 1), 1)
    _, halls, seats, movies, shows = storage.load_catalog()
    manager_cli.list_movies(movies)
    monkeypatch.setattr("builtins.input", lambda _: "1")
    manager_cli.list_shows_by_hall(halls, movies, shows)
    user = LocalUserService(storage.user_repository).get_or_update(
        "Dana Cohen", "0501234567", "dana@example.com"
    )
    request = BookingService.prepare_booking(
        show=shows[0],
        requested_seats=((1, 1),),
        user_id=user.user_id or 0,
        seats=seats,
    )
    storage.booking_repository.add(request)
    bookings, rows = storage.load_bookings(shows, seats, [user])
    manager_cli.list_bookings(bookings, rows, seats, shows, movies, halls)
    manager_cli.print_report(storage)
    output = capsys.readouterr().out
    assert "Dune" in output and "Cinema Report" in output and "Seats: R1-S1" in output


def test_customer_menu_routes_all_options(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = MagicMock()
    storage.load_catalog.return_value = (MagicMock(), [], [], [], [])
    container = SimpleNamespace(storage=storage)
    monkeypatch.setattr(customer_cli, "create_container", lambda _: container)
    monkeypatch.setattr(customer_cli, "load_settings", MagicMock())
    list_all = MagicMock()
    list_genre = MagicMock()
    book = MagicMock()
    cancel = MagicMock()
    monkeypatch.setattr(customer_cli, "list_upcoming_shows", list_all)
    monkeypatch.setattr(customer_cli, "list_upcoming_shows_by_genre", list_genre)
    monkeypatch.setattr(customer_cli, "book_show_interactively", book)
    monkeypatch.setattr(customer_cli, "cancel_booking_interactively", cancel)
    answers = iter(["1", "2", "3", "4", "unknown", "5"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    customer_cli.run_customer_cli()
    list_all.assert_called_once()
    list_genre.assert_called_once()
    book.assert_called_once()
    cancel.assert_called_once()


def test_manager_menu_routes_all_options(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = MagicMock()
    storage.movie_repository.load.return_value = []
    storage.user_repository.load.return_value = []
    storage.load_catalog.return_value = (MagicMock(), [], [], [], [])
    storage.load_bookings.return_value = ([], [])
    container = SimpleNamespace(storage=storage)
    monkeypatch.setattr(manager_cli, "create_container", lambda _: container)
    monkeypatch.setattr(manager_cli, "load_settings", MagicMock())
    helpers = {
        name: MagicMock()
        for name in (
            "add_movie_interactively",
            "schedule_movie_interactively",
            "list_movies",
            "list_shows_by_hall",
            "list_bookings",
            "print_report",
        )
    }
    for name, helper in helpers.items():
        monkeypatch.setattr(manager_cli, name, helper)
    answers = iter(["1", "2", "3", "4", "5", "6", "unknown", "7"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    manager_cli.run_manager_cli()
    assert all(helper.call_count == 1 for helper in helpers.values())


def test_safe_wrapper_logs_unexpected_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("cinema.cli.error_handling.configure_logging", lambda: None)
    logger = MagicMock()
    monkeypatch.setattr("cinema.cli.error_handling.LOGGER", logger)
    with pytest.raises(SystemExit):
        run_cli_safely(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    logger.exception.assert_called_once()
    assert "Unexpected" in capsys.readouterr().out


def _manager(storage: StorageService) -> tuple[CinemaManager, SchedulingService]:
    scheduler = SchedulingService(
        storage.config_repository,
        storage.movie_repository,
        storage.show_repository,
    )
    return CinemaManager(storage.movie_repository, scheduler), scheduler
