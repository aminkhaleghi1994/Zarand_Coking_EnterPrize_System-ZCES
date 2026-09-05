"""Reports service (US1-US3): read-only scope-filtered projections over
existing module data via published contracts (constitution VI, research
R3/R5). No storage, no repositories — the source modules apply their own
scope filters.
"""

from sqlalchemy.orm import Session

from app.common.scope import ScopeContext
from app.modules.loan import contracts as loan_contracts
from app.modules.notification import contracts as notification_contracts
from app.modules.reports.schemas import (
    AlertWarehouseCountOut,
    DashboardCountersOut,
    DashboardOut,
)
from app.modules.user import contracts as user_contracts
from app.modules.warehouse import contracts as warehouse_contracts


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
