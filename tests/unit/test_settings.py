"""Configuration and composition-root selection tests."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cinema import db_init
from cinema.composition import create_storage_service
from cinema.config import AppEnvironment, AuthProvider, Settings, StorageBackend, load_settings
from cinema.exceptions import ConfigurationError
from cinema.storage import JsonMovieRepository


def test_loads_environment_specific_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env.local").write_text(
        "APP_ENV=local\nAUTH_ENABLED=false\nAUTH_PROVIDER=none\nPORT=8123\n",
        encoding="utf-8",
    )
    settings = load_settings("local")
    assert settings.port == 8123
    assert settings.app_env is AppEnvironment.LOCAL


def test_settings_reject_inconsistent_auth_and_missing_neon_url() -> None:
    with pytest.raises(ValueError, match="AUTH_ENABLED"):
        Settings(auth_enabled=True, auth_provider=AuthProvider.NONE)
    with pytest.raises(ValueError, match="NEON_DATABASE_URL"):
        Settings(storage_backend=StorageBackend.NEON)


def test_composition_selects_json_and_rejects_reserved_adapters(tmp_path: Path) -> None:
    storage = create_storage_service(Settings(cinema_data_dir=tmp_path / "data"))
    assert isinstance(storage.movie_repository, JsonMovieRepository)
    with pytest.raises(ConfigurationError, match="reserved"):
        create_storage_service(Settings(storage_backend=StorageBackend.D1))


def test_explicit_database_initializer(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ConfigurationError, match="supports"):
        db_init.main()
    settings = Settings(
        storage_backend=StorageBackend.NEON,
        neon_database_url="postgresql://example.invalid/db",
    )
    monkeypatch.setattr(db_init, "load_settings", lambda: settings)
    create = MagicMock()
    monkeypatch.setattr(db_init, "create_neon_storage_service", create)
    db_init.main()
