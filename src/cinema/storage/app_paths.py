"""Central runtime paths for cinema data, logs, and application locks."""

import os
from pathlib import Path

from platformdirs import user_data_path, user_log_path

from cinema.storage.schema import SCHEMA_VERSION

APP_NAME = "CinemaCity"


def _runtime_path(environment_name: str, default_path: Path) -> Path:
    configured = os.environ.get(environment_name)
    return Path(configured).expanduser().resolve() if configured else default_path.resolve()


DATA_DIR = _runtime_path(
    "CINEMA_DATA_DIR",
    user_data_path(APP_NAME, appauthor=False),
)
LOG_DIR = _runtime_path(
    "CINEMA_LOG_DIR",
    user_log_path(APP_NAME, appauthor=False),
)

CONFIG_FILE = DATA_DIR / "cinema_config.json"
MOVIES_FILE = DATA_DIR / "movies.json"
SHOWS_FILE = DATA_DIR / "shows.json"
BOOKINGS_FILE = DATA_DIR / "bookings.json"
USERS_FILE = DATA_DIR / "users.json"
STATE_LOCK_FILE = DATA_DIR / ".cinema_state.lock"
LOG_FILE = LOG_DIR / "cinema.log"


def bootstrap_data_directory() -> None:
    """Create the complete current-schema data set when the data directory is absent."""
    bootstrap_files(DATA_DIR)


def bootstrap_files(data_dir: Path) -> None:
    """Create a complete current-schema JSON data set in one directory."""
    expected = {
        "cinema_config.json",
        "movies.json",
        "shows.json",
        "bookings.json",
        "users.json",
    }
    existing = {path.name for path in data_dir.glob("*.json")} if data_dir.exists() else set()
    if expected.issubset(existing):
        return
    if existing:
        missing = ", ".join(sorted(expected - existing))
        raise RuntimeError(f"JSON data directory is incomplete; missing: {missing}")

    data_dir.mkdir(parents=True, exist_ok=True)

    (data_dir / "cinema_config.json").write_text(
        "{\n"
        f'  "schema_version": {SCHEMA_VERSION},\n'
        '  "cinema": {"cinema_id": 1, "name": "Cinema City"},\n'
        '  "halls": [\n'
        '    {"hall_id": 1, "hall_name": "Hall 1", '
        '"rows": 20, "seats_per_row": 20},\n'
        '    {"hall_id": 2, "hall_name": "Hall 2", '
        '"rows": 20, "seats_per_row": 20},\n'
        '    {"hall_id": 3, "hall_name": "Hall 3", '
        '"rows": 20, "seats_per_row": 20}\n'
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )
    (data_dir / "movies.json").write_text(
        f'{{\n  "schema_version": {SCHEMA_VERSION},\n  "last_movie_id": 0,\n  "movies": []\n}}\n',
        encoding="utf-8",
    )
    (data_dir / "shows.json").write_text(
        f'{{\n  "schema_version": {SCHEMA_VERSION},\n  "last_show_id": 0,\n  "shows": []\n}}\n',
        encoding="utf-8",
    )
    (data_dir / "bookings.json").write_text(
        f'{{\n  "schema_version": {SCHEMA_VERSION},\n'
        '  "last_booking_id": 0,\n'
        '  "bookings": [],\n'
        '  "booking_seats": []\n}\n',
        encoding="utf-8",
    )
    (data_dir / "users.json").write_text(
        f'{{\n  "schema_version": {SCHEMA_VERSION},\n  "last_user_id": 0,\n  "users": []\n}}\n',
        encoding="utf-8",
    )


def ensure_log_directory() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
