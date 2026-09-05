"""Reports service (US1-US3): read-only scope-filtered projections over
existing module data via published contracts (constitution VI, research
R3/R5). No storage, no repositories — the source modules apply their own
scope filters.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext
from app.modules.audit import contracts as audit_contracts
from app.modules.loan import contracts as loan_contracts
from app.modules.notification import contracts as notification_contracts
from app.modules.reports.schemas import (
    AlertWarehouseCountOut,
    AuditReportRowOut,
    DashboardCountersOut,
    DashboardOut,
    InventoryReportRowOut,
    LoanReportRowOut,
    RequestReportPage,
    RequestReportRowOut,
)
from app.modules.user import contracts as user_contracts
from app.modules.warehouse import contracts as warehouse_contracts

_REPORT_PERMISSION_PREFIX = "reports:"


def _mask_audit_row(row, include_snapshots: bool) -> AuditReportRowOut:  # type: ignore[no-untyped-def]
    return AuditReportRowOut(
        id=str(row.id),
        actor_user_id=str(row.actor_user_id) if row.actor_user_id else None,
        action=row.action,
        entity_type=row.entity_type,
        entity_id=str(row.entity_id) if row.entity_id else None,
        before_snapshot=row.before_snapshot if include_snapshots else None,
        after_snapshot=row.after_snapshot if include_snapshots else None,
        trace_id=row.trace_id,
        created_at=row.created_at,
    )


def dashboard(session: Session, context: ScopeContext) -> DashboardOut:
    counters = DashboardCountersOut(
        active_employees=user_contracts.count_active_employees(session, context),
        catalog_items=warehouse_contracts.count_catalog_items(session),
        open_item_requests=warehouse_contracts.count_open_item_requests(
            session, context
        ),
        active_loans=loan_contracts.count_active_loans(session, context),
        unresolved_low_stock_alerts=warehouse_contracts.count_unresolved_alerts(
            session, context
        ),
        delivered_notifications=notification_contracts.count_delivered_notifications(
            session
        ),
    )
    return DashboardOut(
        counters=counters,
        item_requests_by_status=warehouse_contracts.item_requests_status_counts(
            session, context
        ),
        loans_by_status=loan_contracts.loans_status_counts(session, context),
        low_stock_alerts_by_warehouse=[
            AlertWarehouseCountOut(warehouse_code=code, warehouse_name=name, count=count)
            for code, name, count in warehouse_contracts.low_stock_alerts_by_warehouse(
                session, context
            )
        ],
    )


def inventory_report(
    session: Session,
    context: ScopeContext,
    *,
    page: int,
    page_size: int,
    warehouse_id: uuid.UUID | None = None,
    below_min_only: bool = False,
) -> Page[InventoryReportRowOut]:
    rows, total = warehouse_contracts.report_inventory_page(
        session,
        context,
        page=page,
        page_size=page_size,
        warehouse_id=warehouse_id,
        below_min_only=below_min_only,
    )
    return Page(
        items=[
            InventoryReportRowOut(
                item_id=str(row.item_id),
                item_name=row.item_name,
                item_name_fa=row.item_name_fa,
                item_code=row.item_code,
                unit=row.unit,
                warehouse_code=row.warehouse_code,
                warehouse_name=row.warehouse_name,
                shelf_code=row.shelf_code,
                quantity=f"{row.quantity:.3f}",
                threshold=f"{row.threshold:.3f}",
                below_min=row.below_min,
            )
            for row in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


def requests_report(
    session: Session,
    context: ScopeContext,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> RequestReportPage:
    rows, total, status_counts = warehouse_contracts.report_request_page(
        session,
        context,
        page=page,
        page_size=page_size,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    return RequestReportPage(
        items=[
            RequestReportRowOut(
                id=str(row.id),
                status=row.status,
                requested_by_email=row.requested_by_email,
                purpose_description=row.purpose_description,
                line_count=row.line_count,
                created_at=row.created_at,
                decided_at=row.decided_at,
                fulfilled_at=row.fulfilled_at,
            )
            for row in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        status_counts=status_counts,
    )


def loans_report(
    session: Session,
    context: ScopeContext,
    *,
    year: int | None = None,
    workplace_id: uuid.UUID | None = None,
) -> list[LoanReportRowOut]:
    rows = loan_contracts.report_loan_rows(
        session, context, year=year, workplace_id=workplace_id
    )
    return [
        LoanReportRowOut(
            workplace_id=str(row.workplace_id),
            workplace_code=row.workplace_code,
            workplace_name=row.workplace_name,
            workplace_name_fa=row.workplace_name_fa,
            year=row.year,
            requests_total=row.requests_total,
            requests_pending=row.requests_pending,
            requests_active=row.requests_active,
            requests_settled=row.requests_settled,
            requests_cancelled=row.requests_cancelled,
            active_loan_commitment=f"{row.active_loan_commitment:.2f}",
            active_guarantee_commitment=f"{row.active_guarantee_commitment:.2f}",
            policy_max_loan=(
                f"{row.policy_max_loan:.2f}" if row.policy_max_loan is not None else ""
            ),
            policy_max_guarantee=(
                f"{row.policy_max_guarantee:.2f}"
                if row.policy_max_guarantee is not None
                else ""
            ),
        )
        for row in rows
    ]


def audit_report(
    session: Session,
    context: ScopeContext,
    *,
    page: int,
    page_size: int,
    action: str | None = None,
    entity_type: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Page[AuditReportRowOut]:
    audit_page = audit_contracts.report_audit_page(
        session,
        page=page,
        page_size=page_size,
        action=action,
        entity_type=entity_type,
        actor_user_id=actor_user_id,
        date_from=date_from,
        date_to=date_to,
    )
    include_snapshots = "audit:log:read_full" in context.permission_codes
    return Page(
        items=[
            _mask_audit_row(row, include_snapshots) for row in audit_page.items
        ],
        page=page,
        page_size=page_size,
        total=audit_page.total,
    )
