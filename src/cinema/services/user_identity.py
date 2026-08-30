"""Normalization and validation helpers for customer identity."""

import re

from cinema.exceptions import UserValidationError

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_NON_DIGIT_PATTERN = re.compile(r"\D+")


def normalize_full_name(full_name: str) -> str:
    """Normalize whitespace while preserving the customer's written name."""
    normalized = " ".join(full_name.strip().split())
    if len(normalized) < 2:
        raise UserValidationError("Full name must contain at least two characters")
    return normalized


def normalize_email(email: str) -> str:
    """Normalize an email address for case-insensitive identity matching."""
    normalized = email.strip().casefold()
    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise UserValidationError("Invalid email address")
    return normalized


def normalize_phone_number(phone_number: str) -> str:
    """Normalize an Israeli mobile number to canonical +9725XXXXXXXX form."""
    value = phone_number.strip()
    if value.startswith("+"):
        digits = "+" + _NON_DIGIT_PATTERN.sub("", value[1:])
    else:
        digits = _NON_DIGIT_PATTERN.sub("", value)

    if digits.startswith("+972"):
        local_digits = "0" + digits[4:]
    elif digits.startswith("972"):
        local_digits = "0" + digits[3:]
    else:
        local_digits = digits

    if len(local_digits) != 10 or not local_digits.startswith("05"):
        raise UserValidationError("Phone number must be a valid Israeli mobile number")

    return "+972" + local_digits[1:]
