import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import Settings

_BCRYPT_COST = 12
_ALGORITHMS = ["HS256"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_COST)).decode(
        "utf-8"
    )


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: str, settings: Settings) -> tuple[str, int]:
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "jti": secrets.token_urlsafe(16),
    }
    token: str = str(jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM))
    return token, expires_in


def decode_access_token(token: str, settings: Settings) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access" or not payload.get("sub"):
        return None
    return payload
