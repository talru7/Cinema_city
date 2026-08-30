"""Explicit local authentication adapter for offline development."""

from cinema.auth.context import AuthContext, Role, context_for_role
from cinema.auth.interfaces import AuthenticationService, RequestCredentials
from cinema.models import User
from cinema.storage.interfaces import UserRepository


class NoAuthAuthenticationService(AuthenticationService):
    """Resolve one server-configured local identity without browser authority."""

    def __init__(
        self,
        user_repository: UserRepository,
        role: Role,
        email: str,
    ) -> None:
        self._users = user_repository
        self._role = role
        self._email = email.strip().casefold()

    def authenticate(self, credentials: RequestCredentials) -> AuthContext:
        del credentials
        subject = f"local-{self._role.value}"
        user = self._users.find_by_auth_identity("none", subject)
        if user is None:
            user_id = self._users.create(
                User(
                    user_id=None,
                    auth_provider="none",
                    auth_subject=subject,
                    full_name=f"Local {self._role.value.title()}",
                    phone_number="",
                    email=self._email,
                )
            )
        else:
            if user.user_id is None:
                raise RuntimeError("Persisted local user has no ID")
            user_id = user.user_id
        return context_for_role(user_id, self._role, self._email)
