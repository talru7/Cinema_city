"""The only module that selects and wires concrete application adapters."""

from dataclasses import dataclass

from cinema.application import (
    BookingApplicationService,
    CatalogApplicationService,
    ManagerApplicationService,
)
from cinema.auth import AuthenticationService, Role
from cinema.auth.clerk import (
    ClerkAuthenticationService,
    ClerkJwtVerifier,
    HttpClerkProfileClient,
)
from cinema.auth.noauth import NoAuthAuthenticationService
from cinema.config import AuthProvider, Settings, StorageBackend
from cinema.exceptions import ConfigurationError
from cinema.services import CinemaManager, SchedulingService
from cinema.storage import StorageService, create_json_storage_service
from cinema.storage.sqlalchemy_backend import create_neon_storage_service


@dataclass(frozen=True, slots=True)
class AuthAdapters:
    customer: AuthenticationService
    manager: AuthenticationService


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    settings: Settings
    storage: StorageService
    catalog: CatalogApplicationService
    bookings: BookingApplicationService
    manager: ManagerApplicationService
    auth: AuthAdapters


def create_container(settings: Settings) -> ApplicationContainer:
    """Build all application services from validated settings."""
    storage = create_storage_service(settings)
    scheduler = SchedulingService(
        config_repository=storage.config_repository,
        movie_repository=storage.movie_repository,
        show_repository=storage.show_repository,
    )
    cinema_manager = CinemaManager(storage.movie_repository, scheduler)
    catalog = CatalogApplicationService(storage)
    return ApplicationContainer(
        settings=settings,
        storage=storage,
        catalog=catalog,
        bookings=BookingApplicationService(storage, catalog),
        manager=ManagerApplicationService(storage, cinema_manager, scheduler),
        auth=create_auth_adapters(settings, storage),
    )


def create_storage_service(settings: Settings) -> StorageService:
    """Select one fully replaceable storage implementation."""
    if settings.storage_backend is StorageBackend.JSON:
        return create_json_storage_service(data_dir=settings.cinema_data_dir)
    if settings.storage_backend is StorageBackend.NEON:
        return create_neon_storage_service(
            settings.neon_database_url,
            initialize_schema=settings.auto_create_schema,
        )
    raise ConfigurationError(
        f"The {settings.storage_backend.value} adapter is reserved but not shipped. "
        "Use json locally or neon in production."
    )


def create_auth_adapters(settings: Settings, storage: StorageService) -> AuthAdapters:
    """Create customer and manager boundary adapters without browser-supplied roles."""
    if settings.auth_provider is AuthProvider.NONE:
        return AuthAdapters(
            customer=NoAuthAuthenticationService(
                storage.user_repository,
                Role.CUSTOMER,
                settings.noauth_customer_email,
            ),
            manager=NoAuthAuthenticationService(
                storage.user_repository,
                Role.MANAGER,
                settings.noauth_manager_email,
            ),
        )
    if settings.auth_provider is AuthProvider.CLERK:
        verifier = ClerkJwtVerifier(
            settings.clerk_jwks_url,
            settings.clerk_issuer,
            settings.authorized_party_set,
        )
        profiles = HttpClerkProfileClient(
            settings.clerk_backend_api_url,
            settings.clerk_secret_key,
        )
        service = ClerkAuthenticationService(
            storage.user_repository,
            verifier,
            profiles,
            settings.manager_email_set,
        )
        return AuthAdapters(customer=service, manager=service)
    raise ConfigurationError(f"Unsupported authentication provider: {settings.auth_provider}")
