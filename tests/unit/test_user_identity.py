"""Tests for provider-independent user identity and local profiles."""

import json
from pathlib import Path

import pytest

from cinema.exceptions import StorageError, UserIdentityConflictError, UserValidationError
from cinema.models import User
from cinema.services import (
    LocalUserService,
    normalize_email,
    normalize_full_name,
    normalize_phone_number,
)
from cinema.storage import JsonUserRepository, create_json_storage_service


def test_identity_normalization() -> None:
    assert normalize_full_name("  Dana   Cohen ") == "Dana Cohen"
    assert normalize_email(" DANA@Example.COM ") == "dana@example.com"
    assert normalize_phone_number("050-123-4567") == "+972501234567"
    assert normalize_phone_number("+972 50 123 4567") == "+972501234567"


@pytest.mark.parametrize(
    ("value", "normalizer"),
    [
        (" ", normalize_full_name),
        ("x", normalize_full_name),
        ("bad-email", normalize_email),
        ("03-1234567", normalize_phone_number),
    ],
)
def test_invalid_identity_is_rejected(value: str, normalizer: object) -> None:
    with pytest.raises(UserValidationError):
        normalizer(value)  # type: ignore[operator]


def test_repository_create_update_and_external_lookup(tmp_path: Path) -> None:
    repo = JsonUserRepository(tmp_path / "users.json")
    user_id = repo.create(_user())
    persisted = repo.find_by_auth_identity("clerk", "subject-1")
    assert user_id == 1
    assert persisted is not None
    updated = User(
        user_id=user_id,
        auth_provider="clerk",
        auth_subject="subject-1",
        full_name="Dana Updated",
        phone_number="0501234567",
        email="DANA@example.com",
    )
    repo.update(updated)
    assert repo.find_by_id(1) == repo.find_by_email("dana@example.com")
    assert repo.find_by_phone("050-123-4567") == repo.find_by_id(1)


def test_local_user_service_preserves_internal_id(tmp_path: Path) -> None:
    repository = create_json_storage_service(data_dir=tmp_path / "data").user_repository
    service = LocalUserService(repository)
    first = service.get_or_update("Dana Cohen", "0501234567", "DANA@example.com")
    updated = service.get_or_update("Dana Updated", "+972501234567", "dana@example.com")
    second = service.get_or_update("Avi Levi", "0521234567", "avi@example.com")
    assert first.user_id == updated.user_id == 1
    assert second.user_id == 2
    assert updated.full_name == "Dana Updated"


def test_user_repository_rejects_conflicting_identities(tmp_path: Path) -> None:
    repo = JsonUserRepository(tmp_path / "users.json")
    repo.create(_user())
    with pytest.raises(UserIdentityConflictError):
        repo.create(_user(subject="subject-1", email="other@example.com"))
    with pytest.raises(UserIdentityConflictError):
        repo.create(_user(subject="subject-2", email="dana@example.com"))


def test_update_requires_existing_persisted_user(tmp_path: Path) -> None:
    repo = JsonUserRepository(tmp_path / "users.json")
    with pytest.raises(StorageError, match="without an ID"):
        repo.update(_user())
    with pytest.raises(StorageError, match="does not exist"):
        repo.update(_user(user_id=7))


def test_repository_rejects_bad_persisted_rows(tmp_path: Path) -> None:
    path = tmp_path / "users.json"
    row = {
        "user_id": 1,
        "auth_provider": "clerk",
        "auth_subject": "subject-1",
        "full_name": "Dana",
        "phone_number": "0501234567",
        "email": "dana@example.com",
    }
    path.write_text(
        json.dumps({"schema_version": 3, "last_user_id": 0, "users": [row]}),
        encoding="utf-8",
    )
    with pytest.raises(StorageError, match="last_user_id"):
        JsonUserRepository(path).load()


def _user(
    *,
    user_id: int | None = None,
    subject: str = "subject-1",
    email: str = "dana@example.com",
) -> User:
    return User(
        user_id=user_id,
        auth_provider="clerk",
        auth_subject=subject,
        full_name="Dana Cohen",
        phone_number="0501234567",
        email=email,
    )
