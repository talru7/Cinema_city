"""Explicit database initialization command for deployment workflows."""

from cinema.config import StorageBackend, load_settings
from cinema.exceptions import ConfigurationError
from cinema.storage.sqlalchemy_backend import create_neon_storage_service


def main() -> None:
    """Create and seed the selected relational schema, then exit."""
    settings = load_settings()
    if settings.storage_backend is not StorageBackend.NEON:
        raise ConfigurationError("cinema-db-init currently supports STORAGE_BACKEND=neon")
    create_neon_storage_service(settings.neon_database_url, initialize_schema=True)
    print("Cinema database schema is ready.")
