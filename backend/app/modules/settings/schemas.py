"""Settings module schemas (contracts/reports-settings-endpoints.md).

Typed validation: the fixed key set lives in ``defaults.py``; the value's
shape is validated per ``value_type`` — unknown keys and wrong types raise
VALIDATION_ERROR before any storage write.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.settings.defaults import default_for


class SettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    value: Any
    value_type: str
    description: str
    description_fa: str
    version: int
    updated_at: datetime


class SettingUpdateIn(BaseModel):
    value: Any
    version: int = Field(ge=1)


def validate_setting_value(key: str, value: Any) -> tuple[Any, str]:
    """Validate a (key, raw value) pair against the fixed key set.

    Returns the canonical stored value and its ``value_type``; raises
    VALIDATION_ERROR for unknown keys or values whose type does not match
    the key's declared type.
    """
    setting_default = default_for(key)
    if setting_default is None:
        raise _unknown_key(key)
    value_type = setting_default.value_type

    if value_type == "boolean":
        if not isinstance(value, bool):
            raise _wrong_type(key, "boolean")
        return value, value_type
    if value_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise _wrong_type(key, "integer")
        return value, value_type
    if value_type == "string":
        if not isinstance(value, str):
            raise _wrong_type(key, "string")
        return value, value_type
    if value_type == "json":
        if not isinstance(value, (list, dict)):
            raise _wrong_type(key, "json (list or object)")
        return value, value_type
    raise _unknown_key(key)  # pragma: no cover - guarded by fixed types


def _unknown_key(key: str) -> Exception:
    from app.core.errors import validation_error

    return validation_error(f"Unknown setting key: {key}", {"key": key})


def _wrong_type(key: str, expected: str) -> Exception:
    from app.core.errors import validation_error

    return validation_error(
        f"Setting {key} expects a {expected} value", {"key": key, "expected": expected}
    )
