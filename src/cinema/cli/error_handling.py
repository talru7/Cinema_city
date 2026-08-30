"""Shared top-level error handling for command-line applications."""

import logging
from collections.abc import Callable

from cinema.exceptions import CinemaError
from cinema.storage.app_paths import LOG_FILE, ensure_log_directory

LOGGER = logging.getLogger("cinema")


def configure_logging() -> None:
    """Configure file logging for unexpected application errors."""
    ensure_log_directory()
    logging.basicConfig(
        filename=str(LOG_FILE),
        level=logging.ERROR,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def run_cli_safely(application: Callable[[], None]) -> None:
    """Run a CLI entry point with friendly handling at the application boundary."""
    configure_logging()

    try:
        application()
    except CinemaError as error:
        print(f"Application error: {error}")
        raise SystemExit(1) from None
    except Exception:
        LOGGER.exception("Unexpected application error")
        print(f"Unexpected application error. Technical details were written to {LOG_FILE}.")
        raise SystemExit(1) from None
