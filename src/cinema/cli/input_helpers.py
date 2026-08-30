"""Shared CLI input helper functions."""

from cinema.models import Genre


def read_genre() -> Genre:
    """Read one supported movie genre from standard input."""
    genres = list(Genre)

    for index, genre in enumerate(genres, start=1):
        print(f"{index}. {genre.value}")

    while True:
        choice = input("Choose genre: ").strip()

        if choice.isdigit():
            index = int(choice) - 1

            if 0 <= index < len(genres):
                return genres[index]

        print("Invalid genre.")
