"""JSON persistence for scheduled movie shows."""

import json
from pathlib import Path
from typing import Any

from cinema.exceptions import BusinessError, StorageError
from cinema.models import MovieShow
from cinema.storage.app_paths import SHOWS_FILE, STATE_LOCK_FILE
from cinema.storage.interfaces import ShowRepository
from cinema.storage.json_file import (
    atomic_write_json,
    exclusive_file_lock,
    exclusive_lock,
    read_json,
)
from cinema.storage.schema import SCHEMA_VERSION, validate_schema_version
from cinema.time_utils import from_storage_iso, to_utc_iso

DEFAULT_SHOWS_FILE = SHOWS_FILE


class JsonShowRepository(ShowRepository):
    """Persist movie shows in JSON while allocating show IDs."""

    def __init__(
        self,
        file_path: Path = DEFAULT_SHOWS_FILE,
        state_lock_path: Path | None = None,
    ) -> None:
        self._file_path = file_path
        self._state_lock_path = state_lock_path or (
            STATE_LOCK_FILE
            if file_path == DEFAULT_SHOWS_FILE
            else file_path.parent / ".cinema_state.lock"
        )

    def load(
        self,
        valid_hall_ids: set[int],
        valid_movie_ids: set[int],
    ) -> list[MovieShow]:
        try:
            with exclusive_file_lock(self._file_path):
                last_show_id, data = self._read_document()

            shows = [self._deserialize(item) for item in data]
            self._validate(shows, last_show_id, valid_hall_ids, valid_movie_ids)
            return shows
        except StorageError:
            raise
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            BusinessError,
        ) as error:
            raise StorageError(f"Could not load show data from {self._file_path}") from error

    def find_by_id(self, show_id: int) -> MovieShow | None:
        """Return a show without requiring the caller to supply FK snapshots."""
        try:
            with exclusive_file_lock(self._file_path):
                _, data = self._read_document()
            return next(
                (show for show in map(self._deserialize, data) if show.show_id == show_id),
                None,
            )
        except StorageError:
            raise
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            BusinessError,
        ) as error:
            raise StorageError(f"Could not load show data from {self._file_path}") from error

    def create_many(self, shows: list[MovieShow]) -> list[int]:
        if not shows:
            return []
        if any(show.show_id is not None for show in shows):
            raise StorageError("New shows must not already have IDs")

        try:
            with exclusive_lock(self._state_lock_path):
                with exclusive_file_lock(self._file_path):
                    last_show_id, data = self._read_document_for_write()
                    created = [
                        MovieShow(
                            show_id=last_show_id + index,
                            movie_id=show.movie_id,
                            hall_id=show.hall_id,
                            start_time=show.start_time,
                            ticket_price=show.ticket_price,
                        )
                        for index, show in enumerate(shows, start=1)
                    ]
                    data.extend(self._serialize(show) for show in created)
                    atomic_write_json(
                        self._file_path,
                        {
                            "schema_version": SCHEMA_VERSION,
                            "last_show_id": created[-1].show_id,
                            "shows": data,
                        },
                    )
                    return [self._require_id(show) for show in created]
        except StorageError:
            raise
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            BusinessError,
        ) as error:
            raise StorageError(f"Could not create shows in {self._file_path}") from error

    def _read_document(self) -> tuple[int, list[dict[str, Any]]]:
        document = read_json(self._file_path)
        if not isinstance(document, dict):
            raise TypeError("Show data must be a JSON object")
        validate_schema_version(document)
        shows = document.get("shows")
        last_show_id = document.get("last_show_id")
        if not isinstance(shows, list) or not isinstance(last_show_id, int):
            raise TypeError("Show data has an invalid document structure")
        return last_show_id, shows

    def _read_document_for_write(self) -> tuple[int, list[dict[str, Any]]]:
        if not self._file_path.exists() and self._file_path != DEFAULT_SHOWS_FILE:
            return 0, []
        return self._read_document()

    @staticmethod
    def _validate(
        shows: list[MovieShow],
        last_show_id: int,
        valid_hall_ids: set[int],
        valid_movie_ids: set[int],
    ) -> None:
        if any(show.show_id is None for show in shows):
            raise StorageError("Persisted show is missing its ID")
        show_ids = [show.show_id for show in shows if show.show_id is not None]
        if len(show_ids) != len(set(show_ids)):
            raise StorageError("Show data contains duplicate show IDs")
        if last_show_id < max(show_ids, default=0):
            raise StorageError("Show last_show_id is lower than an existing show ID")

        for show in shows:
            if show.hall_id not in valid_hall_ids:
                raise StorageError(f"Show references unknown hall {show.hall_id}")
            if show.movie_id not in valid_movie_ids:
                raise StorageError(f"Show references unknown movie {show.movie_id}")

    @staticmethod
    def _serialize(show: MovieShow) -> dict[str, Any]:
        if show.show_id is None:
            raise StorageError("Cannot serialize a show without an ID")
        return {
            "show_id": show.show_id,
            "movie_id": show.movie_id,
            "hall_id": show.hall_id,
            "start_time": to_utc_iso(show.start_time),
            "ticket_price": show.ticket_price,
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> MovieShow:
        return MovieShow(
            show_id=int(item["show_id"]),
            movie_id=int(item["movie_id"]),
            hall_id=int(item["hall_id"]),
            start_time=from_storage_iso(str(item["start_time"])),
            ticket_price=int(item["ticket_price"]),
        )

    @staticmethod
    def _require_id(show: MovieShow) -> int:
        if show.show_id is None:
            raise StorageError("Persisted show has no ID")
        return show.show_id
