"""Reports module schemas (contracts/reports-settings-endpoints.md).

Read-only projections — the reports module owns no storage; DTOs mirror
the contract shapes composed from module contracts.
"""

from datetime import datetime

from pydantic import BaseModel

from app.common.pagination import Page


class DashboardCountersOut(BaseModel):
    active_employees: int
    catalog_items: int
    open_item_requests: int
    active_loans: int
    unresolved_low_stock_alerts: int
    delivered_notifications: int


class AlertWarehouseCountOut(BaseModel):
    warehouse_code: str
    warehouse_name: str
    count: int


class DashboardOut(BaseModel):
    counters: DashboardCountersOut
    item_requests_by_status: dict[str, int]
    loans_by_status: dict[str, int]
    low_stock_alerts_by_warehouse: list[AlertWarehouseCountOut]


class InventoryReportRowOut(BaseModel):
    item_id: str
    item_name: str
    item_name_fa: str
    item_code: str | None
    unit: str
    warehouse_code: str
    warehouse_name: str
    shelf_code: str
    quantity: str
    threshold: str
    below_min: bool


class RequestReportRowOut(BaseModel):
    id: str
    status: str
    requested_by_email: str | None
    purpose_description: str
    line_count: int
    created_at: datetime
    decided_at: datetime | None
    fulfilled_at: datetime | None


class RequestReportPage(Page[RequestReportRowOut]):
    """List envelope + status counts over the filtered set (additive field,
    present on every page)."""

    status_counts: dict[str, int] = {}


class LoanReportRowOut(BaseModel):
    workplace_id: str
    workplace_code: str
    workplace_name: str
    workplace_name_fa: str
    year: int
    requests_total: int
    requests_pending: int
    requests_active: int
    requests_settled: int
    requests_cancelled: int
    active_loan_commitment: str
    active_guarantee_commitment: str
    policy_max_loan: str
    policy_max_guarantee: str


class AuditReportRowOut(BaseModel):
    id: str
    actor_user_id: str | None
    action: str
    entity_type: str
    entity_id: str | None
    before_snapshot: dict[str, object] | None
    after_snapshot: dict[str, object] | None
    trace_id: str | None
    created_at: datetime
