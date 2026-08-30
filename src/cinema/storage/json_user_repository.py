"""JSON persistence for provider-independent local users."""

import json
from pathlib import Path
from typing import Any

from cinema.exceptions import BusinessError, StorageError, UserIdentityConflictError
from cinema.models import User
from cinema.services.user_identity import (
    normalize_email,
    normalize_full_name,
    normalize_phone_number,
)
from cinema.storage.app_paths import USERS_FILE
from cinema.storage.interfaces import UserRepository
from cinema.storage.json_file import atomic_write_json, exclusive_file_lock, read_json
from cinema.storage.schema import SCHEMA_VERSION, validate_schema_version

DEFAULT_USERS_FILE = USERS_FILE


class JsonUserRepository(UserRepository):
    """Persist users and enforce unique external and profile identities."""

    def __init__(self, file_path: Path = DEFAULT_USERS_FILE) -> None:
        self._file_path = file_path

    def load(self) -> list[User]:
        try:
            with exclusive_file_lock(self._file_path):
                _, data = self._read_document()
            return self._deserialize_all(data)
        except StorageError:
            raise
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            BusinessError,
        ) as error:
            raise StorageError(f"Could not load user data from {self._file_path}") from error

    def find_by_id(self, user_id: int) -> User | None:
        return next((user for user in self.load() if user.user_id == user_id), None)

    def find_by_auth_identity(
        self,
        auth_provider: str,
        auth_subject: str,
    ) -> User | None:
        provider = auth_provider.strip().casefold()
        subject = auth_subject.strip()
        return next(
            (
                user
                for user in self.load()
                if user.auth_provider.casefold() == provider and user.auth_subject == subject
            ),
            None,
        )

    def find_by_email(self, email: str) -> User | None:
        if not email.strip():
            return None
        normalized = normalize_email(email)
        return next((user for user in self.load() if user.email == normalized), None)

    def find_by_phone(self, phone_number: str) -> User | None:
        if not phone_number.strip():
            return None
        normalized = normalize_phone_number(phone_number)
        return next(
            (user for user in self.load() if user.phone_number == normalized),
            None,
        )

    def create(self, user: User) -> int:
        if user.user_id is not None:
            raise StorageError("A new user must not already have an ID")
        normalized = self._normalized(user)
        try:
            with exclusive_file_lock(self._file_path):
                last_user_id, data = self._read_document_for_write()
                users = self._deserialize_all(data)
                persisted = User(
                    user_id=last_user_id + 1,
                    auth_provider=normalized.auth_provider,
                    auth_subject=normalized.auth_subject,
                    full_name=normalized.full_name,
                    phone_number=normalized.phone_number,
                    email=normalized.email,
                )
                users.append(persisted)
                self._validate_unique_identity(users)
                self._write(persisted.user_id, users)
                assert persisted.user_id is not None
                return persisted.user_id
        except (StorageError, UserIdentityConflictError):
            raise
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            BusinessError,
        ) as error:
            raise StorageError(f"Could not create user in {self._file_path}") from error

    def update(self, user: User) -> None:
        if user.user_id is None:
            raise StorageError("Cannot update a user without an ID")
        normalized = self._normalized(user)
        try:
            with exclusive_file_lock(self._file_path):
                last_user_id, data = self._read_document_for_write()
                users = self._deserialize_all(data)
                if not any(item.user_id == normalized.user_id for item in users):
                    raise StorageError(f"User {normalized.user_id} does not exist")
                updated = [
                    normalized if item.user_id == normalized.user_id else item for item in users
                ]
                self._validate_unique_identity(updated)
                self._write(last_user_id, updated)
        except (StorageError, UserIdentityConflictError):
            raise
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            BusinessError,
        ) as error:
            raise StorageError(f"Could not update user in {self._file_path}") from error

    def _read_document(self) -> tuple[int, list[dict[str, Any]]]:
        document = read_json(self._file_path)
        if not isinstance(document, dict):
            raise TypeError("User data must be a JSON object")
        validate_schema_version(document)
        users = document.get("users")
        last_user_id = document.get("last_user_id")
        if not isinstance(users, list) or not isinstance(last_user_id, int):
            raise TypeError("User data has an invalid document structure")
        ids = [int(item["user_id"]) for item in users]
        if last_user_id < max(ids, default=0):
            raise StorageError("User last_user_id is lower than an existing user ID")
        return last_user_id, users

    def _read_document_for_write(self) -> tuple[int, list[dict[str, Any]]]:
        if not self._file_path.exists() and self._file_path != DEFAULT_USERS_FILE:
            return 0, []
        return self._read_document()

    def _write(self, last_user_id: int | None, users: list[User]) -> None:
        if last_user_id is None:
            raise StorageError("Persisted user ID is missing")
        atomic_write_json(
            self._file_path,
            {
                "schema_version": SCHEMA_VERSION,
                "last_user_id": last_user_id,
                "users": [self._serialize(item) for item in users],
            },
        )

    def _deserialize_all(self, data: list[dict[str, Any]]) -> list[User]:
        users = [self._deserialize(item) for item in data]
        ids = [user.user_id for user in users]
        if len(ids) != len(set(ids)):
            raise StorageError("User data contains duplicate user IDs")
        self._validate_unique_identity(users)
        return users

    @staticmethod
    def _validate_unique_identity(users: list[User]) -> None:
        external = [(user.auth_provider.casefold(), user.auth_subject) for user in users]
        emails = [user.email for user in users if user.email]
        phones = [user.phone_number for user in users if user.phone_number]
        if len(external) != len(set(external)):
            raise UserIdentityConflictError("External authentication identity already exists")
        if len(emails) != len(set(emails)):
            raise UserIdentityConflictError("Email address already belongs to another user")
        if len(phones) != len(set(phones)):
            raise UserIdentityConflictError("Phone number already belongs to another user")

    @staticmethod
    def _normalized(user: User) -> User:
        return User(
            user_id=user.user_id,
            auth_provider=user.auth_provider.strip().casefold(),
            auth_subject=user.auth_subject.strip(),
            full_name=normalize_full_name(user.full_name),
            phone_number=(normalize_phone_number(user.phone_number) if user.phone_number else ""),
            email=normalize_email(user.email) if user.email else "",
        )

    @staticmethod
    def _serialize(user: User) -> dict[str, Any]:
        if user.user_id is None:
            raise StorageError("Cannot serialize a user without an ID")
        return {
            "user_id": user.user_id,
            "auth_provider": user.auth_provider,
            "auth_subject": user.auth_subject,
            "full_name": user.full_name,
            "phone_number": user.phone_number,
            "email": user.email,
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> User:
        return User(
            user_id=int(item["user_id"]),
            auth_provider=str(item["auth_provider"]),
            auth_subject=str(item["auth_subject"]),
            full_name=str(item["full_name"]),
            phone_number=(
                normalize_phone_number(str(item["phone_number"]))
                if item.get("phone_number")
                else ""
            ),
            email=normalize_email(str(item["email"])) if item.get("email") else "",
        )
