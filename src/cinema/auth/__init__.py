"""Provider-independent authentication and authorization adapters."""

from cinema.auth.context import AuthContext, Permission, Role
from cinema.auth.interfaces import AuthenticationService, RequestCredentials

__all__ = [
    "AuthContext",
    "AuthenticationService",
    "Permission",
    "RequestCredentials",
    "Role",
]
