"""Cinema customer identity model."""

from dataclasses import dataclass

from cinema.exceptions import UserValidationError


@dataclass(frozen=True, slots=True)
class User:
    """Represent one customer known to the cinema system."""

    user_id: int | None
    auth_provider: str
    auth_subject: str
    full_name: str
    phone_number: str
    email: str

    def __post_init__(self) -> None:
        """Validate persisted user identity."""
        if self.user_id is not None and self.user_id <= 0:
            raise UserValidationError("User ID must be positive")
        if not self.auth_provider.strip():
            raise UserValidationError("Authentication provider cannot be empty")
        if not self.auth_subject.strip():
            raise UserValidationError("Authentication subject cannot be empty")
        if not self.full_name.strip():
            raise UserValidationError("Full name cannot be empty")
