"""Public contract of the warehouse module for other modules (constitution VI).

Cross-module consumers import ONLY from this file — never from
``models.py``/``repository.py``/services directly. ``apply_fulfillment_issue``
participates in the CALLER's transaction (no commit inside) so the
request-fulfillment service owns its atomic boundary (Phase 5).
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import INSUFFICIENT_STOCK, AppError, not_found
from app.modules.warehouse import repository
from app.modules.warehouse.models import Shelf, Warehouse

__all__ = [
    "ItemView",
    "MovementView",
    "PlacementRef",
    "ShelfContext",
    "apply_fulfillment_issue",
    "get_item",
    "get_placement_for_stock",
    "get_shelf_context",
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
