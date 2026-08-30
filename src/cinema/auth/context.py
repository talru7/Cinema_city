"""Internal authentication context passed to application services."""

from dataclasses import dataclass
from enum import StrEnum

from cinema.exceptions import AuthorizationError


class Role(StrEnum):
    CUSTOMER = "customer"
    MANAGER = "manager"


class Permission(StrEnum):
    VIEW_CATALOG = "catalog:view"
    CREATE_BOOKING = "booking:create"
    VIEW_OWN_BOOKINGS = "booking:view-own"
    CANCEL_OWN_BOOKING = "booking:cancel-own"
    MANAGE_MOVIES = "movie:manage"
    MANAGE_SCHEDULE = "schedule:manage"
    VIEW_ALL_BOOKINGS = "booking:view-all"
    VIEW_REPORTS = "report:view"


CUSTOMER_PERMISSIONS = frozenset(
    {
        Permission.VIEW_CATALOG,
        Permission.CREATE_BOOKING,
        Permission.VIEW_OWN_BOOKINGS,
        Permission.CANCEL_OWN_BOOKING,
    }
)
MANAGER_PERMISSIONS = frozenset(Permission)


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Provider-free identity and permissions used inside the application."""

    user_id: int
    role: Role
    permissions: frozenset[Permission]
    email: str = ""

    def require(self, permission: Permission) -> None:
        if permission not in self.permissions:
            raise AuthorizationError(f"Permission {permission.value} is required")


def context_for_role(user_id: int, role: Role, email: str = "") -> AuthContext:
    permissions = MANAGER_PERMISSIONS if role is Role.MANAGER else CUSTOMER_PERMISSIONS
    return AuthContext(user_id=user_id, role=role, permissions=permissions, email=email)
