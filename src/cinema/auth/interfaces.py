"""Authentication service contract used by external adapters."""

from dataclasses import dataclass
from typing import Protocol

from cinema.auth.context import AuthContext


@dataclass(frozen=True, slots=True)
class RequestCredentials:
    """Credentials extracted at an external application boundary."""

    bearer_token: str | None = None


class AuthenticationService(Protocol):
    """Map external credentials to an internal authentication context."""

    def authenticate(self, credentials: RequestCredentials) -> AuthContext:
        """Authenticate external credentials or raise an authentication error."""
        raise NotImplementedError
