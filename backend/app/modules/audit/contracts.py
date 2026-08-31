from typing import Any

from sqlalchemy.orm import Session

__all__ = ["write_audit"]


def write_audit(
    session: Session | None,
    *,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    actor_user_id: Any = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    critical: bool = False,
) -> None:
    from app.modules.audit.service import write_audit as _write_audit

    _write_audit(
        session,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        before=before,
        after=after,
        critical=critical,
    )
