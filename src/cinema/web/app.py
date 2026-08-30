"""FastAPI adapter with public, customer, and manager security boundaries."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from cinema.auth import (
    AuthContext,
    AuthenticationService,
    RequestCredentials,
    Role,
)
from cinema.composition import ApplicationContainer, create_container
from cinema.config import ApiMode, Settings, load_settings
from cinema.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessError,
    CinemaError,
    StorageError,
)
from cinema.models import Genre
from cinema.web.schemas import (
    CreateBookingRequest,
    CreateMovieRequest,
    ScheduleMovieRequest,
)

WEB_ROOT = Path(__file__).with_name("static")
bearer = HTTPBearer(auto_error=False)


def create_app(
    settings: Settings | None = None,
    container: ApplicationContainer | None = None,
) -> FastAPI:
    """Create an independently testable HTTP adapter."""
    resolved_settings = settings or load_settings()
    dependencies = container or create_container(resolved_settings)
    app = FastAPI(
        title="Cinema City API",
        version="10.0.0",
        docs_url="/api/docs" if resolved_settings.app_env.value != "production" else None,
        redoc_url=None,
    )
    app.state.container = dependencies
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=resolved_settings.allowed_host_list,
    )
    if resolved_settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved_settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
    _register_errors(app)
    _register_security_headers(app)
    app.mount("/assets", StaticFiles(directory=WEB_ROOT), name="assets")
    app.include_router(_public_router(dependencies))
    if resolved_settings.api_mode in (ApiMode.COMBINED, ApiMode.CUSTOMER):
        app.include_router(_customer_router(dependencies))
    if resolved_settings.api_mode in (ApiMode.COMBINED, ApiMode.MANAGER):
        app.include_router(_manager_router(dependencies))
    _register_pages(app, resolved_settings.api_mode)
    return app


def _public_router(container: ApplicationContainer) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["public"])

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/config")
    def frontend_config() -> dict[str, Any]:
        settings = container.settings
        return {
            "authEnabled": settings.auth_enabled,
            "publishableKey": settings.clerk_publishable_key if settings.auth_enabled else "",
            "clerkScriptUrl": (
                f"{settings.clerk_frontend_api_url.rstrip('/')}/npm/"
                "@clerk/clerk-js@5/dist/clerk.browser.js"
                if settings.auth_enabled
                else ""
            ),
            "apiMode": settings.api_mode.value,
        }

    @router.get("/movies")
    def movies() -> list[Any]:
        return container.catalog.list_movies()

    @router.get("/shows")
    def shows(genre: Genre | None = None) -> list[Any]:
        return container.catalog.list_upcoming_shows(genre=genre)

    @router.get("/shows/{show_id}/seats")
    def show_seats(show_id: int) -> list[Any]:
        return container.catalog.list_seats(show_id)

    return router


def _customer_router(container: ApplicationContainer) -> APIRouter:
    router = APIRouter(prefix="/api/customer", tags=["customer"])
    authenticate = _auth_dependency(container.auth.customer, require_manager=False)
    AuthenticatedCustomer = Annotated[AuthContext, Depends(authenticate)]

    @router.post("/bookings", status_code=201)
    def create_booking(
        request: CreateBookingRequest,
        auth: AuthenticatedCustomer,
    ) -> Any:
        coordinates = tuple((seat.row_number, seat.seat_number) for seat in request.seats)
        return container.bookings.create_booking(auth, request.show_id, coordinates)

    @router.get("/bookings")
    def my_bookings(auth: AuthenticatedCustomer) -> list[Any]:
        return container.bookings.list_my_bookings(auth)

    @router.delete("/bookings/{booking_id}")
    def cancel_booking(
        booking_id: int,
        auth: AuthenticatedCustomer,
    ) -> dict[str, int]:
        released = container.bookings.cancel_booking(auth, booking_id)
        return {"booking_id": booking_id, "released_seats": released}

    return router


def _manager_router(container: ApplicationContainer) -> APIRouter:
    router = APIRouter(prefix="/api/manager", tags=["manager"])
    authenticate = _auth_dependency(container.auth.manager, require_manager=True)
    AuthenticatedManager = Annotated[AuthContext, Depends(authenticate)]

    @router.post("/movies", status_code=201)
    def add_movie(
        request: CreateMovieRequest,
        auth: AuthenticatedManager,
    ) -> Any:
        return container.manager.add_movie(auth, **request.model_dump())

    @router.post("/shows", status_code=201)
    def schedule_movie(
        request: ScheduleMovieRequest,
        auth: AuthenticatedManager,
    ) -> list[Any]:
        return list(container.manager.schedule_movie(auth, **request.model_dump()))

    @router.get("/bookings")
    def all_bookings(auth: AuthenticatedManager) -> dict[str, Any]:
        bookings, seats = container.manager.list_all_bookings(auth)
        return {"bookings": bookings, "booking_seats": seats}

    @router.get("/report")
    def report(auth: AuthenticatedManager) -> Any:
        return container.manager.report(auth)

    return router


def _auth_dependency(
    service: AuthenticationService,
    *,
    require_manager: bool,
) -> Callable[[HTTPAuthorizationCredentials | None], AuthContext]:
    def authenticate(
        authorization: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(bearer),
        ],
    ) -> AuthContext:
        token = authorization.credentials if authorization is not None else None
        context = service.authenticate(RequestCredentials(bearer_token=token))
        if require_manager and context.role is not Role.MANAGER:
            raise AuthorizationError("Manager role is required")
        return context

    return authenticate


def _register_pages(app: FastAPI, mode: ApiMode) -> None:
    if mode in (ApiMode.COMBINED, ApiMode.CUSTOMER):

        @app.get("/", include_in_schema=False)
        def customer_page() -> FileResponse:
            return FileResponse(WEB_ROOT / "index.html")

    if mode in (ApiMode.COMBINED, ApiMode.MANAGER):

        @app.get("/manager", include_in_schema=False)
        def manager_page() -> FileResponse:
            return FileResponse(WEB_ROOT / "manager.html")


def _register_errors(app: FastAPI) -> None:
    @app.exception_handler(AuthenticationError)
    async def authentication_error(_: Request, error: AuthenticationError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(error)})

    @app.exception_handler(AuthorizationError)
    async def authorization_error(_: Request, error: AuthorizationError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(error)})

    @app.exception_handler(BusinessError)
    async def business_error(_: Request, error: BusinessError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.exception_handler(StorageError)
    async def storage_error(_: Request, error: StorageError) -> JSONResponse:
        del error
        return JSONResponse(status_code=503, content={"detail": "Storage is unavailable"})

    @app.exception_handler(CinemaError)
    async def cinema_error(_: Request, error: CinemaError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(error)})


def _register_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", str(uuid4()))
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


def run(mode: ApiMode = ApiMode.COMBINED) -> None:
    settings = load_settings().model_copy(update={"api_mode": mode})
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        proxy_headers=settings.app_env.value == "production",
    )


def main() -> None:
    run(ApiMode.COMBINED)


def customer_main() -> None:
    run(ApiMode.CUSTOMER)


def manager_main() -> None:
    run(ApiMode.MANAGER)
