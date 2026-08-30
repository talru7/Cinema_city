"""Authentication adapter and server-side authorization tests."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from cinema.auth import Permission, RequestCredentials, Role
from cinema.auth.clerk import (
    ClerkAuthenticationService,
    ClerkJwtVerifier,
    ClerkProfile,
    HttpClerkProfileClient,
)
from cinema.auth.noauth import NoAuthAuthenticationService
from cinema.exceptions import AuthenticationError, AuthorizationError
from cinema.models import User
from cinema.storage import create_json_storage_service


def test_noauth_uses_server_configured_role_and_local_user(tmp_path: Path) -> None:
    users = create_json_storage_service(data_dir=tmp_path / "data").user_repository
    service = NoAuthAuthenticationService(users, Role.MANAGER, "admin@local.invalid")
    first = service.authenticate(RequestCredentials(bearer_token="browser-value-is-ignored"))
    second = service.authenticate(RequestCredentials())
    assert first == second
    assert first.role is Role.MANAGER
    first.require(Permission.MANAGE_MOVIES)
    assert users.find_by_auth_identity("none", "local-manager") is not None


def test_customer_context_rejects_manager_permission(tmp_path: Path) -> None:
    context = NoAuthAuthenticationService(
        create_json_storage_service(data_dir=tmp_path / "data").user_repository,
        Role.CUSTOMER,
        "customer@local.invalid",
    ).authenticate(RequestCredentials())
    with pytest.raises(AuthorizationError):
        context.require(Permission.VIEW_REPORTS)


def test_clerk_maps_verified_manager_and_refreshes_profile(tmp_path: Path) -> None:
    users = create_json_storage_service(data_dir=tmp_path / "data").user_repository
    verifier = FakeVerifier({"sub": "user_123"})
    profile = ClerkProfile(
        subject="user_123",
        full_name="Dana Cohen",
        email="admin@example.com",
        email_verified=True,
        phone_number="0501234567",
    )
    service = ClerkAuthenticationService(
        users,
        verifier,
        FakeProfiles(profile),
        frozenset({"admin@example.com"}),
    )
    context = service.authenticate(RequestCredentials("token"))
    assert context.role is Role.MANAGER
    assert context.user_id == 1
    assert service.authenticate(RequestCredentials("token")).user_id == 1
    with pytest.raises(AuthenticationError, match="required"):
        service.authenticate(RequestCredentials())


def test_unverified_email_never_grants_manager(tmp_path: Path) -> None:
    service = ClerkAuthenticationService(
        create_json_storage_service(data_dir=tmp_path / "data").user_repository,
        FakeVerifier({"sub": "user_123"}),
        FakeProfiles(ClerkProfile("user_123", "Dana", "admin@example.com", False, "")),
        frozenset({"admin@example.com"}),
    )
    assert service.authenticate(RequestCredentials("token")).role is Role.CUSTOMER


def test_verified_email_links_new_provider_to_existing_user(tmp_path: Path) -> None:
    users = create_json_storage_service(data_dir=tmp_path / "data").user_repository
    original_id = users.create(User(None, "auth0", "old-subject", "Dana", "", "dana@example.com"))
    service = ClerkAuthenticationService(
        users,
        FakeVerifier({"sub": "clerk-subject"}),
        FakeProfiles(ClerkProfile("clerk-subject", "Dana", "dana@example.com", True, "")),
        frozenset(),
    )
    context = service.authenticate(RequestCredentials("token"))
    assert context.user_id == original_id
    assert users.find_by_auth_identity("clerk", "clerk-subject") is not None


def test_clerk_jwt_verifier_checks_signature_claims_and_azp() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = ClerkJwtVerifier(
        "https://example.test/jwks",
        "https://clerk.example.test",
        frozenset({"https://cinema.example.com"}),
    )
    verifier._jwks_client = cast(Any, FakeJwks(private_key.public_key()))  # noqa: SLF001
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "user_123",
            "iss": "https://clerk.example.test",
            "azp": "https://cinema.example.com",
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
    )
    assert verifier.verify(token)["sub"] == "user_123"
    wrong_party = jwt.encode(
        {
            "sub": "user_123",
            "iss": "https://clerk.example.test",
            "azp": "https://evil.example.com",
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
    )
    with pytest.raises(AuthenticationError, match="authorized party"):
        verifier.verify(wrong_party)
    with pytest.raises(AuthenticationError, match="Invalid"):
        verifier.verify("not-a-jwt")


def test_http_clerk_profile_client_uses_verified_primary_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://api.clerk.test/v1/users/user_1"),
        json={
            "first_name": "Dana",
            "last_name": "Cohen",
            "primary_email_address_id": "email_1",
            "email_addresses": [
                {
                    "id": "email_1",
                    "email_address": "DANA@example.com",
                    "verification": {"status": "verified"},
                }
            ],
            "primary_phone_number_id": "phone_1",
            "phone_numbers": [{"id": "phone_1", "phone_number": "+972501234567"}],
        },
    )
    monkeypatch.setattr("cinema.auth.clerk.httpx.get", lambda *args, **kwargs: response)
    profile = HttpClerkProfileClient("https://api.clerk.test", "secret").fetch("user_1")
    assert profile.full_name == "Dana Cohen"
    assert profile.email == "dana@example.com"
    assert profile.email_verified is True


class FakeVerifier:
    def __init__(self, claims: dict[str, object]) -> None:
        self._claims = claims

    def verify(self, token: str) -> dict[str, object]:
        assert token
        return self._claims


class FakeProfiles:
    def __init__(self, profile: ClerkProfile) -> None:
        self._profile = profile

    def fetch(self, subject: str) -> ClerkProfile:
        assert subject == self._profile.subject
        return self._profile


class FakeJwks:
    def __init__(self, public_key: object) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
        jwt.get_unverified_header(token)
        return SimpleNamespace(key=self._public_key)
