"""JSON persistence for movie catalog data."""

import json
from pathlib import Path
from typing import Any

from cinema.exceptions import BusinessError, StorageError
from cinema.models import Genre, Movie
from cinema.storage.app_paths import MOVIES_FILE, STATE_LOCK_FILE
from cinema.storage.interfaces import MovieRepository
from cinema.storage.json_file import (
    atomic_write_json,
    exclusive_file_lock,
    exclusive_lock,
    read_json,
)
from cinema.storage.schema import SCHEMA_VERSION, validate_schema_version

DEFAULT_MOVIES_FILE = MOVIES_FILE


class JsonMovieRepository(MovieRepository):
    """Persist movies in JSON while allocating movie IDs."""

    def __init__(
        self,
        file_path: Path = DEFAULT_MOVIES_FILE,
        state_lock_path: Path | None = None,
    ) -> None:
        self._file_path = file_path
        self._state_lock_path = state_lock_path or (
            STATE_LOCK_FILE
            if file_path == DEFAULT_MOVIES_FILE
            else file_path.parent / ".cinema_state.lock"
        )

    def load(self) -> list[Movie]:
        try:
            with exclusive_file_lock(self._file_path):
                last_movie_id, data = self._read_document()
            movies = [self._deserialize(item) for item in data]
            self._validate_unique_movies(movies, last_movie_id)
            return movies
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
            raise StorageError(f"Could not load movie data from {self._file_path}") from error

    def find_by_id(self, movie_id: int) -> Movie | None:
        """Return one movie by its internal ID."""
        return next((movie for movie in self.load() if movie.movie_id == movie_id), None)

    def create(self, movie: Movie) -> int:
        """Persist a non-persisted movie and return its allocated ID."""
        if movie.movie_id is not None:
            raise StorageError("A new movie must not already have an ID")
        try:
            with exclusive_lock(self._state_lock_path):
                with exclusive_file_lock(self._file_path):
                    last_movie_id, data = self._read_document_for_write()
                    movies = [self._deserialize(item) for item in data]
                    self._validate_unique_movies(movies, last_movie_id)

                    normalized_title = movie.title.strip().casefold()
                    if any(movie.title.strip().casefold() == normalized_title for movie in movies):
                        raise StorageError(f'Movie title "{movie.title.strip()}" already exists')

                    persisted = Movie(
                        movie_id=last_movie_id + 1,
                        title=movie.title,
                        duration_minutes=movie.duration_minutes,
                        description=movie.description,
                        genre=movie.genre,
                        ticket_price=movie.ticket_price,
                    )
                    data.append(self._serialize(persisted))
                    atomic_write_json(
                        self._file_path,
                        {
                            "schema_version": SCHEMA_VERSION,
                            "last_movie_id": persisted.movie_id,
                            "movies": data,
                        },
                    )
                    assert persisted.movie_id is not None
                    return persisted.movie_id
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
            raise StorageError(f"Could not create movie in {self._file_path}") from error

    def _read_document(self) -> tuple[int, list[dict[str, Any]]]:
        document = read_json(self._file_path)
        if not isinstance(document, dict):
            raise TypeError("Movie data must be a JSON object")
        validate_schema_version(document)
        movies = document.get("movies")
        last_movie_id = document.get("last_movie_id")
        if not isinstance(movies, list) or not isinstance(last_movie_id, int):
            raise TypeError("Movie data has an invalid document structure")
        return last_movie_id, movies

    def _read_document_for_write(self) -> tuple[int, list[dict[str, Any]]]:
        if not self._file_path.exists() and self._file_path != DEFAULT_MOVIES_FILE:
            return 0, []
        return self._read_document()

    @staticmethod
    def _validate_unique_movies(movies: list[Movie], last_movie_id: int) -> None:
        if any(movie.movie_id is None for movie in movies):
            raise StorageError("Persisted movie is missing its ID")
        movie_ids = [movie.movie_id for movie in movies if movie.movie_id is not None]
        if len(movie_ids) != len(set(movie_ids)):
            raise StorageError("Movie data contains duplicate movie IDs")
        if last_movie_id < max(movie_ids, default=0):
            raise StorageError("Movie last_movie_id is lower than an existing movie ID")

        normalized_titles = [movie.title.strip().casefold() for movie in movies]
        if len(normalized_titles) != len(set(normalized_titles)):
            raise StorageError("Movie data contains duplicate movie titles")

    @staticmethod
    def _serialize(movie: Movie) -> dict[str, Any]:
        if movie.movie_id is None:
            raise StorageError("Cannot serialize a movie without an ID")
        return {
            "movie_id": movie.movie_id,
            "title": movie.title,
            "duration_minutes": movie.duration_minutes,
            "description": movie.description,
            "genre": movie.genre.value,
            "ticket_price": movie.ticket_price,
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> Movie:
        return Movie(
            movie_id=int(item["movie_id"]),
            title=str(item["title"]),
            duration_minutes=int(item["duration_minutes"]),
            description=str(item["description"]),
            genre=Genre(str(item["genre"])),
            ticket_price=int(item["ticket_price"]),
        )
