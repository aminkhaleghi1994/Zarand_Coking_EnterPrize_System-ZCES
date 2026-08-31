SENSITIVE_KEYS_FULL_MASK = frozenset(
    {
        "password",
        "hashed_password",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "api_key",
    }
)
SENSITIVE_KEYS_IDENTIFIER = frozenset({"national_id", "personnel_code"})


def mask_secret(value: str | None) -> str:
    return "***" if value else ""


def mask_email(value: str | None) -> str:
    if not value:
        return ""
    if "@" not in value:
        return "***"
    local, _, domain = value.partition("@")
    return f"{local[0]}***@{domain}" if local else f"***@{domain}"


def mask_identifier(value: str | None) -> str:
    if not value:
        return ""
    return f"***{value[-4:]}" if len(value) > 4 else "***"


def mask_user_agent(value: str | None) -> str:
    if not value:
        return ""
    return value[:256]


def mask_snapshot(snapshot: dict[str, object] | None) -> dict[str, object] | None:
    if snapshot is None:
        return None
    masked: dict[str, object] = {}
    for key, value in snapshot.items():
        if not isinstance(value, str):
            masked[key] = value
        elif key.lower() in SENSITIVE_KEYS_FULL_MASK:
            masked[key] = mask_secret(value)
        elif key.lower() in SENSITIVE_KEYS_IDENTIFIER:
            masked[key] = mask_identifier(value)
        elif key.lower() == "email":
            masked[key] = mask_email(value)
        elif key.lower() == "user_agent":
            masked[key] = mask_user_agent(value)
        else:
            masked[key] = value
    return masked
