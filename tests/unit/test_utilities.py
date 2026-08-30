"""Tests for time, bootstrap, schema, and validation utility branches."""

from datetime import date, datetime, time
from pathlib import Path
from typing import Any, cast

import pytest

from cinema.exceptions import StorageError, UserValidationError, ValidationError
from cinema.models import Genre, Movie, User
from cinema.storage import app_paths
from cinema.storage.schema import validate_schema_version
from cinema.time_utils import (
    CINEMA_TIMEZONE,
    from_storage_iso,
    local_datetime,
    local_now,
    require_aware,
    to_utc_iso,
)


def test_time_helpers_cover_aware_and_legacy_paths() -> None:
    assert local_now().tzinfo is not None
    value = local_datetime(date(2026, 9, 1), time(12, 30))
    assert value.tzinfo == CINEMA_TIMEZONE
    require_aware(value)
    assert "+00:00" in to_utc_iso(value)
    assert from_storage_iso("2026-09-01T12:00:00").tzinfo == CINEMA_TIMEZONE

    with pytest.raises(ValueError, match="timezone"):
        require_aware(datetime(2026, 9, 1, 12))


def test_schema_rejects_wrong_version_and_allows_unversioned() -> None:
    validate_schema_version({})
    with pytest.raises(StorageError, match="Unsupported"):
        validate_schema_version({"schema_version": 999})


def test_bootstrap_creates_schema_three_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = tmp_path / "runtime"
    monkeypatch.setattr(app_paths, "DATA_DIR", data)
    monkeypatch.setattr(app_paths, "CONFIG_FILE", data / "cinema_config.json")
    monkeypatch.setattr(app_paths, "MOVIES_FILE", data / "movies.json")
    monkeypatch.setattr(app_paths, "SHOWS_FILE", data / "shows.json")
    monkeypatch.setattr(app_paths, "BOOKINGS_FILE", data / "bookings.json")
    monkeypatch.setattr(app_paths, "USERS_FILE", data / "users.json")

    app_paths.bootstrap_data_directory()
    assert app_paths.CONFIG_FILE.exists()
    assert '"hall_id": 1' in app_paths.CONFIG_FILE.read_text(encoding="utf-8")
    assert '"last_movie_id": 0' in app_paths.MOVIES_FILE.read_text(encoding="utf-8")
    assert '"booking_seats": []' in app_paths.BOOKINGS_FILE.read_text(encoding="utf-8")

    # Existing directory is deliberately not modified.
    before = app_paths.CONFIG_FILE.read_text(encoding="utf-8")
    app_paths.bootstrap_data_directory()
    assert app_paths.CONFIG_FILE.read_text(encoding="utf-8") == before


@pytest.mark.parametrize(
    "kwargs",
    [
        {"movie_id": 0},
        {"title": " "},
        {"duration_minutes": 0},
        {"description": " "},
        {"description": "x" * 301},
        {"ticket_price": 100},
    ],
)
def test_movie_validation_branches(kwargs: dict[str, object]) -> None:
    values: dict[str, object] = {
        "movie_id": 1,
        "title": "Dune",
        "duration_minutes": 120,
        "description": "Description",
        "genre": Genre.DRAMA,
        "ticket_price": 40,
    }
    values.update(kwargs)
    with pytest.raises(ValidationError):
        Movie(**cast(Any, values))


@pytest.mark.parametrize(
    "args",
    [
        (0, "clerk", "subject", "Dana", "", "dana@example.com"),
        (1, "", "subject", "Dana", "", "dana@example.com"),
        (1, "clerk", "", "Dana", "", "dana@example.com"),
        (1, "clerk", "subject", " ", "", "dana@example.com"),
    ],
)
def test_user_model_validation_branches(args: tuple[object, ...]) -> None:
    with pytest.raises(UserValidationError):
        User(*cast(Any, args))
