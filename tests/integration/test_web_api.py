"""HTTP security-boundary and use-case integration tests."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from cinema.auth import AuthContext, RequestCredentials
from cinema.composition import AuthAdapters, create_container
from cinema.config import ApiMode, AppEnvironment, Settings
from cinema.exceptions import AuthenticationError
from cinema.time_utils import local_now
from cinema.web import create_app


def test_combined_web_api_lifecycle(tmp_path: Path) -> None:
    settings = Settings(
        app_env=AppEnvironment.TEST,
        api_mode=ApiMode.COMBINED,
        cinema_data_dir=tmp_path / "data",
    )
    client = TestClient(create_app(settings))
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/config").json()["authEnabled"] is False
    movie = client.post(
        "/api/manager/movies",
        json={
            "title": "Dune",
            "duration_minutes": 120,
            "description": "Description",
            "genre": "drama",
            "ticket_price": 40,
        },
    )
    assert movie.status_code == 201
    show = client.post(
        "/api/manager/shows",
        json={
            "movie_id": movie.json()["movie_id"],
            "screening_date": (local_now() + timedelta(days=1)).date().isoformat(),
            "hall_id": 1,
            "shows_count": 1,
        },
    )
    assert show.status_code == 201
    show_id = show.json()[0]["show_id"]
    assert len(client.get(f"/api/shows/{show_id}/seats").json()) == 400
    booking = client.post(
        "/api/customer/bookings",
        json={
            "show_id": show_id,
            "seats": [
                {"row_number": 1, "seat_number": 1},
                {"row_number": 1, "seat_number": 2},
            ],
        },
    )
    assert booking.status_code == 201
    assert booking.json()["total_price"] == 80
    assert len(client.get("/api/customer/bookings").json()) == 1
    assert client.get("/api/manager/report").json()["revenue_nis"] == 80
    assert (
        client.delete(f"/api/customer/bookings/{booking.json()['booking_id']}").json()[
            "released_seats"
        ]
        == 2
    )
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-request-id"]


def test_gateway_mode_controls_external_routes(tmp_path: Path) -> None:
    customer = TestClient(
        create_app(
            Settings(
                app_env=AppEnvironment.TEST,
                api_mode=ApiMode.CUSTOMER,
                cinema_data_dir=tmp_path / "customer",
            )
        )
    )
    manager = TestClient(
        create_app(
            Settings(
                app_env=AppEnvironment.TEST,
                api_mode=ApiMode.MANAGER,
                cinema_data_dir=tmp_path / "manager",
            )
        )
    )
    assert customer.get("/manager").status_code == 404
    assert customer.get("/api/manager/report").status_code == 404
    assert manager.get("/").status_code == 404
    assert manager.get("/api/customer/bookings").status_code == 404


def test_http_error_mapping_and_static_pages(tmp_path: Path) -> None:
    settings = Settings(
        app_env=AppEnvironment.TEST,
        cinema_data_dir=tmp_path / "data",
    )
    container = create_container(settings)
    protected = TestClient(
        create_app(
            settings,
            container=replace(
                container,
                auth=AuthAdapters(FailingAuth(), FailingAuth()),
            ),
        )
    )
    assert protected.get("/api/customer/bookings").status_code == 401
    client = TestClient(create_app(settings, container=container))
    assert client.get("/").status_code == 200
    assert client.get("/manager").status_code == 200
    assert client.get("/api/shows/999/seats").status_code == 400
    assert (
        client.post(
            "/api/customer/bookings",
            json={"show_id": 999, "seats": [{"row_number": 1, "seat_number": 1}]},
        ).status_code
        == 400
    )


class FailingAuth:
    def authenticate(self, credentials: RequestCredentials) -> AuthContext:
        del credentials
        raise AuthenticationError("bad token")
