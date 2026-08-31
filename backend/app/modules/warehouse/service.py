"""Warehouse module services: catalog, structure and stock (plan.md).

Sectioned per aggregate:
- item_service: catalog CRUD with normalization + duplicate rules (US1)
- warehouse_service: warehouses/shelves with scope anchoring (US2)   [added T010+]
- stock_service: placement movements, FOR UPDATE serialization (US3) [added T015+]
- alerts: episode evaluation wired into movements (US4)              [added T025+]
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.scope import ScopeContext, ScopeTarget, can
from app.core.errors import (
    AUTHORIZATION_DENIED,
    BUSINESS_RULE_VIOLATION,
    INSUFFICIENT_STOCK,
    STALE_VERSION,
    AppError,
    duplicate_resource,
    not_found,
    validation_error,
)
from app.modules.audit.contracts import write_audit
from app.modules.user import contracts as user_contracts
from app.modules.warehouse import repository
from app.modules.warehouse.models import InventoryPlacement, ItemCatalog, Shelf, Warehouse
from app.modules.warehouse.schemas import (
    AdjustIn,
    IssueIn,
    ItemCreateIn,
    ItemRetireIn,
    ItemUpdateIn,
    ReceiveIn,
    ShelfCreateIn,
    ShelfRetireIn,
    ShelfUpdateIn,
    WarehouseCreateIn,
    WarehouseRetireIn,
    WarehouseUpdateIn,
    format_quantity,
    quantize_quantity,
)

_ITEM_CREATE = "warehouse:item:create"
_ITEM_UPDATE = "warehouse:item:update"
_ITEM_RETIRE = "warehouse:item:retire"
_WAREHOUSE_CREATE = "warehouse:warehouse:create"
_WAREHOUSE_UPDATE = "warehouse:warehouse:update"
_WAREHOUSE_RETIRE = "warehouse:warehouse:retire"
_SHELF_CREATE = "warehouse:shelf:create"
_SHELF_UPDATE = "warehouse:shelf:update"
_SHELF_RETIRE = "warehouse:shelf:retire"
_STOCK_RECEIVE = "warehouse:stock:receive"
_STOCK_ISSUE = "warehouse:stock:issue"
_STOCK_ADJUST = "warehouse:stock:adjust"
_STOCK_READ = "warehouse:stock:read"


def _require_catalog_scope_any(context: ScopeContext, operation: str) -> None:
    """Catalog writes need the permission (router) plus at least one active
    scope assignment in the warehouse domain — any level (spec FR-019/R5)."""
    if not context.is_active or not any(
        assignment.module == "warehouse" for assignment in context.scopes
    ):
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def _item_snapshot(item: ItemCatalog) -> dict[str, object]:
    return {
        "id": str(item.id),
        "name": item.name,
        "name_fa": item.name_fa,
        "code": item.code,
        "unit": item.unit,
        "min_quantity": format_quantity(item.min_quantity),
        "description": item.description,
        "version": item.version,
    }


def _check_duplicates(
    session: Session,
    *,
    name_norm: str,
    code_norm: str | None,
    exclude_item_id: uuid.UUID | None = None,
) -> None:
    by_name = repository.get_item_by_name_norm(session, name_norm)
    if by_name is not None and by_name.id != exclude_item_id:
        raise duplicate_resource("An active item with this name already exists")
    if code_norm is not None:
        by_code = repository.get_item_by_code_norm(session, code_norm)
        if by_code is not None and by_code.id != exclude_item_id:
            raise duplicate_resource("An active item with this code already exists")


def _flush_catching_duplicate(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise duplicate_resource("An active item with this name or code already exists") from exc


def create_item(session: Session, context: ScopeContext, payload: ItemCreateIn) -> ItemCatalog:
    _require_catalog_scope_any(context, _ITEM_CREATE)
    name = payload.name.strip()
    name_norm = _normalize_name(payload.name)
    code = payload.code
    code_norm = _normalize_name(payload.code) if payload.code else None
    _check_duplicates(session, name_norm=name_norm, code_norm=code_norm)

    item = ItemCatalog(
        name=name,
        name_fa=payload.name_fa.strip(),
        name_norm=name_norm,
        code=code,
        code_norm=code_norm,
        unit=payload.unit,
        min_quantity=quantize_quantity(payload.min_quantity),
        description=payload.description,
        created_by=uuid.UUID(context.user_id),
        updated_by=uuid.UUID(context.user_id),
    )
    session.add(item)
    _flush_catching_duplicate(session)

    write_audit(
        session,
        action="ITEM_CREATED",
        entity_type="item",
        entity_id=item.id,
        actor_user_id=uuid.UUID(context.user_id),
        after=_item_snapshot(item),
        critical=True,
    )
    session.commit()
    return item


def _get_active_item(session: Session, item_id: uuid.UUID) -> ItemCatalog:
    item = repository.get_item(session, item_id)
    if item is None or item.deleted_at is not None:
        raise not_found("Item not found")
    return item


def update_item(
    session: Session, context: ScopeContext, item_id: uuid.UUID, payload: ItemUpdateIn
) -> ItemCatalog:
    _require_catalog_scope_any(context, _ITEM_UPDATE)
    item = _get_active_item(session, item_id)
    if item.version != payload.version:
        raise AppError(
            STALE_VERSION,
            "This record changed since you opened it — refresh and retry",
            status_code=409,
        )

    before = _item_snapshot(item)
    updates = payload.model_dump(exclude={"version"}, exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        item.name = updates["name"].strip()
        item.name_norm = _normalize_name(updates["name"])
    if "name_fa" in updates and updates["name_fa"] is not None:
        item.name_fa = updates["name_fa"].strip()
    if "code" in updates:
        item.code = updates["code"]
        item.code_norm = _normalize_name(updates["code"]) if updates["code"] else None
    if "unit" in updates and updates["unit"] is not None:
        item.unit = updates["unit"]
    if "min_quantity" in updates and updates["min_quantity"] is not None:
        item.min_quantity = quantize_quantity(Decimal(str(updates["min_quantity"])))
    if "description" in updates:
        item.description = updates["description"]
    item.updated_by = uuid.UUID(context.user_id)
    item.version += 1
    session.add(item)
    _check_duplicates(
        session,
        name_norm=item.name_norm,
        code_norm=item.code_norm,
        exclude_item_id=item.id,
    )
    _flush_catching_duplicate(session)

    write_audit(
        session,
        action="ITEM_UPDATED",
        entity_type="item",
        entity_id=item.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after=_item_snapshot(item),
        critical=True,
    )
    session.commit()
    return item


def retire_item(
    session: Session, context: ScopeContext, item_id: uuid.UUID, payload: ItemRetireIn
) -> ItemCatalog:
    _require_catalog_scope_any(context, _ITEM_RETIRE)
    item = repository.get_item(session, item_id)
    if item is None:
        raise not_found("Item not found")

    if item.deleted_at is None:
        if item.version != payload.version:
            raise AppError(
                STALE_VERSION,
                "This record changed since you opened it — refresh and retry",
                status_code=409,
            )
        before = _item_snapshot(item)
        item.deleted_at = datetime.now(UTC)
        item.updated_by = uuid.UUID(context.user_id)
        item.version += 1
        session.add(item)
        write_audit(
            session,
            action="ITEM_RETIRED",
            entity_type="item",
            entity_id=item.id,
            actor_user_id=uuid.UUID(context.user_id),
            before=before,
            after=_item_snapshot(item),
            critical=True,
        )
    else:
        write_audit(
            session,
            action="ITEM_RETIRED",
            entity_type="item",
            entity_id=item.id,
            actor_user_id=uuid.UUID(context.user_id),
            after=_item_snapshot(item),
            critical=True,
        )
    session.commit()
    return item


# --- warehouse_service (US2): warehouses & shelves ---


def _warehouse_snapshot(warehouse: Warehouse) -> dict[str, object]:
    return {
        "id": str(warehouse.id),
        "workplace_id": str(warehouse.workplace_id),
        "code": warehouse.code,
        "name": warehouse.name,
        "name_fa": warehouse.name_fa,
        "version": warehouse.version,
    }


def _shelf_snapshot(shelf: Shelf) -> dict[str, object]:
    return {
        "id": str(shelf.id),
        "warehouse_id": str(shelf.warehouse_id),
        "code": shelf.code,
        "name": shelf.name,
        "name_fa": shelf.name_fa,
        "version": shelf.version,
    }


def _blocking_detail(
    session: Session, *, warehouse_id: uuid.UUID | None = None, shelf_id: uuid.UUID | None = None
) -> list[dict[str, str]]:
    blockings = repository.list_blocking_placements(
        session, warehouse_id=warehouse_id, shelf_id=shelf_id
    )
    return [
        {
            "placement_id": str(placement.id),
            "item_id": str(placement.item_id),
            "quantity": format_quantity(placement.quantity),
        }
        for placement in blockings
    ]


def _raise_if_blocked(
    session: Session, *, warehouse_id: uuid.UUID | None = None, shelf_id: uuid.UUID | None = None
) -> None:
    blockings = _blocking_detail(session, warehouse_id=warehouse_id, shelf_id=shelf_id)
    if blockings:
        raise AppError(
            BUSINESS_RULE_VIOLATION,
            "Retirement is blocked while stock remains on the shelves",
            status_code=422,
            details={"blocking_placements": blockings},
        )


def create_warehouse(
    session: Session, context: ScopeContext, payload: WarehouseCreateIn
) -> Warehouse:
    parents = user_contracts.get_workplace_with_parents(session, payload.workplace_id)
    if parents is None:
        raise not_found("Workplace not found")
    if not parents.is_active:
        raise validation_error("Workplace is deactivated")
    if not can(
        context,
        _WAREHOUSE_CREATE,
        ScopeTarget(complex_id=str(parents.complex_id), workplace_id=str(parents.id)),
    ):
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
    if repository.get_warehouse_by_code(session, payload.code) is not None:
        raise duplicate_resource("An active warehouse with this code already exists")

    warehouse = Warehouse(
        workplace_id=parents.id,
        company_id=parents.company_id,
        complex_id=parents.complex_id,
        code=payload.code,
        name=payload.name,
        name_fa=payload.name_fa,
        created_by=uuid.UUID(context.user_id),
        updated_by=uuid.UUID(context.user_id),
    )
    session.add(warehouse)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise duplicate_resource("An active warehouse with this code already exists") from exc

    write_audit(
        session,
        action="WAREHOUSE_CREATED",
        entity_type="warehouse",
        entity_id=warehouse.id,
        actor_user_id=uuid.UUID(context.user_id),
        after=_warehouse_snapshot(warehouse),
        critical=True,
    )
    session.commit()
    return warehouse


def update_warehouse(
    session: Session, context: ScopeContext, warehouse_id: uuid.UUID, payload: WarehouseUpdateIn
) -> Warehouse:
    warehouse = repository.get_warehouse_in_scope(session, warehouse_id, context, _WAREHOUSE_UPDATE)
    if warehouse is None or warehouse.deleted_at is not None:
        raise not_found("Warehouse not found")
    if warehouse.version != payload.version:
        raise AppError(
            STALE_VERSION,
            "This record changed since you opened it — refresh and retry",
            status_code=409,
        )
    before = _warehouse_snapshot(warehouse)
    updates = payload.model_dump(exclude={"version"}, exclude_unset=True)
    if "code" in updates and updates["code"] is not None:
        warehouse.code = updates["code"]
    if "name" in updates and updates["name"] is not None:
        warehouse.name = updates["name"]
    if "name_fa" in updates and updates["name_fa"] is not None:
        warehouse.name_fa = updates["name_fa"]
    warehouse.updated_by = uuid.UUID(context.user_id)
    warehouse.version += 1
    session.add(warehouse)
    if repository.get_warehouse_by_code(session, warehouse.code) not in (None, warehouse):
        session.rollback()
        raise duplicate_resource("An active warehouse with this code already exists")
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise duplicate_resource("An active warehouse with this code already exists") from exc

    write_audit(
        session,
        action="WAREHOUSE_UPDATED",
        entity_type="warehouse",
        entity_id=warehouse.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after=_warehouse_snapshot(warehouse),
        critical=True,
    )
    session.commit()
    return warehouse


def retire_warehouse(
    session: Session, context: ScopeContext, warehouse_id: uuid.UUID, payload: WarehouseRetireIn
) -> Warehouse:
    warehouse = repository.get_warehouse_in_scope(session, warehouse_id, context, _WAREHOUSE_RETIRE)
    if warehouse is None:
        raise not_found("Warehouse not found")
    if warehouse.deleted_at is None:
        if warehouse.version != payload.version:
            raise AppError(
                STALE_VERSION,
                "This record changed since you opened it — refresh and retry",
                status_code=409,
            )
        _raise_if_blocked(session, warehouse_id=warehouse.id)
        before = _warehouse_snapshot(warehouse)
        warehouse.deleted_at = datetime.now(UTC)
        warehouse.updated_by = uuid.UUID(context.user_id)
        warehouse.version += 1
        session.add(warehouse)
        write_audit(
            session,
            action="WAREHOUSE_RETIRED",
            entity_type="warehouse",
            entity_id=warehouse.id,
            actor_user_id=uuid.UUID(context.user_id),
            before=before,
            after=_warehouse_snapshot(warehouse),
            critical=True,
        )
    else:
        write_audit(
            session,
            action="WAREHOUSE_RETIRED",
            entity_type="warehouse",
            entity_id=warehouse.id,
            actor_user_id=uuid.UUID(context.user_id),
            after=_warehouse_snapshot(warehouse),
            critical=True,
        )
    session.commit()
    return warehouse


def create_shelf(
    session: Session, context: ScopeContext, warehouse_id: uuid.UUID, payload: ShelfCreateIn
) -> Shelf:
    warehouse = repository.get_warehouse_in_scope(session, warehouse_id, context, _SHELF_CREATE)
    if warehouse is None or warehouse.deleted_at is not None:
        raise not_found("Warehouse not found")
    if repository.get_shelf_by_code(session, warehouse.id, payload.code) is not None:
        raise duplicate_resource("An active shelf with this code already exists in this warehouse")

    shelf = Shelf(
        warehouse_id=warehouse.id,
        code=payload.code,
        name=payload.name,
        name_fa=payload.name_fa,
        created_by=uuid.UUID(context.user_id),
        updated_by=uuid.UUID(context.user_id),
    )
    session.add(shelf)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise duplicate_resource(
            "An active shelf with this code already exists in this warehouse"
        ) from exc

    write_audit(
        session,
        action="SHELF_CREATED",
        entity_type="shelf",
        entity_id=shelf.id,
        actor_user_id=uuid.UUID(context.user_id),
        after=_shelf_snapshot(shelf),
        critical=True,
    )
    session.commit()
    return shelf


def update_shelf(
    session: Session, context: ScopeContext, shelf_id: uuid.UUID, payload: ShelfUpdateIn
) -> Shelf:
    shelf = repository.get_shelf_in_scope(session, shelf_id, context, _SHELF_UPDATE)
    if shelf is None or shelf.deleted_at is not None:
        raise not_found("Shelf not found")
    if shelf.version != payload.version:
        raise AppError(
            STALE_VERSION,
            "This record changed since you opened it — refresh and retry",
            status_code=409,
        )
    before = _shelf_snapshot(shelf)
    updates = payload.model_dump(exclude={"version"}, exclude_unset=True)
    if "code" in updates and updates["code"] is not None:
        shelf.code = updates["code"]
    if "name" in updates:
        shelf.name = updates["name"]
    if "name_fa" in updates:
        shelf.name_fa = updates["name_fa"]
    shelf.updated_by = uuid.UUID(context.user_id)
    shelf.version += 1
    session.add(shelf)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise duplicate_resource(
            "An active shelf with this code already exists in this warehouse"
        ) from exc

    write_audit(
        session,
        action="SHELF_UPDATED",
        entity_type="shelf",
        entity_id=shelf.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after=_shelf_snapshot(shelf),
        critical=True,
    )
    session.commit()
    return shelf


def retire_shelf(
    session: Session, context: ScopeContext, shelf_id: uuid.UUID, payload: ShelfRetireIn
) -> Shelf:
    shelf = repository.get_shelf_in_scope(session, shelf_id, context, _SHELF_RETIRE)
    if shelf is None:
        raise not_found("Shelf not found")
    if shelf.deleted_at is None:
        if shelf.version != payload.version:
            raise AppError(
                STALE_VERSION,
                "This record changed since you opened it — refresh and retry",
                status_code=409,
            )
        _raise_if_blocked(session, shelf_id=shelf.id)
        before = _shelf_snapshot(shelf)
        shelf.deleted_at = datetime.now(UTC)
        shelf.updated_by = uuid.UUID(context.user_id)
        shelf.version += 1
        session.add(shelf)
        write_audit(
            session,
            action="SHELF_RETIRED",
            entity_type="shelf",
            entity_id=shelf.id,
            actor_user_id=uuid.UUID(context.user_id),
            before=before,
            after=_shelf_snapshot(shelf),
            critical=True,
        )
    else:
        write_audit(
            session,
            action="SHELF_RETIRED",
            entity_type="shelf",
            entity_id=shelf.id,
            actor_user_id=uuid.UUID(context.user_id),
            after=_shelf_snapshot(shelf),
            critical=True,
        )
    session.commit()
    return shelf


# --- stock_service (US3): placements & movement ledger ---


def _require_stock_target(context: ScopeContext, operation: str, warehouse: Warehouse) -> None:
    if not can(
        context,
        operation,
        ScopeTarget(complex_id=str(warehouse.complex_id), workplace_id=str(warehouse.workplace_id)),
    ):
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)


def _load_stock_bundle(
    session: Session, context: ScopeContext, placement_id: uuid.UUID, operation: str
) -> tuple[InventoryPlacement, ItemCatalog, Shelf, Warehouse]:
    bundle = repository.get_placement_bundle(session, placement_id)
    if bundle is None:
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
    placement, item, shelf, warehouse = bundle
    if shelf.deleted_at is not None or item.deleted_at is not None:
        raise not_found("Placement not found")
    _require_stock_target(context, operation, warehouse)
    return placement, item, shelf, warehouse


def _placement_movement_snapshot(
    placement: InventoryPlacement, before_quantity: Decimal, after_quantity: Decimal
) -> dict[str, object]:
    return {
        "placement_id": str(placement.id),
        "item_id": str(placement.item_id),
        "quantity_before": format_quantity(before_quantity),
        "quantity_after": format_quantity(after_quantity),
    }


def _evaluate_alert(session: Session, placement: InventoryPlacement, item: ItemCatalog) -> None:
    """US4 wires alert evaluation here (T026); kept as a hook point."""


def receive_stock(
    session: Session, context: ScopeContext, payload: ReceiveIn
) -> tuple[InventoryPlacement, ItemCatalog, Shelf, Warehouse]:
    item = repository.get_item(session, payload.item_id)
    if item is None or item.deleted_at is not None:
        raise not_found("Item not found")
    shelf = repository.get_shelf(session, payload.shelf_id)
    if shelf is None or shelf.deleted_at is not None:
        raise not_found("Shelf not found")
    warehouse = repository.get_warehouse(session, shelf.warehouse_id)
    if warehouse is None:
        raise not_found("Warehouse not found")
    _require_stock_target(context, _STOCK_RECEIVE, warehouse)

    quantity = quantize_quantity(payload.quantity)
    placement = repository.lock_placement_for_stock(session, shelf.id, item.id)
    if placement is None:
        try:
            with session.begin_nested():
                placement = InventoryPlacement(
                    shelf_id=shelf.id,
                    item_id=item.id,
                    quantity=Decimal("0"),
                    created_by=uuid.UUID(context.user_id),
                    updated_by=uuid.UUID(context.user_id),
                )
                session.add(placement)
                session.flush()
        except IntegrityError:
            placement = repository.lock_placement_for_stock(session, shelf.id, item.id)
            if placement is None:
                raise

    resulting = quantize_quantity(placement.quantity + quantity)
    placement.quantity = resulting
    placement.updated_by = uuid.UUID(context.user_id)
    session.add(placement)
    movement = repository.record_movement(
        session,
        placement_id=placement.id,
        item_id=item.id,
        movement_type="receive",
        quantity_delta=quantity,
        resulting_quantity=resulting,
        reason=payload.reason,
        actor_user_id=uuid.UUID(context.user_id),
    )
    _evaluate_alert(session, placement, item)
    write_audit(
        session,
        action="STOCK_RECEIVED",
        entity_type="stock_movement",
        entity_id=movement.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=_placement_movement_snapshot(placement, resulting - quantity, resulting - quantity),
        after={
            **_placement_movement_snapshot(placement, resulting - quantity, resulting),
            "movement_id": str(movement.id),
            "movement_type": "receive",
            "quantity": format_quantity(quantity),
            "reason": payload.reason,
        },
        critical=True,
    )
    session.commit()
    return placement, item, shelf, warehouse


def issue_stock(
    session: Session, context: ScopeContext, payload: IssueIn
) -> tuple[InventoryPlacement, ItemCatalog, Shelf, Warehouse]:
    placement, item, shelf, warehouse = _load_stock_bundle(
        session, context, payload.placement_id, _STOCK_ISSUE
    )
    placement = repository.lock_placement(session, placement.id)
    assert placement is not None
    quantity = quantize_quantity(payload.quantity)
    current = quantize_quantity(placement.quantity)
    if quantity > current:
        raise AppError(
            INSUFFICIENT_STOCK,
            "Not enough stock on this placement",
            status_code=409,
            details={"available": format_quantity(current), "requested": format_quantity(quantity)},
        )

    resulting = quantize_quantity(current - quantity)
    placement.quantity = resulting
    placement.updated_by = uuid.UUID(context.user_id)
    session.add(placement)
    movement = repository.record_movement(
        session,
        placement_id=placement.id,
        item_id=item.id,
        movement_type="issue",
        quantity_delta=-quantity,
        resulting_quantity=resulting,
        reason=payload.reason,
        actor_user_id=uuid.UUID(context.user_id),
    )
    _evaluate_alert(session, placement, item)
    write_audit(
        session,
        action="STOCK_ISSUED",
        entity_type="stock_movement",
        entity_id=movement.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=_placement_movement_snapshot(placement, current, current),
        after={
            **_placement_movement_snapshot(placement, current, resulting),
            "movement_id": str(movement.id),
            "movement_type": "issue",
            "quantity": format_quantity(quantity),
            "reason": payload.reason,
        },
        critical=True,
    )
    session.commit()
    return placement, item, shelf, warehouse


def adjust_stock(
    session: Session, context: ScopeContext, payload: AdjustIn
) -> tuple[InventoryPlacement, ItemCatalog, Shelf, Warehouse]:
    placement, item, shelf, warehouse = _load_stock_bundle(
        session, context, payload.placement_id, _STOCK_ADJUST
    )
    placement = repository.lock_placement(session, placement.id)
    assert placement is not None
    target = quantize_quantity(payload.quantity)
    current = quantize_quantity(placement.quantity)
    delta = quantize_quantity(target - current)
    if delta == 0:
        raise validation_error("Adjusted quantity equals the current stock")

    placement.quantity = target
    placement.updated_by = uuid.UUID(context.user_id)
    session.add(placement)
    movement = repository.record_movement(
        session,
        placement_id=placement.id,
        item_id=item.id,
        movement_type="adjust",
        quantity_delta=delta,
        resulting_quantity=target,
        reason=payload.reason,
        actor_user_id=uuid.UUID(context.user_id),
    )
    _evaluate_alert(session, placement, item)
    write_audit(
        session,
        action="STOCK_ADJUSTED",
        entity_type="stock_movement",
        entity_id=movement.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=_placement_movement_snapshot(placement, current, current),
        after={
            **_placement_movement_snapshot(placement, current, target),
            "movement_id": str(movement.id),
            "movement_type": "adjust",
            "quantity": format_quantity(delta),
            "reason": payload.reason,
        },
        critical=True,
    )
    session.commit()
    return placement, item, shelf, warehouse


__all__ = [
    "adjust_stock",
    "create_item",
    "create_shelf",
    "create_warehouse",
    "issue_stock",
    "receive_stock",
    "retire_item",
    "retire_shelf",
    "retire_warehouse",
    "update_item",
    "update_shelf",
    "update_warehouse",
]
