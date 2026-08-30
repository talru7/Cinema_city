"""The same repository behavior must hold for JSON and relational adapters."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from cinema.exceptions import (
    BookingNotFoundError,
    BookingValidationError,
    SeatAlreadyBookedError,
    StorageError,
    UserIdentityConflictError,
)
from cinema.models import BookingRequest, Genre, Movie, MovieShow, User
from cinema.storage import StorageService, create_json_storage_service
from cinema.storage.sqlalchemy_backend import create_neon_storage_service
from cinema.time_utils import CINEMA_TIMEZONE

StorageFactory = Callable[[Path], StorageService]


@pytest.fixture(params=["json", "sql"])
def storage(request: pytest.FixtureRequest, tmp_path: Path) -> StorageService:
    if request.param == "json":
        return create_json_storage_service(data_dir=tmp_path / "json")
    return create_neon_storage_service(f"sqlite+pysqlite:///{tmp_path / 'cinema.db'}")


def test_movie_repository_contract(storage: StorageService) -> None:
    movie_id = storage.movie_repository.create(
        Movie(None, "Dune", 120, "Description", Genre.DRAMA, 40)
    )
    assert movie_id == 1
    assert storage.movie_repository.find_by_id(movie_id) == storage.movie_repository.load()[0]


def test_user_repository_contract(storage: StorageService) -> None:
    user_id = storage.user_repository.create(
        User(None, "clerk", "subject-1", "Dana", "0501234567", "dana@example.com")
    )
    user = storage.user_repository.find_by_auth_identity("clerk", "subject-1")
    assert user is not None and user.user_id == user_id
    storage.user_repository.update(
        User(user_id, "clerk", "subject-1", "Dana Updated", "0501234567", "dana@example.com")
    )
    updated = storage.user_repository.find_by_id(user_id)
    assert updated is not None
    assert updated.full_name == "Dana Updated"


def test_show_and_booking_repository_contract(storage: StorageService) -> None:
    movie_id = storage.movie_repository.create(
        Movie(None, "Dune", 120, "Description", Genre.DRAMA, 40)
    )
    user_id = storage.user_repository.create(
        User(None, "clerk", "subject-1", "Dana", "0501234567", "dana@example.com")
    )
    show_id = storage.show_repository.create_many(
        [
            MovieShow(
                None,
                movie_id,
                1,
                datetime(2026, 9, 1, 18, tzinfo=CINEMA_TIMEZONE),
                40,
            )
        ]
    )[0]
    booking_id = storage.booking_repository.add(
        BookingRequest(user_id=user_id, show_id=show_id, seat_ids=(1, 2))
    )
    assert storage.booking_repository.find_by_user_id(user_id)[0].booking_id == booking_id
    _, rows = storage.booking_repository.load({show_id}, {user_id}, {1, 2})
    assert {(row.show_id, row.seat_id) for row in rows} == {(show_id, 1), (show_id, 2)}
    with pytest.raises(SeatAlreadyBookedError):
        storage.booking_repository.add(
            BookingRequest(user_id=user_id, show_id=show_id, seat_ids=(1,))
        )
    assert storage.booking_repository.delete(booking_id, user_id) == 2


def test_relational_adapter_error_and_lookup_contracts(tmp_path: Path) -> None:
    storage = create_neon_storage_service(f"sqlite+pysqlite:///{tmp_path / 'errors.db'}")
    movies = storage.movie_repository
    movie_id = movies.create(Movie(None, "Dune", 120, "Description", Genre.DRAMA, 40))
    with pytest.raises(StorageError, match="already exists"):
        movies.create(Movie(None, "Dune", 120, "Description", Genre.DRAMA, 40))
    assert movies.find_by_id(999) is None

    user_id = storage.user_repository.create(
        User(None, "clerk", "subject-1", "Dana", "0501234567", "dana@example.com")
    )
    assert storage.user_repository.find_by_email("dana@example.com") is not None
    assert storage.user_repository.find_by_phone("0501234567") is not None
    assert storage.user_repository.find_by_email("") is None
    with pytest.raises(UserIdentityConflictError):
        storage.user_repository.create(
            User(None, "clerk", "subject-2", "Other", "", "dana@example.com")
        )
    with pytest.raises(StorageError, match="does not exist"):
        storage.user_repository.update(
            User(99, "clerk", "missing", "Missing", "", "missing@example.com")
        )

    show_id = storage.show_repository.create_many(
        [
            MovieShow(
                None,
                movie_id,
                1,
                datetime(2026, 9, 1, 18, tzinfo=CINEMA_TIMEZONE),
                40,
            )
        ]
    )[0]
    assert storage.show_repository.find_by_id(999) is None
    with pytest.raises(StorageError, match="unknown hall"):
        storage.show_repository.load(set(), {movie_id})
    booking_id = storage.booking_repository.add(BookingRequest(user_id, show_id, (1,)))
    assert storage.booking_repository.find_by_id(999) is None
    with pytest.raises(BookingValidationError):
        storage.booking_repository.delete(booking_id, user_id + 1)
    with pytest.raises(BookingNotFoundError):
        storage.booking_repository.delete(999, user_id)
