"""Read-only application results for external interface adapters."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ShowView:
    show_id: int
    movie_id: int
    movie_title: str
    genre: str
    hall_id: int
    hall_name: str
    start_time: datetime
    ticket_price: int


@dataclass(frozen=True, slots=True)
class SeatView:
    seat_id: int
    row_number: int
    seat_number: int
    available: bool


@dataclass(frozen=True, slots=True)
class BookingView:
    booking_id: int
    show: ShowView
    seats: tuple[SeatView, ...]
    total_price: int


@dataclass(frozen=True, slots=True)
class CinemaReport:
    movies: int
    shows: int
    bookings: int
    booked_seats: int
    revenue_nis: int
