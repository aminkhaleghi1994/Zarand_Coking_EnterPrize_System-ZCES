"""Settings service (US4): version-guarded, audited updates in one
transaction; typed reads with code-default fallback (research R7).

- unknown key / wrong type -> VALIDATION_ERROR before any write;
- stale version -> STALE_VERSION before any write (requirements §25);
- every successful update writes a SETTING_UPDATED audit row with
  before/after snapshots (masked by the standard masker) in the same
  transaction (requirements §21: "تغییر تنظیمات").
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.common.scope import ScopeContext
from app.core.errors import STALE_VERSION, AppError, not_found
from app.modules.audit.contracts import write_audit
from app.modules.settings import repository
from app.modules.settings.models import Setting
from app.modules.settings.schemas import validate_setting_value

STALE_MESSAGE = "This setting changed since you opened it - refresh and retry"


def _snapshot(setting: Setting) -> dict[str, Any]:
    return {
        "key": setting.key,
        "value": setting.value,
        "value_type": setting.value_type,
    }


def list_settings(session: Session) -> list[Setting]:
    return repository.list_all(session)


def update_setting(
    session: Session,
    context: ScopeContext,
    key: str,
    value: Any,
    expected_version: int,
) -> Setting:
    """Validate, version-check, update, and audit — atomically."""
    canonical_value, _value_type = validate_setting_value(key, value)

    setting = repository.get_by_key(session, key)
    if setting is None:
        # The seed covers the fixed key set; a missing row is a seed gap,
        # surfaced as 404 rather than silently re-created at update time.
        raise not_found("Setting not found")

    if setting.version != expected_version:
        raise AppError(STALE_VERSION, STALE_MESSAGE, status_code=409)

    before = _snapshot(setting)
    setting.value = canonical_value
    setting.version += 1
    session.add(setting)
    session.flush()

    write_audit(
        session,
        action="SETTING_UPDATED",
        entity_type="setting",
        entity_id=setting.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after=_snapshot(setting),
        critical=True,
    )
    session.commit()
    session.refresh(setting)
    return setting


def get_setting(
    session: Session, key: str, default: Any = None
) -> Any:
    """Contract read: typed value with fallback (missing row never breaks
    a consumer). ``default`` wins only when the row is absent."""
    setting = repository.get_by_key(session, key)
    if setting is None:
        return default
    return setting.value


def get_setting_bool(session: Session, key: str, default: bool = False) -> bool:
    value = get_setting(session, key, default)
    return value if isinstance(value, bool) else default
