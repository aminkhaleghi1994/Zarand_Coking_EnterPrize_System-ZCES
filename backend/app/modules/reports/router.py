"""Reports endpoints (contracts/reports-settings-endpoints.md).

Scope-filtered surface: `require_operation` gates the permission code and
every composed query applies the owning module's scope filter via
`allowed_units` (the established warehouse pattern — a caller with the
permission but only workplace coverage sees workplace-bounded numbers,
constitution II).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.scope import ScopeContext
from app.core.database import get_db
from app.modules.reports import service
from app.modules.reports.schemas import DashboardOut
from app.modules.user.dependencies import require_operation

router = APIRouter(tags=["reports"])

require_dashboard_read = require_operation("reports:dashboard:read")


@router.get("/reports/dashboard", response_model=DashboardOut)
def get_dashboard(
    context: ScopeContext = Depends(require_dashboard_read),
    session: Session = Depends(get_db),
) -> DashboardOut:
    return service.dashboard(session, context)
