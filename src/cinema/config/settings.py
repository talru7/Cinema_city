"""Validated settings loaded once at the application composition root."""

import os
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cinema.exceptions import ConfigurationError


class AppEnvironment(StrEnum):
    """Supported runtime environments."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


class StorageBackend(StrEnum):
    """Storage adapters known to the composition root."""

    JSON = "json"
    NEON = "neon"
    D1 = "d1"
    MONGODB = "mongodb"


class AuthProvider(StrEnum):
    """Authentication adapters known to the composition root."""

    NONE = "none"
    CLERK = "clerk"


class ApiMode(StrEnum):
    """External gateway layouts supported by the same application code."""

    COMBINED = "combined"
    CUSTOMER = "customer"
    MANAGER = "manager"


class Settings(BaseSettings):
    """Single validated source of runtime configuration."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        env_file_encoding="utf-8",
    )

    app_env: AppEnvironment = AppEnvironment.LOCAL
    storage_backend: StorageBackend = StorageBackend.JSON
    auth_enabled: bool = False
    auth_provider: AuthProvider = AuthProvider.NONE
    api_mode: ApiMode = ApiMode.COMBINED

    cinema_data_dir: Path | None = None
    cinema_log_dir: Path | None = None
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    cors_origins: str = ""

    manager_emails: str = ""
    noauth_customer_email: str = "customer@local.invalid"
    noauth_manager_email: str = "manager@local.invalid"

    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_issuer: str = ""
    clerk_jwks_url: str = ""
    clerk_frontend_api_url: str = ""
    clerk_backend_api_url: str = "https://api.clerk.com"
    clerk_authorized_parties: str = ""

    neon_database_url: str = ""
    d1_database_id: str = ""
    d1_account_id: str = ""
    d1_api_token: str = ""
    mongodb_uri: str = ""
    mongodb_database: str = "cinema_city"
    auto_create_schema: bool = False

    @property
    def manager_email_set(self) -> frozenset[str]:
        return _split_csv(self.manager_emails)

    @property
    def authorized_party_set(self) -> frozenset[str]:
        return _split_csv(self.clerk_authorized_parties)

    @property
    def allowed_host_list(self) -> list[str]:
        return list(_split_csv(self.allowed_hosts))

    @property
    def cors_origin_list(self) -> list[str]:
        return list(_split_csv(self.cors_origins))

    @model_validator(mode="after")
    def validate_adapter_configuration(self) -> "Settings":
        if self.auth_enabled and self.auth_provider is not AuthProvider.CLERK:
            raise ValueError("AUTH_ENABLED=true currently requires AUTH_PROVIDER=clerk")
        if not self.auth_enabled and self.auth_provider is not AuthProvider.NONE:
            raise ValueError("AUTH_ENABLED=false requires AUTH_PROVIDER=none")
        if self.auth_enabled:
            required = {
                "CLERK_PUBLISHABLE_KEY": self.clerk_publishable_key,
                "CLERK_SECRET_KEY": self.clerk_secret_key,
                "CLERK_ISSUER": self.clerk_issuer,
                "CLERK_JWKS_URL": self.clerk_jwks_url,
                "CLERK_FRONTEND_API_URL": self.clerk_frontend_api_url,
                "CLERK_AUTHORIZED_PARTIES": self.clerk_authorized_parties,
            }
            missing = [name for name, value in required.items() if not value.strip()]
            if missing:
                raise ValueError(f"Missing Clerk settings: {', '.join(missing)}")
        if self.storage_backend is StorageBackend.NEON and not self.neon_database_url:
            raise ValueError("STORAGE_BACKEND=neon requires NEON_DATABASE_URL")
        return self


def load_settings(environment: str | None = None) -> Settings:
    """Load base and environment-specific dotenv files exactly once."""
    app_env = environment or os.environ.get("APP_ENV", AppEnvironment.LOCAL.value)
    current = Path.cwd()
    env_files = tuple(
        path for path in (current / ".env", current / f".env.{app_env}") if path.exists()
    )
    try:
        settings_factory = cast(Any, Settings)
        return cast(Settings, settings_factory(_env_file=env_files or None))
    except ValueError as error:
        raise ConfigurationError(str(error)) from error


def _split_csv(value: str) -> frozenset[str]:
    return frozenset(item.strip().casefold() for item in value.split(",") if item.strip())
