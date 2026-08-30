"""Persistence schema version helpers."""

from typing import Any

from cinema.exceptions import StorageError

SCHEMA_VERSION = 3


def validate_schema_version(document: dict[str, Any]) -> None:
    """Validate a versioned document while allowing legacy unversioned data."""
    if "schema_version" not in document:
        return

    version = document["schema_version"]
    if version != SCHEMA_VERSION:
        raise StorageError(f"Unsupported data schema version {version}; expected {SCHEMA_VERSION}")
