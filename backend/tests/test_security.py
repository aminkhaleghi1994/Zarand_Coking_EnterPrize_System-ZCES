from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_opaque_token,
    hash_password,
    new_opaque_token,
    verify_password,
)


def _settings(**overrides: object) -> Settings:
    base = {
        "DATABASE_URL": "sqlite://",
        "JWT_SECRET_KEY": "unit-test-secret-key-0123456789abcdef",
        "_env_file": None,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("S3cure-Passw0rd!")
    assert hashed.startswith("$2b$12$")
    assert verify_password("S3cure-Passw0rd!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_password_hash_is_salted() -> None:
    assert hash_password("same-input") != hash_password("same-input")


def test_verify_password_rejects_malformed_hash() -> None:
    assert not verify_password("x", "not-a-bcrypt-hash")


def test_access_token_roundtrip() -> None:
    settings = _settings()
    token, expires_in = create_access_token("user-123", settings)
    assert expires_in == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    payload = decode_access_token(token, settings)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert "jti" in payload


def test_tampered_token_rejected() -> None:
    settings = _settings()
    token, _ = create_access_token("user-123", settings)
    assert decode_access_token(token + "x", settings) is None


def test_expired_token_rejected() -> None:
    settings = _settings()
    now = datetime.now(UTC)
    expired = jwt.encode(
        {"sub": "user-123", "type": "access", "iat": now, "exp": now - timedelta(seconds=1)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_access_token(expired, settings) is None


def test_foreign_secret_rejected() -> None:
    settings = _settings()
    token, _ = create_access_token("user-123", settings)
    other = _settings(JWT_SECRET_KEY="another-secret-key-0123456789abcdef")
    assert decode_access_token(token, other) is None


def test_wrong_type_token_rejected() -> None:
    settings = _settings()
    now = datetime.now(UTC)
    refresh_like = jwt.encode(
        {"sub": "user-123", "type": "refresh", "iat": now, "exp": now + timedelta(minutes=5)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_access_token(refresh_like, settings) is None


def test_opaque_tokens_unique_and_hash_stable() -> None:
    a, b = new_opaque_token(), new_opaque_token()
    assert a != b
    assert len(a) >= 32
    assert hash_opaque_token(a) == hash_opaque_token(a)
    assert hash_opaque_token(a) != hash_opaque_token(b)
    assert len(hash_opaque_token(a)) == 64


def test_missing_jwt_secret_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("JWT_SECRET_KEY", "short")
    with pytest.raises(Exception, match="JWT_SECRET_KEY"):
        Settings(_env_file=None)
