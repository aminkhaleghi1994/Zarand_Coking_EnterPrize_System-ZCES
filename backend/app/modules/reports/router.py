"""Reports endpoints (contracts/reports-settings-endpoints.md).

Scope-filtered surface: `require_operation` gates the permission code and
every composed query applies the owning module's scope filter via
`allowed_units` (the established warehouse pattern — a caller with the
permission but only workplace coverage sees workplace-bounded numbers,
constitution II). The audit report reuses the audit permissions
(`audit:log:read` + `audit:log:read_full` for snapshot contents).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext
from app.core.database import get_db
from app.modules.reports import service
from app.modules.reports.schemas import (
    AuditReportRowOut,
    DashboardOut,
    InventoryReportRowOut,
    LoanReportRowOut,
    RequestReportPage,
)
from app.modules.user.dependencies import load_context, require_operation
from app.modules.user.schemas import PageParams

router = APIRouter(tags=["reports"])

require_dashboard_read = require_operation("reports:dashboard:read")
require_inventory_read = require_operation("reports:inventory:read")
require_request_report_read = require_operation("reports:request:read")
require_loan_report_read = require_operation("reports:loan:read")


@router.get("/reports/dashboard", response_model=DashboardOut)
def get_dashboard(
    context: ScopeContext = Depends(require_dashboard_read),
    session: Session = Depends(get_db),
) -> DashboardOut:
    return service.dashboard(session, context)


@router.get("/reports/inventory", response_model=Page[InventoryReportRowOut])
def get_inventory_report(
    params: PageParams = Depends(),
    warehouse_id: uuid.UUID | None = Query(default=None),
    below_min_only: bool = Query(default=False),
    context: ScopeContext = Depends(require_inventory_read),
    session: Session = Depends(get_db),
) -> Page[InventoryReportRowOut]:
    return service.inventory_report(
        session,
        context,
        page=params.page,
        page_size=params.page_size,
        warehouse_id=warehouse_id,
        below_min_only=below_min_only,
    )


@router.get("/reports/requests", response_model=RequestReportPage)
def get_requests_report(
    params: PageParams = Depends(),
    status: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    context: ScopeContext = Depends(require_request_report_read),
    session: Session = Depends(get_db),
) -> RequestReportPage:
    return service.requests_report(
        session,
        context,
        page=params.page,
        page_size=params.page_size,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/reports/loans", response_model=list[LoanReportRowOut])
def get_loans_report(
    year: int | None = Query(default=None, ge=1300, le=1500),
    workplace_id: uuid.UUID | None = Query(default=None),
    context: ScopeContext = Depends(require_loan_report_read),
    session: Session = Depends(get_db),
) -> list[LoanReportRowOut]:
    return service.loans_report(
        session, context, year=year, workplace_id=workplace_id
    )


@router.get("/reports/audit", response_model=Page[AuditReportRowOut])
def get_audit_report(
    params: PageParams = Depends(),
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    actor_user_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    context: ScopeContext = Depends(load_context),
    session: Session = Depends(get_db),
) -> Page[AuditReportRowOut]:
    if "audit:log:read" not in context.permission_codes:
        from app.core.errors import AUTHORIZATION_DENIED, AppError

        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
    return service.audit_report(
        session,
        context,
        page=params.page,
        page_size=params.page_size,
        action=action,
        entity_type=entity_type,
        actor_user_id=actor_user_id,
        date_from=date_from,
        date_to=date_to,
    )
