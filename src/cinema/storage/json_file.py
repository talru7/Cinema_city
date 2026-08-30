"""Low-level helpers for safe JSON file access."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from cinema.exceptions import StorageError

LOCK_TIMEOUT_SECONDS = 10


@contextmanager
def exclusive_lock(lock_path: Path) -> Iterator[None]:
    """Acquire one explicit cross-platform lock path."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(lock_path, timeout=LOCK_TIMEOUT_SECONDS)

    try:
        with lock:
            yield
    except Timeout as error:
        raise StorageError(
            f"Could not acquire lock {lock_path} within {LOCK_TIMEOUT_SECONDS} seconds"
        ) from error


@contextmanager
def exclusive_file_lock(file_path: Path) -> Iterator[None]:
    """Lock a JSON sidecar file so read-modify-write operations stay serialized."""
    lock_path = file_path.with_suffix(file_path.suffix + ".lock")
    with exclusive_lock(lock_path):
        yield


def read_json(file_path: Path) -> Any:
    """Read JSON from disk and fail when an expected file is missing."""
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def atomic_write_json(file_path: Path, data: Any) -> None:
    """Write JSON through a temporary file and atomically replace the target."""
    file_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=file_path.parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(data, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, file_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
