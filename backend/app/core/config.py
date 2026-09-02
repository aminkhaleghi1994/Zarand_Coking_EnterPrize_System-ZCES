from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class SettingsValidationError(RuntimeError):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_ENV: str = "development"
    APP_NAME: str = "ZCES"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str | None = None
    DATABASE_HOST: str | None = None
    DATABASE_PORT: int | None = None
    DATABASE_NAME: str | None = None
    DATABASE_USER: str | None = None
    DATABASE_PASSWORD: str | None = Field(default=None, repr=False)

    CORS_ALLOWED_ORIGINS: str | None = None

    JWT_SECRET_KEY: str = Field(default="", repr=False)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    COOKIE_SECURE: bool = False
    COOKIE_HTTPONLY: bool = True
    COOKIE_SAMESITE: str = "lax"

    INITIAL_ADMIN_EMAIL: str | None = None
    INITIAL_ADMIN_USERNAME: str | None = None
    INITIAL_ADMIN_PASSWORD: str | None = Field(default=None, repr=False)

    RELAY_ENABLED: bool = True
    RELAY_POLL_SECONDS: float = 2.0
    RELAY_BATCH_SIZE: int = Field(default=50, ge=1, le=500)

    @model_validator(mode="after")
    def _validate_jwt_config(self) -> "Settings":
        if len(self.JWT_SECRET_KEY) < 16:
            raise SettingsValidationError("JWT_SECRET_KEY must be at least 16 characters long")
        if self.ACCESS_TOKEN_EXPIRE_MINUTES < 1:
            raise SettingsValidationError("ACCESS_TOKEN_EXPIRE_MINUTES must be >= 1")
        if self.REFRESH_TOKEN_EXPIRE_DAYS < 1:
            raise SettingsValidationError("REFRESH_TOKEN_EXPIRE_DAYS must be >= 1")
        samesite = self.COOKIE_SAMESITE.lower()
        if samesite not in {"lax", "strict", "none"}:
            raise SettingsValidationError("COOKIE_SAMESITE must be one of lax, strict, none")
        self.COOKIE_SAMESITE = samesite
        return self

    @model_validator(mode="after")
    def _validate_database_config(self) -> "Settings":
        parts = {
            "DATABASE_HOST": self.DATABASE_HOST,
            "DATABASE_PORT": self.DATABASE_PORT,
            "DATABASE_NAME": self.DATABASE_NAME,
            "DATABASE_USER": self.DATABASE_USER,
            "DATABASE_PASSWORD": self.DATABASE_PASSWORD,
        }
        if not self.DATABASE_URL:
            missing = sorted(name for name, value in parts.items() if value is None)
            if missing:
                raise SettingsValidationError(
                    "Missing required environment variables: "
                    + ", ".join(missing)
                    + " (or set DATABASE_URL with all parts)"
                )
        self.DATABASE_URL = self._database_url()
        return self

    def _database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    @model_validator(mode="after")
    def _validate_log_level(self) -> "Settings":
        level = self.LOG_LEVEL.upper()
        if level not in _VALID_LOG_LEVELS:
            raise SettingsValidationError(
                f"LOG_LEVEL must be one of {sorted(_VALID_LOG_LEVELS)}, got an invalid value"
            )
        self.LOG_LEVEL = level
        return self

    @model_validator(mode="after")
    def _validate_relay_config(self) -> "Settings":
        if self.RELAY_POLL_SECONDS <= 0:
            raise SettingsValidationError("RELAY_POLL_SECONDS must be greater than 0")
        return self

    @property
    def cors_origins(self) -> list[str]:
        if not self.CORS_ALLOWED_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
