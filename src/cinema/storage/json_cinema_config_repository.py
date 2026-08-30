"""JSON persistence for cinema, hall, and seat configuration."""

import json
from pathlib import Path
from typing import Any

from cinema.exceptions import BusinessError, StorageError
from cinema.models import Cinema, Hall, Seat
from cinema.storage.app_paths import CONFIG_FILE
from cinema.storage.interfaces import CinemaConfigRepository
from cinema.storage.json_file import exclusive_file_lock, read_json
from cinema.storage.schema import validate_schema_version

DEFAULT_CONFIG_FILE = CONFIG_FILE


class JsonCinemaConfigRepository(CinemaConfigRepository):
    """Load the static cinema configuration from JSON."""

    def __init__(self, file_path: Path = DEFAULT_CONFIG_FILE) -> None:
        self._file_path = file_path

    def load(self) -> tuple[Cinema, list[Hall], list[Seat]]:
        try:
            with exclusive_file_lock(self._file_path):
                data: dict[str, Any] = read_json(self._file_path)

            validate_schema_version(data)
            cinema_data = data["cinema"]
            raw_halls = data["halls"]

            cinema = Cinema(
                cinema_id=int(cinema_data["cinema_id"]),
                name=str(cinema_data["name"]),
            )

            halls = [
                Hall(
                    hall_id=int(item["hall_id"]),
                    hall_name=str(item["hall_name"]),
                )
                for item in raw_halls
            ]
            self._validate_halls(halls)

            seats: list[Seat] = []
            next_seat_id = 1
            for item in sorted(raw_halls, key=lambda hall: int(hall["hall_id"])):
                hall_id = int(item["hall_id"])
                rows = int(item["rows"])
                seats_per_row = int(item["seats_per_row"])
                if rows <= 0 or seats_per_row <= 0:
                    raise StorageError("Hall dimensions must be positive")

                for row_number in range(1, rows + 1):
                    for seat_number in range(1, seats_per_row + 1):
                        seats.append(
                            Seat(
                                seat_id=next_seat_id,
                                hall_id=hall_id,
                                row_number=row_number,
                                seat_number=seat_number,
                            )
                        )
                        next_seat_id += 1

            return cinema, halls, seats
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
            raise StorageError(
                f"Could not load cinema configuration from {self._file_path}"
            ) from error

    @staticmethod
    def _validate_halls(halls: list[Hall]) -> None:
        hall_ids = [hall.hall_id for hall in halls]
        if len(hall_ids) != len(set(hall_ids)):
            raise StorageError("Cinema configuration contains duplicate hall IDs")

        names = [hall.hall_name.strip().casefold() for hall in halls]
        if len(names) != len(set(names)):
            raise StorageError("Cinema configuration contains duplicate hall names")
