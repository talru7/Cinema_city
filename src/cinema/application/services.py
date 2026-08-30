"""Application use cases composed only from business services and contracts."""

from datetime import date, datetime, timedelta

from cinema.application.dto import BookingView, CinemaReport, SeatView, ShowView
from cinema.auth import AuthContext, Permission
from cinema.exceptions import BookingNotFoundError, BookingValidationError, ScheduleValidationError
from cinema.models import Booking, BookingSeat, Genre, Hall, Movie, MovieShow, Seat
from cinema.services import BookingService, CinemaManager, SchedulingService
from cinema.storage import StorageService
from cinema.time_utils import local_now

UPCOMING_WINDOW = timedelta(days=7)


class CatalogApplicationService:
    """Expose public catalog queries without persistence knowledge."""

    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    def list_movies(self) -> list[Movie]:
        return self._storage.movie_repository.load()

    def list_upcoming_shows(
        self,
        *,
        genre: Genre | None = None,
        now: datetime | None = None,
    ) -> list[ShowView]:
        current = now or local_now()
        _, halls, _, movies, shows = self._storage.load_catalog()
        movies_by_id = {movie.movie_id: movie for movie in movies}
        halls_by_id = {hall.hall_id: hall for hall in halls}
        visible = [
            show
            for show in shows
            if current <= show.start_time < current + UPCOMING_WINDOW
            and (genre is None or movies_by_id[show.movie_id].genre is genre)
        ]
        return [
            self._show_view(show, movies_by_id, halls_by_id)
            for show in sorted(visible, key=lambda item: item.start_time)
        ]

    def list_seats(self, show_id: int) -> list[SeatView]:
        _, _, seats, movies, shows = self._storage.load_catalog()
        show = next((item for item in shows if item.show_id == show_id), None)
        if show is None:
            raise ScheduleValidationError(f"Show {show_id} does not exist")
        users = self._storage.user_repository.load()
        bookings, booking_seats = self._storage.load_bookings(shows, seats, users)
        booking_ids = {booking.booking_id for booking in bookings if booking.show_id == show_id}
        occupied = {row.seat_id for row in booking_seats if row.booking_id in booking_ids}
        del movies
        return [
            SeatView(
                seat_id=seat.seat_id,
                row_number=seat.row_number,
                seat_number=seat.seat_number,
                available=seat.seat_id not in occupied,
            )
            for seat in seats
            if seat.hall_id == show.hall_id
        ]

    @staticmethod
    def _show_view(
        show: MovieShow,
        movies: dict[int | None, Movie],
        halls: dict[int, Hall],
    ) -> ShowView:
        movie = movies[show.movie_id]
        hall = halls[show.hall_id]
        if show.show_id is None or movie.movie_id is None:
            raise RuntimeError("Catalog contains a non-persisted entity")
        return ShowView(
            show_id=show.show_id,
            movie_id=movie.movie_id,
            movie_title=movie.title,
            genre=movie.genre.value,
            hall_id=show.hall_id,
            hall_name=hall.hall_name,
            start_time=show.start_time,
            ticket_price=show.ticket_price,
        )


class BookingApplicationService:
    """Execute authenticated customer booking use cases."""

    def __init__(self, storage: StorageService, catalog: CatalogApplicationService) -> None:
        self._storage = storage
        self._catalog = catalog

    def create_booking(
        self,
        auth: AuthContext,
        show_id: int,
        requested_seats: tuple[tuple[int, int], ...],
        now: datetime | None = None,
    ) -> BookingView:
        auth.require(Permission.CREATE_BOOKING)
        _, _, seats, movies, shows = self._storage.load_catalog()
        show = next((item for item in shows if item.show_id == show_id), None)
        if show is None:
            raise BookingValidationError(f"Show {show_id} does not exist")
        if show.start_time <= (now or local_now()):
            raise BookingValidationError("Cannot book a show that has already started")
        users = self._storage.user_repository.load()
        bookings, booking_seats = self._storage.load_bookings(shows, seats, users)
        request = BookingService.prepare_booking(
            show=show,
            requested_seats=requested_seats,
            user_id=auth.user_id,
            seats=seats,
            bookings=bookings,
            booking_seats=booking_seats,
        )
        booking_id = self._storage.booking_repository.add(request)
        return self._booking_view(booking_id, movies, shows, seats)

    def list_my_bookings(self, auth: AuthContext) -> list[BookingView]:
        auth.require(Permission.VIEW_OWN_BOOKINGS)
        _, _, seats, movies, shows = self._storage.load_catalog()
        return [
            self._booking_view(booking_id, movies, shows, seats)
            for booking_id in (
                booking.booking_id
                for booking in self._storage.booking_repository.find_by_user_id(auth.user_id)
                if booking.booking_id is not None
            )
        ]

    def cancel_booking(
        self,
        auth: AuthContext,
        booking_id: int,
        now: datetime | None = None,
    ) -> int:
        auth.require(Permission.CANCEL_OWN_BOOKING)
        booking = self._storage.booking_repository.find_by_id(booking_id)
        if booking is None or booking.user_id != auth.user_id:
            raise BookingNotFoundError(f"Booking {booking_id} does not exist")
        show = self._storage.show_repository.find_by_id(booking.show_id)
        if show is None:
            raise BookingValidationError("Booking references a missing show")
        BookingService.validate_cancellation(booking, show, now or local_now())
        return self._storage.booking_repository.delete(booking_id, auth.user_id)

    def _booking_view(
        self,
        booking_id: int,
        movies: list[Movie],
        shows: list[MovieShow],
        seats: list[Seat],
    ) -> BookingView:
        booking = self._storage.booking_repository.find_by_id(booking_id)
        if booking is None:
            raise BookingNotFoundError(f"Booking {booking_id} does not exist")
        users = self._storage.user_repository.load()
        all_bookings, rows = self._storage.booking_repository.load(
            valid_show_ids={show.show_id for show in shows if show.show_id is not None},
            valid_user_ids={user.user_id for user in users if user.user_id is not None},
            valid_seat_ids={seat.seat_id for seat in seats},
        )
        del all_bookings
        selected_ids = {row.seat_id for row in rows if row.booking_id == booking_id}
        selected = tuple(
            SeatView(
                seat_id=seat.seat_id,
                row_number=seat.row_number,
                seat_number=seat.seat_number,
                available=False,
            )
            for seat in seats
            if seat.seat_id in selected_ids
        )
        show = next(item for item in shows if item.show_id == booking.show_id)
        _, halls, _ = self._storage.config_repository.load()
        show_view = CatalogApplicationService._show_view(
            show,
            {movie.movie_id: movie for movie in movies},
            {hall.hall_id: hall for hall in halls},
        )
        return BookingView(
            booking_id=booking_id,
            show=show_view,
            seats=selected,
            total_price=show.ticket_price * len(selected),
        )


class ManagerApplicationService:
    """Execute manager-only catalog, scheduling, and reporting use cases."""

    def __init__(
        self,
        storage: StorageService,
        manager: CinemaManager,
        scheduler: SchedulingService,
    ) -> None:
        self._storage = storage
        self._manager = manager
        self._scheduler = scheduler

    def add_movie(
        self,
        auth: AuthContext,
        *,
        title: str,
        duration_minutes: int,
        description: str,
        genre: Genre,
        ticket_price: int,
    ) -> Movie:
        auth.require(Permission.MANAGE_MOVIES)
        return self._manager.add_movie(
            title=title,
            duration_minutes=duration_minutes,
            description=description,
            genre=genre,
            ticket_price=ticket_price,
        )

    def schedule_movie(
        self,
        auth: AuthContext,
        *,
        movie_id: int,
        screening_date: date,
        hall_id: int | None,
        shows_count: int,
    ) -> tuple[MovieShow, ...]:
        auth.require(Permission.MANAGE_SCHEDULE)
        movie = self._storage.movie_repository.find_by_id(movie_id)
        if movie is None:
            raise ScheduleValidationError(f"Movie {movie_id} does not exist")
        if hall_id is None:
            return self._scheduler.schedule_movie_for_all_halls(movie, screening_date, shows_count)
        return tuple(self._scheduler.schedule_movie(hall_id, movie, screening_date, shows_count))

    def report(self, auth: AuthContext) -> CinemaReport:
        auth.require(Permission.VIEW_REPORTS)
        _, _, seats, movies, shows, users, bookings, rows = self._storage.load()
        del seats, users
        shows_by_id = {show.show_id: show for show in shows}
        revenue = sum(shows_by_id[row.show_id].ticket_price for row in rows)
        return CinemaReport(
            movies=len(movies),
            shows=len(shows),
            bookings=len(bookings),
            booked_seats=len(rows),
            revenue_nis=revenue,
        )

    def list_all_bookings(
        self,
        auth: AuthContext,
    ) -> tuple[list[Booking], list[BookingSeat]]:
        auth.require(Permission.VIEW_ALL_BOOKINGS)
        _, _, seats, _, shows, users, bookings, rows = self._storage.load()
        del seats, shows, users
        return list(bookings), list(rows)
