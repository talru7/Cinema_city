"""Clerk JWT verification and local-user resolution."""

from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import jwt
from jwt import PyJWKClient

from cinema.auth.context import AuthContext, Role, context_for_role
from cinema.auth.interfaces import AuthenticationService, RequestCredentials
from cinema.exceptions import AuthenticationError
from cinema.models import User
from cinema.storage.interfaces import UserRepository


class TokenVerifier(Protocol):
    def verify(self, token: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class ClerkProfile:
    subject: str
    full_name: str
    email: str
    email_verified: bool
    phone_number: str


class ClerkProfileClient(Protocol):
    def fetch(self, subject: str) -> ClerkProfile: ...


class ClerkJwtVerifier:
    """Verify signature and required Clerk session-token claims."""

    def __init__(
        self,
        jwks_url: str,
        issuer: str,
        authorized_parties: frozenset[str],
    ) -> None:
        self._jwks_client = PyJWKClient(jwks_url, cache_keys=True)
        self._issuer = issuer.rstrip("/")
        self._authorized_parties = authorized_parties

    def verify(self, token: str) -> dict[str, Any]:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                options={"require": ["sub", "exp", "iat", "nbf"]},
                leeway=5,
            )
        except jwt.PyJWTError as error:
            raise AuthenticationError("Invalid or expired session token") from error
        authorized_party = str(claims.get("azp", "")).casefold()
        if self._authorized_parties and authorized_party not in self._authorized_parties:
            raise AuthenticationError("Token authorized party is not allowed")
        return claims


class HttpClerkProfileClient:
    """Read verified profile data from Clerk's backend API."""

    def __init__(self, backend_api_url: str, secret_key: str) -> None:
        self._base_url = backend_api_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {secret_key}"}

    def fetch(self, subject: str) -> ClerkProfile:
        try:
            response = httpx.get(
                f"{self._base_url}/v1/users/{subject}",
                headers=self._headers,
                timeout=5.0,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise AuthenticationError("Could not resolve authenticated Clerk user") from error

        primary_email_id = payload.get("primary_email_address_id")
        email = ""
        email_verified = False
        for item in payload.get("email_addresses", []):
            if item.get("id") == primary_email_id:
                email = str(item.get("email_address", "")).casefold()
                verification = item.get("verification") or {}
                email_verified = verification.get("status") == "verified"
                break

        primary_phone_id = payload.get("primary_phone_number_id")
        phone = next(
            (
                str(item.get("phone_number", ""))
                for item in payload.get("phone_numbers", [])
                if item.get("id") == primary_phone_id
            ),
            "",
        )
        full_name = (
            " ".join(
                part
                for part in (
                    str(payload.get("first_name") or "").strip(),
                    str(payload.get("last_name") or "").strip(),
                )
                if part
            )
            or "Cinema Customer"
        )
        return ClerkProfile(
            subject=subject,
            full_name=full_name,
            email=email,
            email_verified=email_verified,
            phone_number=phone,
        )


class ClerkAuthenticationService(AuthenticationService):
    """Map a verified Clerk identity to an internal user and role."""

    def __init__(
        self,
        user_repository: UserRepository,
        verifier: TokenVerifier,
        profile_client: ClerkProfileClient,
        manager_emails: frozenset[str],
    ) -> None:
        self._users = user_repository
        self._verifier = verifier
        self._profiles = profile_client
        self._manager_emails = manager_emails

    def authenticate(self, credentials: RequestCredentials) -> AuthContext:
        if not credentials.bearer_token:
            raise AuthenticationError("Bearer token is required")
        claims = self._verifier.verify(credentials.bearer_token)
        subject = str(claims["sub"])
        profile = self._profiles.fetch(subject)
        user = self._users.find_by_auth_identity("clerk", subject)
        if user is None:
            linked = (
                self._users.find_by_email(profile.email)
                if profile.email and profile.email_verified
                else None
            )
            if linked is not None:
                if linked.user_id is None:
                    raise RuntimeError("Persisted linked user has no ID")
                user_id = linked.user_id
                self._users.update(
                    User(
                        user_id=user_id,
                        auth_provider="clerk",
                        auth_subject=subject,
                        full_name=profile.full_name,
                        phone_number=profile.phone_number,
                        email=profile.email,
                    )
                )
            else:
                user_id = self._users.create(
                    User(
                        user_id=None,
                        auth_provider="clerk",
                        auth_subject=subject,
                        full_name=profile.full_name,
                        phone_number=profile.phone_number,
                        email=profile.email,
                    )
                )
        else:
            if user.user_id is None:
                raise RuntimeError("Persisted Clerk user has no ID")
            user_id = user.user_id
            refreshed = User(
                user_id=user_id,
                auth_provider=user.auth_provider,
                auth_subject=user.auth_subject,
                full_name=profile.full_name,
                phone_number=profile.phone_number,
                email=profile.email,
            )
            if refreshed != user:
                self._users.update(refreshed)

        is_manager = profile.email_verified and profile.email in self._manager_emails
        role = Role.MANAGER if is_manager else Role.CUSTOMER
        return context_for_role(user_id, role, profile.email)
