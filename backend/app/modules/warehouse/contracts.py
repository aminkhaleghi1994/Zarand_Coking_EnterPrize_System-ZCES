"""Public contract of the warehouse module for other modules (constitution VI).

Cross-module consumers import ONLY from this file — never from
``models.py``/``repository.py``/services directly. ``apply_fulfillment_issue``
participates in the CALLER's transaction (no commit inside) so the
request-fulfillment service owns its atomic boundary (Phase 5).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.scope import ScopeContext
from app.core.errors import INSUFFICIENT_STOCK, AppError, not_found
from app.modules.warehouse import repository, request_repository
from app.modules.warehouse.models import Shelf, Warehouse

__all__ = [
    "InventoryReportRow",
    "ItemView",
    "MovementView",
    "PlacementRef",
    "RequestReportRow",
    "ShelfContext",
    "apply_fulfillment_issue",
    "count_catalog_items",
    "count_open_item_requests",
    "count_unresolved_alerts",
    "get_item",
    "get_placement_for_stock",
    "get_shelf_context",
    "item_requests_status_counts",
    "low_stock_alerts_by_warehouse",
    "report_inventory_page",
    "report_request_page",
]


@dataclass(frozen=True)
class ItemView:
    id: uuid.UUID
    name: str
    name_fa: str
    code: str | None
    unit: str
    min_quantity: Decimal
    is_active: bool


@dataclass(frozen=True)
class PlacementRef:
    id: uuid.UUID
    quantity: Decimal


@dataclass(frozen=True)
class ShelfContext:
    shelf_id: uuid.UUID
    warehouse_id: uuid.UUID
    workplace_id: uuid.UUID
    complex_id: uuid.UUID
    company_id: uuid.UUID


@dataclass(frozen=True)
class MovementView:
    id: uuid.UUID
    placement_id: uuid.UUID
    item_id: uuid.UUID
    quantity_delta: Decimal
    resulting_quantity: Decimal


def get_item(session: Session, item_id: uuid.UUID) -> ItemView | None:
    item = repository.get_item(session, item_id)
    if item is None:
        return None
    return ItemView(
        id=item.id,
        name=item.name,
        name_fa=item.name_fa,
        code=item.code,
        unit=item.unit,
        min_quantity=item.min_quantity,
        is_active=item.deleted_at is None,
    )


def get_placement_for_stock(
    session: Session, *, item_id: uuid.UUID, shelf_id: uuid.UUID
) -> PlacementRef | None:
    placement = repository.lock_placement_for_stock(session, shelf_id, item_id)
    if placement is None:
        return None
    return PlacementRef(id=placement.id, quantity=placement.quantity)


def get_shelf_context(session: Session, shelf_id: uuid.UUID) -> ShelfContext | None:
    row = session.execute(
        select(Shelf, Warehouse)
        .join(Warehouse, Shelf.warehouse_id == Warehouse.id)
        .where(Shelf.id == shelf_id)
    ).first()
    if row is None:
        return None
    shelf, warehouse = row
    return ShelfContext(
        shelf_id=shelf.id,
        warehouse_id=warehouse.id,
        workplace_id=warehouse.workplace_id,
        complex_id=warehouse.complex_id,
        company_id=warehouse.company_id,
    )


def apply_fulfillment_issue(
    session: Session,
    *,
    placement_id: uuid.UUID,
    quantity: Decimal,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
) -> MovementView:
    """Atomically decrease a placement for item-request fulfillment (Phase 5).

    Locks the placement row (FOR UPDATE), refuses overdraws with
    ``AppError(INSUFFICIENT_STOCK)``, writes a ``fulfillment`` movement,
    re-evaluates the low-stock alert, and audits — all inside the CALLER's
    transaction (no commit; the caller owns commit/rollback).
    """
    from app.modules.warehouse.service import _evaluate_alert

    bundle = repository.get_placement_bundle(session, placement_id)
    if bundle is None:
        raise not_found("Placement not found")
    placement, item, _shelf, _warehouse = bundle
    locked = repository.lock_placement(session, placement.id)
    if locked is None:
        raise not_found("Placement not found")
    placement = locked

    delta = quantity.quantize(Decimal("0.001"))
    current = placement.quantity.quantize(Decimal("0.001"))
    if delta > current:
        raise AppError(
            INSUFFICIENT_STOCK,
            "Not enough stock on this placement",
            status_code=409,
            details={"available": f"{current:.3f}", "requested": f"{delta:.3f}"},
        )

    resulting = current - delta
    placement.quantity = resulting
    placement.updated_by = actor_user_id
    session.add(placement)
    movement = repository.record_movement(
        session,
        placement_id=placement.id,
        item_id=item.id,
        movement_type="fulfillment",
        quantity_delta=-delta,
        resulting_quantity=resulting,
        reason=reason,
        actor_user_id=actor_user_id,
    )
    _evaluate_alert(session, placement, item, actor_user_id)
    write_audit_contract(
        session,
        movement_id=movement.id,
        placement_id=placement.id,
        before=current,
        after=resulting,
        delta=delta,
        actor_user_id=actor_user_id,
        reason=reason,
    )
    return MovementView(
        id=movement.id,
        placement_id=placement.id,
        item_id=item.id,
        quantity_delta=-delta,
        resulting_quantity=resulting,
    )


def write_audit_contract(
    session: Session,
    *,
    movement_id: uuid.UUID,
    placement_id: uuid.UUID,
    before: Decimal,
    after: Decimal,
    delta: Decimal,
    actor_user_id: uuid.UUID,
    reason: str | None,
) -> None:
    from app.modules.audit.contracts import write_audit

    write_audit(
        session,
        action="STOCK_FULFILLED",
        entity_type="stock_movement",
        entity_id=movement_id,
        actor_user_id=actor_user_id,
        before={
            "placement_id": str(placement_id),
            "quantity_before": f"{before:.3f}",
            "quantity_after": f"{before:.3f}",
        },
        after={
            "placement_id": str(placement_id),
            "quantity_before": f"{before:.3f}",
            "quantity_after": f"{after:.3f}",
            "movement_type": "fulfillment",
            "quantity": f"{delta:.3f}",
            "reason": reason,
        },
        critical=True,
    )


# --- Report/dashboard aggregates (Phase 9, research R3/R5) ---


def count_catalog_items(session: Session) -> int:
    """Active catalog items. The catalog is a global resource: scope gating
    happens at the endpoint (permission + assignment), not per-row."""
    from sqlalchemy import func

    from app.modules.warehouse.models import ItemCatalog

    return int(
        session.scalar(
            select(func.count())
            .select_from(ItemCatalog)
            .where(ItemCatalog.deleted_at.is_(None))
        )
        or 0
    )


def count_open_item_requests(session: Session, context: ScopeContext) -> int:
    """Scope-filtered count of requests still open (pending + approved).

    ItemRequest is immutable history (no soft delete) — no deleted_at filter.
    """
    from sqlalchemy import func

    from app.modules.warehouse.models import ItemRequest, RequestStatus

    scope = request_repository._request_scope_filter(
        context, request_repository.REQUEST_READ_OPERATION
    )
    return int(
        session.scalar(
            select(func.count())
            .select_from(ItemRequest)
            .where(
                scope,
                ItemRequest.status.in_([RequestStatus.PENDING, RequestStatus.APPROVED]),
            )
        )
        or 0
    )


def item_requests_status_counts(
    session: Session, context: ScopeContext
) -> dict[str, int]:
    """Scope-filtered counts by request status (immutable rows — all of them)."""
    from sqlalchemy import func

    from app.modules.warehouse.models import ItemRequest, RequestStatus

    scope = request_repository._request_scope_filter(
        context, request_repository.REQUEST_READ_OPERATION
    )
    rows = session.execute(
        select(ItemRequest.status, func.count())
        .where(scope)
        .group_by(ItemRequest.status)
    ).all()
    counts = {status.value: 0 for status in RequestStatus}
    for status, count in rows:
        counts[status.value] = int(count)
    return counts


def count_unresolved_alerts(session: Session, context: ScopeContext) -> int:
    """Scope-filtered count of unresolved low-stock alerts."""
    from sqlalchemy import func

    from app.modules.warehouse.models import InventoryPlacement, Shelf, StockAlert

    scope = repository._warehouse_scope_filter(context, "warehouse:alert:read")
    return int(
        session.scalar(
            select(func.count())
            .select_from(StockAlert)
            .join(InventoryPlacement, StockAlert.placement_id == InventoryPlacement.id)
            .join(Shelf, InventoryPlacement.shelf_id == Shelf.id)
            .join(Warehouse, Shelf.warehouse_id == Warehouse.id)
            .where(scope, StockAlert.resolved_at.is_(None))
        )
        or 0
    )


def low_stock_alerts_by_warehouse(
    session: Session, context: ScopeContext
) -> list[tuple[str, str, int]]:
    """Unresolved alert counts grouped by warehouse:
    ``(code, name, count)`` sorted by count descending."""
    from sqlalchemy import func

    from app.modules.warehouse.models import InventoryPlacement, Shelf, StockAlert

    scope = repository._warehouse_scope_filter(context, "warehouse:alert:read")
    rows = session.execute(
        select(Warehouse.code, Warehouse.name, func.count())
        .select_from(StockAlert)
        .join(InventoryPlacement, StockAlert.placement_id == InventoryPlacement.id)
        .join(Shelf, InventoryPlacement.shelf_id == Shelf.id)
        .join(Warehouse, Shelf.warehouse_id == Warehouse.id)
        .where(scope, StockAlert.resolved_at.is_(None))
        .group_by(Warehouse.code, Warehouse.name)
        .order_by(func.count().desc())
    ).all()
    return [(code, name, int(count)) for code, name, count in rows]


# --- Operational report pages (Phase 9, research R3) ---


@dataclass(frozen=True)
class InventoryReportRow:
    """Placement projection for the inventory report (US2)."""

    item_id: uuid.UUID
    item_name: str
    item_name_fa: str
    item_code: str | None
    unit: str
    warehouse_code: str
    warehouse_name: str
    shelf_code: str
    quantity: Decimal
    threshold: Decimal
    below_min: bool


def report_inventory_page(
    session: Session,
    context: ScopeContext,
    *,
    page: int,
    page_size: int,
    warehouse_id: uuid.UUID | None = None,
    below_min_only: bool = False,
) -> tuple[list[InventoryReportRow], int]:
    """Scope-filtered placement page (``warehouse:stock:read`` coverage,
    mirroring the placements listing — constitution II)."""
    from sqlalchemy import func

    from app.modules.warehouse.models import InventoryPlacement, ItemCatalog, Shelf

    scope = repository._warehouse_scope_filter(context, "warehouse:stock:read")
    base = (
        select(InventoryPlacement, ItemCatalog, Shelf, Warehouse)
        .join(ItemCatalog, InventoryPlacement.item_id == ItemCatalog.id)
        .join(Shelf, InventoryPlacement.shelf_id == Shelf.id)
        .join(Warehouse, Shelf.warehouse_id == Warehouse.id)
        .where(scope, Warehouse.deleted_at.is_(None))
    )
    if warehouse_id is not None:
        base = base.where(Warehouse.id == warehouse_id)
    if below_min_only:
        base = base.where(InventoryPlacement.quantity < ItemCatalog.min_quantity)

    total = int(
        session.scalar(select(func.count()).select_from(base.subquery())) or 0
    )
    rows = session.execute(
        base.order_by(Warehouse.code, Shelf.code, ItemCatalog.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    projected = [
        InventoryReportRow(
            item_id=item.id,
            item_name=item.name,
            item_name_fa=item.name_fa,
            item_code=item.code,
            unit=item.unit,
            warehouse_code=warehouse.code,
            warehouse_name=warehouse.name,
            shelf_code=shelf.code,
            quantity=placement.quantity,
            threshold=item.min_quantity,
            below_min=placement.quantity < item.min_quantity,
        )
        for placement, item, shelf, warehouse in rows
    ]
    return projected, total


@dataclass(frozen=True)
class RequestReportRow:
    """Item-request projection for the requests report (US2)."""

    id: uuid.UUID
    status: str
    requested_by_email: str | None
    purpose_description: str
    line_count: int
    created_at: datetime
    decided_at: datetime | None
    fulfilled_at: datetime | None


def report_request_page(
    session: Session,
    context: ScopeContext,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[RequestReportRow], int, dict[str, int]]:
    """Scope-OR-ownership filtered request page (mirrors the request
    module's visibility semantics) + status counts over the filtered set."""
    from sqlalchemy import func, or_

    from app.modules.user.models import User
    from app.modules.warehouse.models import ItemRequest, ItemRequestLine, RequestStatus

    caller = uuid.UUID(context.user_id)
    scope = request_repository._request_scope_filter(
        context, request_repository.REQUEST_READ_OPERATION
    )
    visibility = or_(ItemRequest.requested_by == caller, scope)

    base = select(ItemRequest, User.email).join(
        User, ItemRequest.requested_by == User.id, isouter=True
    )
    conditions = [visibility]
    if status:
        conditions.append(ItemRequest.status == RequestStatus(status))
    if date_from is not None:
        conditions.append(ItemRequest.created_at >= date_from)
    if date_to is not None:
        conditions.append(ItemRequest.created_at <= date_to)
    base = base.where(*conditions)

    total = int(
        session.scalar(select(func.count()).select_from(base.subquery())) or 0
    )

    counts_query = (
        select(ItemRequest.status, func.count())
        .where(*conditions)
        .group_by(ItemRequest.status)
    )
    status_counts = {member.value: 0 for member in RequestStatus}
    for row_status, count in session.execute(counts_query).all():
        status_counts[row_status.value] = int(count)

    rows = session.execute(
        base.order_by(ItemRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    line_counts: dict[uuid.UUID, int] = {}
    if rows:
        request_ids = [request.id for request, _email in rows]
        count_rows = session.execute(
            select(ItemRequestLine.request_id, func.count())
            .where(ItemRequestLine.request_id.in_(request_ids))
            .group_by(ItemRequestLine.request_id)
        ).all()
        line_counts = {request_id: int(count) for request_id, count in count_rows}

    projected = [
        RequestReportRow(
            id=request.id,
            status=request.status.value,
            requested_by_email=email,
            purpose_description=request.purpose_description,
            line_count=line_counts.get(request.id, 0),
            created_at=request.created_at,
            decided_at=request.decided_at,
            fulfilled_at=request.fulfilled_at,
        )
        for request, email in rows
    ]
    return projected, total, status_counts
