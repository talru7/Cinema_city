"""Interactive command-line interface for the cinema manager."""

from datetime import timedelta

from cinema.cli.error_handling import run_cli_safely
from cinema.cli.input_helpers import read_genre
from cinema.composition import create_container
from cinema.config import load_settings
from cinema.exceptions import BusinessError
from cinema.models import Booking, BookingSeat, Hall, Movie, MovieShow, Seat
from cinema.services import CinemaManager, SchedulingService
from cinema.services.cinema_manager import DEFAULT_TICKET_PRICE
from cinema.storage import StorageService
from cinema.time_utils import local_now

MAX_TICKET_PRICE = 99


def read_positive_int(prompt: str) -> int:
    while True:
        raw_value = input(prompt).strip()
        try:
            value = int(raw_value)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if value <= 0:
            print("Please enter a positive number.")
            continue
        return value


def read_ticket_price(prompt: str = "Ticket price [40 NIS]: ") -> int:
    while True:
        raw_value = input(prompt).strip()
        if not raw_value:
            return DEFAULT_TICKET_PRICE
        try:
            value = int(raw_value)
        except ValueError:
            print("Please enter a whole number between 1 and 99, or press Enter for 40.")
            continue
        if 1 <= value <= MAX_TICKET_PRICE:
            return value
        print("Ticket price must be between 1 and 99 NIS.")


def read_non_empty_text(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Value cannot be empty.")


def find_movie_by_id_or_title(
    movies: list[Movie],
    movie_reference: str,
) -> Movie | None:
    normalized_reference = movie_reference.strip()
    if normalized_reference.isdigit():
        movie_id = int(normalized_reference)
        return next(
            (movie for movie in movies if movie.movie_id == movie_id),
            None,
        )

    normalized_title = normalized_reference.casefold()
    return next(
        (movie for movie in movies if movie.title.casefold() == normalized_title),
        None,
    )


def add_movie_interactively(manager: CinemaManager) -> Movie:
    print("\nAdd a new movie")
    movie = manager.add_movie(
        title=read_non_empty_text("Movie title: "),
        duration_minutes=read_positive_int("Duration in minutes: "),
        description=read_non_empty_text("Short description: "),
        genre=read_genre(),
        ticket_price=read_ticket_price(),
    )
    print(f'Added movie #{movie.movie_id}: "{movie.title}"')
    return movie


def schedule_movie_interactively(
    movies: list[Movie],
    manager: CinemaManager,
) -> tuple[MovieShow, ...]:
    if not movies:
        print("No movies in catalog.")
        return ()

    movie = find_movie_by_id_or_title(
        movies,
        read_non_empty_text("Enter movie ID or exact title: "),
    )
    if movie is None:
        print("Movie not found.")
        return ()

    try:
        shows = manager.schedule_movie(
            movie=movie,
            screening_date=local_now().date(),
        )
    except BusinessError as error:
        print(f"Cannot schedule movie: {error}")
        return ()

    print(f'Scheduled {len(shows)} shows for "{movie.title}".')
    return shows


def list_movies(movies: list[Movie]) -> None:
    if not movies:
        print("No movies in catalog.")
        return
    for movie in movies:
        print(
            f"{movie.movie_id}. {movie.title} "
            f"({movie.duration_minutes} minutes, {movie.genre.value}, "
            f"{movie.ticket_price} NIS)"
        )


def list_shows_by_hall(
    halls: list[Hall],
    movies: list[Movie],
    shows: list[MovieShow],
) -> None:
    hall_id = read_positive_int("Hall ID: ")
    hall = next((item for item in halls if item.hall_id == hall_id), None)
    if hall is None:
        print(f"Hall ID {hall_id} does not exist.")
        return

    movies_by_id = {movie.movie_id: movie for movie in movies}
    hall_shows = sorted(
        (show for show in shows if show.hall_id == hall_id),
        key=lambda show: show.start_time,
    )
    if not hall_shows:
        print(f"No shows scheduled in {hall.hall_name}.")
        return

    print(f"\n{hall.hall_name} Shows")
    for show in hall_shows:
        movie = movies_by_id[show.movie_id]
        end_time = show.start_time + timedelta(minutes=movie.duration_minutes)
        print(
            f"#{show.show_id} | {movie.title} | {movie.genre.value} | "
            f"{show.start_time:%Y-%m-%d %H:%M} - {end_time:%H:%M} | "
            f"{show.ticket_price} NIS"
        )


def list_bookings(
    bookings: list[Booking],
    booking_seats: list[BookingSeat],
    seats: list[Seat],
    shows: list[MovieShow],
    movies: list[Movie],
    halls: list[Hall],
) -> None:
    if not bookings:
        print("No bookings.")
        return

    seats_by_id = {seat.seat_id: seat for seat in seats}
    shows_by_id = {show.show_id: show for show in shows if show.show_id is not None}
    movies_by_id = {movie.movie_id: movie for movie in movies if movie.movie_id is not None}
    halls_by_id = {hall.hall_id: hall for hall in halls}
    rows_by_booking: dict[int, list[BookingSeat]] = {}
    for row in booking_seats:
        rows_by_booking.setdefault(row.booking_id, []).append(row)

    print("\nBookings")
    for booking in sorted(bookings, key=lambda item: item.booking_id or 0):
        show = shows_by_id[booking.show_id]
        movie = movies_by_id[show.movie_id]
        hall = halls_by_id[show.hall_id]
        booking_rows = rows_by_booking.get(booking.booking_id or 0, [])
        selected = [seats_by_id[row.seat_id] for row in booking_rows]
        seat_text = ", ".join(f"R{seat.row_number}-S{seat.seat_number}" for seat in selected)
        total = show.ticket_price * len(selected)
        print(
            f"#{booking.booking_id} | {movie.title} | Show #{show.show_id} | "
            f"{hall.hall_name} | {show.start_time:%Y-%m-%d %H:%M} | "
            f"Seats: {seat_text} | Total: {total} NIS"
        )


def print_report(storage: StorageService) -> None:
    (
        _,
        _,
        _,
        movies,
        shows,
        _,
        bookings,
        booking_seats,
    ) = storage.load()

    print("\nCinema Report")
    print(f"Movies: {len(movies)}")
    print(f"Shows: {len(shows)}")
    print(f"Bookings: {len(bookings)}")
    print(f"Total booked seats: {len(booking_seats)}")


def run_manager_cli() -> None:
    storage = create_container(load_settings()).storage
    scheduler = SchedulingService(
        config_repository=storage.config_repository,
        movie_repository=storage.movie_repository,
        show_repository=storage.show_repository,
    )
    manager = CinemaManager(
        movie_repository=storage.movie_repository,
        scheduling_service=scheduler,
    )

    while True:
        print(
            "\nCinema Manager\n"
            "1. Add movie\n"
            "2. Schedule movie\n"
            "3. List movies\n"
            "4. List shows by hall\n"
            "5. List bookings\n"
            "6. Cinema report\n"
            "7. Exit"
        )
        choice = input("Choose an option: ").strip()

        if choice == "1":
            try:
                add_movie_interactively(manager)
            except BusinessError as error:
                print(f"Cannot add movie: {error}")
        elif choice == "2":
            movies = storage.movie_repository.load()
            schedule_movie_interactively(movies, manager)
        elif choice == "3":
            list_movies(storage.movie_repository.load())
        elif choice == "4":
            _, halls, _, movies, shows = storage.load_catalog()
            list_shows_by_hall(halls, movies, shows)
        elif choice == "5":
            _, halls, seats, movies, shows = storage.load_catalog()
            users = storage.user_repository.load()
            bookings, booking_seats = storage.load_bookings(
                shows,
                seats,
                users,
            )
            list_bookings(
                bookings,
                booking_seats,
                seats,
                shows,
                movies,
                halls,
            )
        elif choice == "6":
            print_report(storage)
        elif choice == "7":
            print("Goodbye.")
            return
        else:
            print("Unknown option.")


def main() -> None:
    run_cli_safely(run_manager_cli)


if __name__ == "__main__":
    main()
