"""Stateless business logic for validating booking requests."""

from datetime import datetime, timedelta

from cinema.exceptions import (
    BookingValidationError,
    SeatAlreadyBookedError,
    SeatNotFoundError,
)
from cinema.models import Booking, BookingRequest, BookingSeat, MovieShow, Seat
from cinema.time_utils import require_aware

MAX_SEATS_PER_BOOKING = 5
CANCELLATION_NOTICE = timedelta(hours=1)


class BookingService:
    """Validate booking operations using explicit entity collections."""

    @staticmethod
    def find_seat(
        seats: list[Seat] | tuple[Seat, ...],
        hall_id: int,
        row_number: int,
        seat_number: int,
    ) -> Seat:
        """Return a physical seat by hall and coordinates."""
        seat = next(
            (
                item
                for item in seats
                if item.hall_id == hall_id
                and item.row_number == row_number
                and item.seat_number == seat_number
            ),
            None,
        )
        if seat is None:
            raise SeatNotFoundError(
                f"Seat {row_number}-{seat_number} does not exist in hall {hall_id}"
            )
        return seat

    @staticmethod
    def prepare_booking(
        *,
        show: MovieShow,
        requested_seats: tuple[tuple[int, int], ...],
        user_id: int,
        seats: list[Seat] | tuple[Seat, ...],
        bookings: list[Booking] | tuple[Booking, ...] = (),
        booking_seats: list[BookingSeat] | tuple[BookingSeat, ...] = (),
    ) -> BookingRequest:
        """Validate a booking and return only foreign-key IDs for persistence."""
        if user_id <= 0:
            raise BookingValidationError("Booking user ID must be positive")
        if show.show_id is None:
            raise BookingValidationError("Show must be persisted before booking")
        if not requested_seats:
            raise BookingValidationError("At least one seat must be requested")
        if len(requested_seats) > MAX_SEATS_PER_BOOKING:
            raise BookingValidationError(
                f"A booking can contain at most {MAX_SEATS_PER_BOOKING} seats"
            )

        selected = tuple(
            BookingService.find_seat(
                seats,
                show.hall_id,
                row_number,
                seat_number,
            )
            for row_number, seat_number in requested_seats
        )
        seat_ids = tuple(seat.seat_id for seat in selected)
        if len(seat_ids) != len(set(seat_ids)):
            raise BookingValidationError("A seat cannot be requested more than once")
        if not BookingService._are_seats_adjacent(selected):
            raise BookingValidationError("Requested seats must be adjacent in the same row")

        booking_by_id = {booking.booking_id: booking for booking in bookings}
        occupied_ids = {
            row.seat_id
            for row in booking_seats
            if (
                row.booking_id in booking_by_id
                and booking_by_id[row.booking_id].show_id == show.show_id
            )
        }
        overlap = occupied_ids.intersection(seat_ids)
        if overlap:
            raise SeatAlreadyBookedError(
                f"Seat ID {min(overlap)} is already booked for show {show.show_id}"
            )

        return BookingRequest(
            user_id=user_id,
            show_id=show.show_id,
            seat_ids=seat_ids,
        )

    @staticmethod
    def validate_cancellation(
        booking: Booking,
        show: MovieShow,
        current_time: datetime,
    ) -> None:
        """Allow cancellation only until one hour before the show starts."""
        del booking
        try:
            require_aware(current_time)
        except ValueError as error:
            raise BookingValidationError(str(error)) from error

        cancellation_deadline = show.start_time - CANCELLATION_NOTICE
        if current_time > cancellation_deadline:
            raise BookingValidationError(
                "Booking can only be cancelled up to one hour before the show starts"
            )

    @staticmethod
    def total_price(
        booking: Booking,
        show: MovieShow,
        booking_seats: list[BookingSeat] | tuple[BookingSeat, ...],
    ) -> int:
        """Calculate booking price from persisted show and junction rows."""
        seat_count = sum(1 for row in booking_seats if row.booking_id == booking.booking_id)
        return show.ticket_price * seat_count

    @staticmethod
    def _are_seats_adjacent(seats: tuple[Seat, ...]) -> bool:
        if not seats:
            return False
        row_number = seats[0].row_number
        if any(seat.row_number != row_number for seat in seats):
            return False

        seat_numbers = sorted(seat.seat_number for seat in seats)
        expected = list(range(seat_numbers[0], seat_numbers[0] + len(seat_numbers)))
        return seat_numbers == expected
