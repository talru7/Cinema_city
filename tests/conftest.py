"""Shared fixtures for schema-v3 repository and service tests."""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from cinema.storage import StorageService, create_json_storage_service


@dataclass(frozen=True, slots=True)
class CinemaEnvironment:
    data_dir: Path
    config_file: Path
    movies_file: Path
    shows_file: Path
    bookings_file: Path
    users_file: Path
    state_lock_file: Path

    def storage(self) -> StorageService:
        return create_json_storage_service(
            config_file=self.config_file,
            movies_file=self.movies_file,
            shows_file=self.shows_file,
            bookings_file=self.bookings_file,
            users_file=self.users_file,
            state_lock_file=self.state_lock_file,
            bootstrap=False,
        )


@pytest.fixture
def environment(tmp_path: Path) -> CinemaEnvironment:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    env = CinemaEnvironment(
        data_dir=data_dir,
        config_file=data_dir / "cinema_config.json",
        movies_file=data_dir / "movies.json",
        shows_file=data_dir / "shows.json",
        bookings_file=data_dir / "bookings.json",
        users_file=data_dir / "users.json",
        state_lock_file=data_dir / ".cinema_state.lock",
    )

    env.config_file.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "cinema": {"cinema_id": 1, "name": "Cinema City"},
                "halls": [
                    {
                        "hall_id": 1,
                        "hall_name": "Hall Alpha",
                        "rows": 3,
                        "seats_per_row": 4,
                    },
                    {
                        "hall_id": 2,
                        "hall_name": "Hall Beta",
                        "rows": 3,
                        "seats_per_row": 4,
                    },
                    {
                        "hall_id": 3,
                        "hall_name": "Hall Gamma",
                        "rows": 3,
                        "seats_per_row": 4,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    env.movies_file.write_text(
        json.dumps({"schema_version": 3, "last_movie_id": 0, "movies": []}),
        encoding="utf-8",
    )
    env.shows_file.write_text(
        json.dumps({"schema_version": 3, "last_show_id": 0, "shows": []}),
        encoding="utf-8",
    )
    env.bookings_file.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "last_booking_id": 0,
                "bookings": [],
                "booking_seats": [],
            }
        ),
        encoding="utf-8",
    )
    env.users_file.write_text(
        json.dumps({"schema_version": 3, "last_user_id": 0, "users": []}),
        encoding="utf-8",
    )
    return env
