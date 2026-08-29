import pytest

from app.core.config import Settings, SettingsValidationError

_DB_VARS = [
    "DATABASE_URL",
    "DATABASE_HOST",
    "DATABASE_PORT",
    "DATABASE_NAME",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
]


def _clear_db_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _DB_VARS:
        monkeypatch.delenv(name, raising=False)


def test_missing_database_config_names_variables_and_never_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("DATABASE_PASSWORD", "super-secret-value")
    with pytest.raises(SettingsValidationError) as exc:
        Settings(_env_file=None)
    message = str(exc.value)
    assert "DATABASE_URL" in message
    assert "DATABASE_HOST" in message
    assert "super-secret-value" not in message


def test_composes_url_from_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("DATABASE_HOST", "db.internal")
    monkeypatch.setenv("DATABASE_PORT", "5432")
    monkeypatch.setenv("DATABASE_NAME", "zces_dev")
    monkeypatch.setenv("DATABASE_USER", "zces_user")
    monkeypatch.setenv("DATABASE_PASSWORD", "pw")
    settings = Settings(_env_file=None)
    assert settings.DATABASE_URL == "postgresql+psycopg://zces_user:pw@db.internal:5432/zces_dev"


def test_explicit_url_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h:1/d")
    settings = Settings(_env_file=None)
    assert settings.DATABASE_URL == "postgresql+psycopg://u:p@h:1/d"


def test_invalid_log_level_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("LOG_LEVEL", "BOGUS")
    with pytest.raises(SettingsValidationError) as exc:
        Settings(_env_file=None)
    assert "LOG_LEVEL" in str(exc.value)


def test_log_level_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    settings = Settings(_env_file=None)
    assert settings.LOG_LEVEL == "DEBUG"


def test_cors_origins_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_db_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://a.test, http://b.test ,")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://a.test", "http://b.test"]
