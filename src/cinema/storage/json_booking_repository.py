"""JSON persistence for bookings and booking-seat junction rows."""

import json
from pathlib import Path
from typing import Any

from cinema.exceptions import (
    BookingNotFoundError,
    BookingValidationError,
    BusinessError,
    SeatAlreadyBookedError,
    StorageError,
)
from cinema.models import Booking, BookingRequest, BookingSeat
from cinema.storage.app_paths import BOOKINGS_FILE
from cinema.storage.interfaces import BookingRepository
from cinema.storage.json_file import atomic_write_json, exclusive_file_lock, read_json
from cinema.storage.schema import SCHEMA_VERSION, validate_schema_version

DEFAULT_BOOKINGS_FILE = BOOKINGS_FILE


class JsonBookingRepository(BookingRepository):
    """Persist booking and booking_seats rows in one JSON document."""

    def __init__(self, file_path: Path = DEFAULT_BOOKINGS_FILE) -> None:
        self._file_path = file_path

    def load(
        self,
        valid_show_ids: set[int],
        valid_user_ids: set[int],
        valid_seat_ids: set[int],
    ) -> tuple[list[Booking], list[BookingSeat]]:
        try:
            with exclusive_file_lock(self._file_path):
                last_booking_id, bookings_data, booking_seats_data = self._read_document()

            bookings = [self._deserialize_booking(item) for item in bookings_data]
            booking_seats = [self._deserialize_booking_seat(item) for item in booking_seats_data]
            self._validate(
                bookings,
                booking_seats,
                last_booking_id,
                valid_show_ids,
                valid_user_ids,
                valid_seat_ids,
            )
            return bookings, booking_seats
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
            raise StorageError(f"Could not load booking data from {self._file_path}") from error

    def find_by_id(self, booking_id: int) -> Booking | None:
        """Return one booking without resolving its foreign keys."""
        try:
            with exclusive_file_lock(self._file_path):
                _, bookings_data, _ = self._read_document()
            return next(
                (
                    booking
                    for booking in map(self._deserialize_booking, bookings_data)
                    if booking.booking_id == booking_id
                ),
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
            raise StorageError(f"Could not load booking data from {self._file_path}") from error

    def find_by_user_id(self, user_id: int) -> list[Booking]:
        """Return all bookings owned by one local user."""
        try:
            with exclusive_file_lock(self._file_path):
                _, bookings_data, _ = self._read_document()
            return [
                booking
                for booking in map(self._deserialize_booking, bookings_data)
                if booking.user_id == user_id
            ]
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
            raise StorageError(f"Could not load booking data from {self._file_path}") from error

    def add(self, request: BookingRequest) -> int:
        try:
            with exclusive_file_lock(self._file_path):
                last_booking_id, bookings_data, booking_seats_data = self._read_document_for_write()

                bookings = [self._deserialize_booking(item) for item in bookings_data]
                booking_seats = [
                    self._deserialize_booking_seat(item) for item in booking_seats_data
                ]

                booked_ids = {
                    row.seat_id
                    for row in booking_seats
                    if any(
                        booking.booking_id == row.booking_id and booking.show_id == request.show_id
                        for booking in bookings
                    )
                }
                overlap = booked_ids.intersection(request.seat_ids)
                if overlap:
                    seat_id = min(overlap)
                    raise SeatAlreadyBookedError(
                        f"Seat ID {seat_id} is already booked for show {request.show_id}"
                    )

                booking = Booking(
                    booking_id=last_booking_id + 1,
                    user_id=request.user_id,
                    show_id=request.show_id,
                )
                assert booking.booking_id is not None
                rows = [
                    BookingSeat(
                        booking_id=booking.booking_id,
                        show_id=request.show_id,
                        seat_id=seat_id,
                    )
                    for seat_id in request.seat_ids
                ]

                bookings_data.append(self._serialize_booking(booking))
                booking_seats_data.extend(self._serialize_booking_seat(row) for row in rows)
                atomic_write_json(
                    self._file_path,
                    {
                        "schema_version": SCHEMA_VERSION,
                        "last_booking_id": booking.booking_id,
                        "bookings": bookings_data,
                        "booking_seats": booking_seats_data,
                    },
                )
                return booking.booking_id
        except (StorageError, SeatAlreadyBookedError):
            raise
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            BusinessError,
        ) as error:
            raise StorageError(f"Could not add booking data to {self._file_path}") from error

    def delete(
        self,
        booking_id: int,
        user_id: int,
    ) -> int:
        try:
            with exclusive_file_lock(self._file_path):
                last_booking_id, bookings_data, booking_seats_data = self._read_document_for_write()
                bookings = [self._deserialize_booking(item) for item in bookings_data]
                booking = next(
                    (item for item in bookings if item.booking_id == booking_id),
                    None,
                )
                if booking is None:
                    raise BookingNotFoundError(f"Booking {booking_id} does not exist")
                if booking.user_id != user_id:
                    raise BookingValidationError("Booking ID and phone number do not match")

                removed_rows = [
                    self._deserialize_booking_seat(item)
                    for item in booking_seats_data
                    if int(item["booking_id"]) == booking_id
                ]
                remaining_bookings = [
                    item for item in bookings_data if int(item["booking_id"]) != booking_id
                ]
                remaining_seats = [
                    item for item in booking_seats_data if int(item["booking_id"]) != booking_id
                ]
                atomic_write_json(
                    self._file_path,
                    {
                        "schema_version": SCHEMA_VERSION,
                        "last_booking_id": last_booking_id,
                        "bookings": remaining_bookings,
                        "booking_seats": remaining_seats,
                    },
                )
                return len(removed_rows)
        except (StorageError, BookingNotFoundError, BookingValidationError):
            raise
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            BusinessError,
        ) as error:
            raise StorageError(f"Could not delete booking data in {self._file_path}") from error

    def _read_document(
        self,
    ) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
        document = read_json(self._file_path)
        if not isinstance(document, dict):
            raise TypeError("Booking data must be a JSON object")
        validate_schema_version(document)
        bookings = document.get("bookings")
        booking_seats = document.get("booking_seats")
        last_booking_id = document.get("last_booking_id")
        if (
            not isinstance(bookings, list)
            or not isinstance(booking_seats, list)
            or not isinstance(last_booking_id, int)
        ):
            raise TypeError("Booking data has an invalid document structure")
        return last_booking_id, bookings, booking_seats

    def _read_document_for_write(
        self,
    ) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
        if not self._file_path.exists() and self._file_path != DEFAULT_BOOKINGS_FILE:
            return 0, [], []
        return self._read_document()

    @staticmethod
    def _validate(
        bookings: list[Booking],
        booking_seats: list[BookingSeat],
        last_booking_id: int,
        valid_show_ids: set[int],
        valid_user_ids: set[int],
        valid_seat_ids: set[int],
    ) -> None:
        if any(booking.booking_id is None for booking in bookings):
            raise StorageError("Persisted booking is missing its ID")
        booking_ids = [booking.booking_id for booking in bookings if booking.booking_id is not None]
        if len(booking_ids) != len(set(booking_ids)):
            raise StorageError("Booking data contains duplicate booking IDs")
        if last_booking_id < max(booking_ids, default=0):
            raise StorageError("Booking data last_booking_id is lower than an existing booking ID")

        valid_booking_ids = set(booking_ids)
        seen_pairs: set[tuple[int, int]] = set()
        occupied_by_show: set[tuple[int, int]] = set()
        for booking in bookings:
            if booking.show_id not in valid_show_ids:
                raise StorageError(
                    f"Booking {booking.booking_id} references unknown show {booking.show_id}"
                )
            if booking.user_id not in valid_user_ids:
                raise StorageError(
                    f"Booking {booking.booking_id} references unknown user {booking.user_id}"
                )

        for row in booking_seats:
            if row.booking_id not in valid_booking_ids:
                raise StorageError(f"Booking-seat references unknown booking {row.booking_id}")
            if row.seat_id not in valid_seat_ids:
                raise StorageError(f"Booking-seat references unknown seat {row.seat_id}")
            pair = (row.booking_id, row.seat_id)
            if pair in seen_pairs:
                raise StorageError("Booking data contains duplicate booking-seat rows")
            seen_pairs.add(pair)

            booking_show_id = next(
                booking.show_id for booking in bookings if booking.booking_id == row.booking_id
            )
            if row.show_id != booking_show_id:
                raise StorageError(f"Booking-seat show {row.show_id} does not match its booking")

            occupied = (row.show_id, row.seat_id)
            if occupied in occupied_by_show:
                raise StorageError(
                    f"Booking data double-books seat {row.seat_id} for show {occupied[0]}"
                )
            occupied_by_show.add(occupied)

    @staticmethod
    def _serialize_booking(booking: Booking) -> dict[str, int]:
        if booking.booking_id is None:
            raise StorageError("Cannot serialize a booking without an ID")
        return {
            "booking_id": booking.booking_id,
            "user_id": booking.user_id,
            "show_id": booking.show_id,
        }

    @staticmethod
    def _serialize_booking_seat(row: BookingSeat) -> dict[str, int]:
        return {
            "booking_id": row.booking_id,
            "show_id": row.show_id,
            "seat_id": row.seat_id,
        }

    @staticmethod
    def _deserialize_booking(item: dict[str, Any]) -> Booking:
        return Booking(
            booking_id=int(item["booking_id"]),
            user_id=int(item["user_id"]),
            show_id=int(item["show_id"]),
        )

    @staticmethod
    def _deserialize_booking_seat(item: dict[str, Any]) -> BookingSeat:
        return BookingSeat(
            booking_id=int(item["booking_id"]),
            show_id=int(item["show_id"]),
            seat_id=int(item["seat_id"]),
        )
