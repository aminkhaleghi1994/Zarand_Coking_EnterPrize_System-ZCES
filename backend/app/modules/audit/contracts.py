"""Public contract of the audit module for other modules (constitution VI).

Cross-module consumers import ONLY from this file. The report page
returns the module's AuditOut DTOs; snapshot masking (the ``read_full``
gate) is applied by the CALLER per its own permission semantics, matching
the audit endpoint's masking rules.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.modules.audit.schemas import AuditOut

__all__ = ["report_audit_page", "write_audit"]


def report_audit_page(
    session: Session,
    *,
    page: int,
    page_size: int,
    action: str | None = None,
    entity_type: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Page[AuditOut]:
    """Filtered, paginated audit page for the sensitive-operations report
    (US1). Newest first; snapshots are pre-masked by the standard masker at
    write time — the caller nulls snapshot contents for users without the
    unmask-level permission."""
    from app.modules.audit import repository

    return repository.list_audit_logs(
        session,
        page=page,
        page_size=page_size,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        date_from=date_from,
        date_to=date_to,
    )


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
