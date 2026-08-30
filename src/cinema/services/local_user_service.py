"""Local CLI profile resolution without an external authentication provider."""

from cinema.exceptions import UserIdentityConflictError
from cinema.models import User
from cinema.services.user_identity import (
    normalize_email,
    normalize_full_name,
    normalize_phone_number,
)
from cinema.storage.interfaces import UserRepository


class LocalUserService:
    """Create or update a CLI user while preserving the internal user ID."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    def get_or_update(self, full_name: str, phone_number: str, email: str) -> User:
        name = normalize_full_name(full_name)
        phone = normalize_phone_number(phone_number)
        normalized_email = normalize_email(email)
        by_email = self._repository.find_by_email(normalized_email)
        by_phone = self._repository.find_by_phone(phone)
        if by_email is not None and by_phone is not None and by_email.user_id != by_phone.user_id:
            raise UserIdentityConflictError("Email and phone number belong to different users")
        existing = by_email or by_phone
        if existing is None:
            user_id = self._repository.create(
                User(
                    user_id=None,
                    auth_provider="local",
                    auth_subject=normalized_email,
                    full_name=name,
                    phone_number=phone,
                    email=normalized_email,
                )
            )
            created = self._repository.find_by_id(user_id)
            if created is None:
                raise RuntimeError("User repository did not return the created user")
            return created
        updated = User(
            user_id=existing.user_id,
            auth_provider=existing.auth_provider,
            auth_subject=existing.auth_subject,
            full_name=name,
            phone_number=phone,
            email=normalized_email,
        )
        self._repository.update(updated)
        return updated
