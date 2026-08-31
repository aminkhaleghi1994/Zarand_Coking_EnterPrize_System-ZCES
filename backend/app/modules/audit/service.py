import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.common.masking import mask_snapshot
from app.core.tracing import get_trace_id
from app.modules.audit.models import AuditLog
from app.modules.audit.repository import create

logger = logging.getLogger(__name__)


def write_audit(
    session: Session | None,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    critical: bool = False,
) -> None:
    record = AuditLog(
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before_snapshot=mask_snapshot(before),
        after_snapshot=mask_snapshot(after),
        trace_id=get_trace_id(),
    )

    if critical:
        if session is None:
            logger.error("Critical audit write requested without a session")
            return
        create(session, record)
        return

    try:
        from app.core.database import get_session_factory

        with get_session_factory()() as isolated:
            isolated.add(record)
            isolated.commit()
    except Exception:
        logger.warning(
            "Deferred audit write failed for action=%s entity_type=%s", action, entity_type
        )
