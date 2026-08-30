"""Persistence abstractions and JSON implementation composition."""

from cinema.storage.interfaces import (
    BookingRepository,
    CinemaConfigRepository,
    MovieRepository,
    ShowRepository,
    UserRepository,
)
from cinema.storage.json_booking_repository import JsonBookingRepository
from cinema.storage.json_cinema_config_repository import JsonCinemaConfigRepository
from cinema.storage.json_factory import create_json_storage_service
from cinema.storage.json_movie_repository import JsonMovieRepository
from cinema.storage.json_show_repository import JsonShowRepository
from cinema.storage.json_user_repository import JsonUserRepository
from cinema.storage.storage_service import StorageService

__all__ = [
    "BookingRepository",
    "CinemaConfigRepository",
    "JsonBookingRepository",
    "JsonCinemaConfigRepository",
    "JsonMovieRepository",
    "JsonShowRepository",
    "JsonUserRepository",
    "MovieRepository",
    "ShowRepository",
    "StorageService",
    "UserRepository",
    "create_json_storage_service",
]
