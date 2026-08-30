"""Focused unit tests for JSON repository safety and integrity."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from cinema.exceptions import (
    BookingNotFoundError,
    BookingValidationError,
    SeatAlreadyBookedError,
    StorageError,
)
from cinema.models import BookingRequest, Genre, Movie, MovieShow
from cinema.storage import (
    BookingRepository,
    CinemaConfigRepository,
    JsonBookingRepository,
    JsonCinemaConfigRepository,
    JsonMovieRepository,
    JsonShowRepository,
    JsonUserRepository,
    MovieRepository,
    ShowRepository,
    UserRepository,
)
from cinema.storage.schema import SCHEMA_VERSION
from cinema.time_utils import CINEMA_TIMEZONE
from tests.conftest import CinemaEnvironment


def test_repository_protocols_are_separate_from_implementations() -> None:
    assert JsonMovieRepository is not MovieRepository
    assert JsonShowRepository is not ShowRepository
    assert JsonUserRepository is not UserRepository
    assert JsonBookingRepository is not BookingRepository
    assert JsonCinemaConfigRepository is not CinemaConfigRepository


def test_json_config_loads_clean_entities(environment: CinemaEnvironment) -> None:
    cinema, halls, seats = JsonCinemaConfigRepository(environment.config_file).load()
    assert cinema.cinema_id == 1
    assert [hall.hall_name for hall in halls] == ["Hall Alpha", "Hall Beta", "Hall Gamma"]
    assert len(seats) == 36
    assert seats[0].seat_id == 1


@pytest.mark.parametrize(
    ("halls", "message"),
    [
        (
            [
                {"hall_id": 1, "hall_name": "A", "rows": 1, "seats_per_row": 1},
                {"hall_id": 1, "hall_name": "B", "rows": 1, "seats_per_row": 1},
            ],
            "duplicate hall IDs",
        ),
        (
            [
                {"hall_id": 1, "hall_name": "Same", "rows": 1, "seats_per_row": 1},
                {"hall_id": 2, "hall_name": " same ", "rows": 1, "seats_per_row": 1},
            ],
            "duplicate hall names",
        ),
    ],
)
def test_json_config_rejects_duplicate_halls(
    tmp_path: Path,
    halls: list[dict[str, object]],
    message: str,
) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "cinema": {"cinema_id": 1, "name": "Cinema"},
                "halls": halls,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(StorageError, match=message):
        JsonCinemaConfigRepository(path).load()


def test_movie_repository_entity_contract(environment: CinemaEnvironment) -> None:
    repo = JsonMovieRepository(environment.movies_file, environment.state_lock_file)
    first_id = repo.create(_movie("Dune"))
    second_id = repo.create(_movie("Alien", Genre.THRILLER))
    assert (first_id, second_id) == (1, 2)
    assert repo.find_by_id(1) == repo.load()[0]
    assert repo.find_by_id(99) is None
    with pytest.raises(StorageError, match="already exists"):
        repo.create(_movie("  dune "))
    with pytest.raises(StorageError, match="must not already have an ID"):
        repo.create(Movie(7, "Other", 100, "Description", Genre.DRAMA, 40))


def test_movie_repository_rejects_corrupt_metadata(tmp_path: Path) -> None:
    path = tmp_path / "movies.json"
    movie = {
        "movie_id": 2,
        "title": "Dune",
        "duration_minutes": 120,
        "description": "Description",
        "genre": "drama",
        "ticket_price": 40,
    }
    path.write_text(
        json.dumps({"schema_version": 3, "last_movie_id": 0, "movies": [movie]}),
        encoding="utf-8",
    )
    with pytest.raises(StorageError, match="last_movie_id"):
        JsonMovieRepository(path).load()


def test_show_repository_entity_contract(environment: CinemaEnvironment) -> None:
    repo = JsonShowRepository(environment.shows_file, environment.state_lock_file)
    show = _show(movie_id=1, hall_id=2)
    assert repo.create_many([show]) == [1]
    persisted = repo.find_by_id(1)
    assert persisted is not None
    assert persisted.movie_id == 1 and persisted.hall_id == 2
    assert repo.load({1, 2, 3}, {1}) == [persisted]
    assert repo.find_by_id(99) is None
    with pytest.raises(StorageError, match="must not already have IDs"):
        repo.create_many([MovieShow(4, 1, 1, show.start_time, 40)])


def test_show_repository_validates_foreign_keys(environment: CinemaEnvironment) -> None:
    repo = JsonShowRepository(environment.shows_file, environment.state_lock_file)
    repo.create_many([_show(movie_id=9, hall_id=8)])
    with pytest.raises(StorageError, match="unknown hall"):
        repo.load({1}, {1})


def test_booking_repository_contract_and_explicit_show_id(
    environment: CinemaEnvironment,
) -> None:
    repo = JsonBookingRepository(environment.bookings_file)
    booking_id = repo.add(BookingRequest(user_id=1, show_id=7, seat_ids=(2, 3)))
    assert booking_id == 1
    booking = repo.find_by_id(booking_id)
    assert booking is not None and booking.user_id == 1
    assert repo.find_by_user_id(1) == [booking]
    bookings, rows = repo.load({7}, {1}, {1, 2, 3})
    assert bookings == [booking]
    assert {(row.show_id, row.seat_id) for row in rows} == {(7, 2), (7, 3)}
    document = json.loads(environment.bookings_file.read_text(encoding="utf-8"))
    assert document["booking_seats"][0]["show_id"] == 7


def test_booking_repository_prevents_double_booking(
    environment: CinemaEnvironment,
) -> None:
    repo = JsonBookingRepository(environment.bookings_file)
    repo.add(BookingRequest(user_id=1, show_id=7, seat_ids=(2,)))
    with pytest.raises(SeatAlreadyBookedError):
        repo.add(BookingRequest(user_id=2, show_id=7, seat_ids=(2,)))
    assert repo.add(BookingRequest(user_id=2, show_id=8, seat_ids=(2,))) == 2


def test_booking_delete_checks_owner_and_releases_seats(
    environment: CinemaEnvironment,
) -> None:
    repo = JsonBookingRepository(environment.bookings_file)
    booking_id = repo.add(BookingRequest(user_id=1, show_id=7, seat_ids=(2, 3)))
    with pytest.raises(BookingValidationError):
        repo.delete(booking_id, 2)
    with pytest.raises(BookingNotFoundError):
        repo.delete(99, 1)
    assert repo.delete(booking_id, 1) == 2
    assert repo.load({7}, {1}, {1, 2, 3}) == ([], [])


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (
            {
                "schema_version": 3,
                "last_booking_id": 1,
                "bookings": [{"booking_id": 1, "user_id": 9, "show_id": 7}],
                "booking_seats": [],
            },
            "unknown user",
        ),
        (
            {
                "schema_version": 3,
                "last_booking_id": 1,
                "bookings": [{"booking_id": 1, "user_id": 1, "show_id": 7}],
                "booking_seats": [{"booking_id": 1, "show_id": 8, "seat_id": 2}],
            },
            "does not match",
        ),
    ],
)
def test_booking_repository_rejects_invalid_foreign_keys(
    tmp_path: Path,
    document: dict[str, object],
    message: str,
) -> None:
    path = tmp_path / "bookings.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(StorageError, match=message):
        JsonBookingRepository(path).load({7, 8}, {1}, {1, 2, 3})


def test_schema_version_constant_is_three() -> None:
    assert SCHEMA_VERSION == 3


def _movie(title: str, genre: Genre = Genre.DRAMA) -> Movie:
    return Movie(None, title, 120, "Description", genre, 40)


def _show(movie_id: int, hall_id: int) -> MovieShow:
    return MovieShow(
        show_id=None,
        movie_id=movie_id,
        hall_id=hall_id,
        start_time=datetime(2026, 9, 1, 18, tzinfo=CINEMA_TIMEZONE),
        ticket_price=40,
    )
