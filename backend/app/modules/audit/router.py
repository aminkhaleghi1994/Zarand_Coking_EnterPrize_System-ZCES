import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext
from app.core.database import get_db
from app.modules.audit import repository
from app.modules.audit.schemas import AuditOut
from app.modules.user.dependencies import require_permission
from app.modules.user.schemas import PageParams

require_audit_read = require_permission("audit:log:read")

router = APIRouter(tags=["audit"])


@router.get("/audit-logs", response_model=Page[AuditOut])
def list_audit_logs(
    params: PageParams = Depends(),
    actor_user_id: uuid.UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    context: ScopeContext = Depends(require_audit_read),
    session: Session = Depends(get_db),
) -> Page[AuditOut]:
    page = repository.list_audit_logs(
        session,
        page=params.page,
        page_size=params.page_size,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
    )
    if "audit:log:read_full" not in context.permission_codes:
        page.items = [
            item.model_copy(update={"before_snapshot": None, "after_snapshot": None})
            for item in page.items
        ]
    return page

