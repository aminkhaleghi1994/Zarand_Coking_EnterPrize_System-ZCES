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
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext
from app.core.database import get_db
from app.core.errors import AUTHORIZATION_DENIED, VALIDATION_ERROR, AppError
from app.modules.reports import service
from app.modules.reports.excel import build_report_workbook, export_filename
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
require_export = require_operation("reports:export:excel")

_REPORT_READ_PERMISSIONS: dict[str, str] = {
    "inventory": "reports:inventory:read",
    "requests": "reports:request:read",
    "loans": "reports:loan:read",
    "audit": "audit:log:read",
}


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


@router.get("/reports/export/excel")
def export_report_excel(
    report: str = Query(default=""),
    locale: str = Query(default="en", pattern="^(en|fa)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    warehouse_id: uuid.UUID | None = Query(default=None),
    below_min_only: bool = Query(default=False),
    status: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    year: int | None = Query(default=None, ge=1300, le=1500),
    workplace_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    actor_user_id: uuid.UUID | None = Query(default=None),
    context: ScopeContext = Depends(require_export),
    session: Session = Depends(get_db),
) -> StreamingResponse:
    """Excel export of the current filtered page of a report (FR-006,
    research R4): the same scope+masking-filtered rows the JSON endpoint
    returns, page-bounded (≤ 100 rows)."""
    if report not in _REPORT_READ_PERMISSIONS:
        raise AppError(
            VALIDATION_ERROR,
            f"Unknown report: {report}",
            details={"report": report},
        )
    read_permission = _REPORT_READ_PERMISSIONS[report]
    if read_permission not in context.permission_codes:
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)

    rows: list[Any] = []
    if report == "inventory":
        rows = service.inventory_report(
            session,
            context,
            page=page,
            page_size=page_size,
            warehouse_id=warehouse_id,
            below_min_only=below_min_only,
        ).items
    elif report == "requests":
        rows = service.requests_report(
            session,
            context,
            page=page,
            page_size=page_size,
            status=status,
            date_from=date_from,
            date_to=date_to,
        ).items
    elif report == "loans":
        rows = service.loans_report(
            session, context, year=year, workplace_id=workplace_id
        )
    else:
        rows = service.audit_report(
            session,
            context,
            page=page,
            page_size=page_size,
            action=action,
            entity_type=entity_type,
            actor_user_id=actor_user_id,
            date_from=date_from,
            date_to=date_to,
        ).items

    buffer = build_report_workbook(report, rows, locale)
    filename = export_filename(report, locale)
    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    # HTTP headers are latin-1: the ASCII name always rides `filename`,
    # and a non-ASCII (fa) name travels RFC 5987-encoded in `filename*`.
    disposition = f'attachment; filename="{filename}"'
    if not filename.isascii():
        quoted = filename.encode("utf-8").hex()
        encoded = "".join(
            f"%{quoted[i : i + 2].upper()}" for i in range(0, len(quoted), 2)
        )
        fallback = export_filename(report, "en")
        disposition = (
            f'attachment; filename="{fallback}"; '
            f"filename*=UTF-8''{encoded}"
        )
    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={
            "Content-Disposition": disposition,
            "Content-Type": media_type,
        },
    )
