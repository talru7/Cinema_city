"""HTTP request schemas. Responses are derived from application results."""

from datetime import date

from pydantic import BaseModel, Field

from cinema.models import Genre


class SeatRequest(BaseModel):
    row_number: int = Field(ge=1)
    seat_number: int = Field(ge=1)


class CreateBookingRequest(BaseModel):
    show_id: int = Field(ge=1)
    seats: list[SeatRequest] = Field(min_length=1, max_length=5)


class CreateMovieRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    duration_minutes: int = Field(ge=1, le=240)
    description: str = Field(min_length=1, max_length=300)
    genre: Genre
    ticket_price: int = Field(default=40, ge=1, le=99)


class ScheduleMovieRequest(BaseModel):
    movie_id: int = Field(ge=1)
    screening_date: date
    hall_id: int | None = Field(default=None, ge=1)
    shows_count: int = Field(default=3, ge=1, le=10)
