"""Timezone helpers for cinema-local time and UTC persistence."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

CINEMA_TIMEZONE = ZoneInfo("Asia/Jerusalem")


def local_now() -> datetime:
    """Return the current cinema-local timezone-aware datetime."""
    return datetime.now(CINEMA_TIMEZONE)


def local_datetime(day: date, clock_time: time) -> datetime:
    """Combine a local cinema date and time into an aware datetime."""
    return datetime.combine(day, clock_time, tzinfo=CINEMA_TIMEZONE)


def require_aware(value: datetime) -> None:
    """Reject naive datetimes at application boundaries."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must include timezone information")


def to_utc_iso(value: datetime) -> str:
    """Serialize an aware datetime as an ISO-8601 UTC timestamp."""
    require_aware(value)
    return value.astimezone(UTC).isoformat()


def from_storage_iso(value: str) -> datetime:
    """Load a persisted timestamp and return cinema-local aware time.

    Legacy naive values are interpreted as historical cinema-local timestamps.
    New schema-v1 files are persisted with an explicit UTC offset.
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=CINEMA_TIMEZONE)
    return parsed.astimezone(CINEMA_TIMEZONE)
