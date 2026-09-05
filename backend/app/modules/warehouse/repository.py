"""Warehouse module queries. Every scope-aware function takes a ScopeContext
and applies the mandatory scope filter (constitution II) — a query without one
is a bug. Exception per spec FR-019/research R5: catalog reads are
company-wide reference data gated by permission alone."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy import false as sa_false
from sqlalchemy import true as sa_true
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext, allowed_units
from app.core.errors import AUTHORIZATION_DENIED, AppError
from app.modules.user.schemas import PageParams
from app.modules.warehouse.models import (
    InventoryPlacement,
    ItemCatalog,
    Shelf,
    StockAlert,
    StockMovement,
    Warehouse,
)
from app.modules.warehouse.schemas import (
    AlertOut,
    ItemOut,
    MovementOut,
    PlacementOut,
    ShelfOut,
    WarehouseOut,
    format_quantity,
)

ITEM_READ_OPERATION = "warehouse:item:read"


def to_item_out(item: ItemCatalog) -> ItemOut:
    return ItemOut(
        id=item.id,
        version=item.version,
        name=item.name,
        name_fa=item.name_fa,
        code=item.code,
        unit=item.unit,
        min_quantity=format_quantity(item.min_quantity),
        description=item.description,
        is_active=item.deleted_at is None,
        created_at=item.created_at,
    )


def _item_search_filter(search: str | None) -> ColumnElement[bool]:
    if not search:
        return sa_true()
    pattern = f"%{search.strip()}%"
    return or_(
        ItemCatalog.name_norm.ilike(pattern),
        ItemCatalog.name_fa.ilike(pattern),
        ItemCatalog.code_norm.ilike(pattern),
    )


def search_items(
    session: Session, params: PageParams, *, search: str | None = None
) -> Page[ItemOut]:
    base = select(ItemCatalog).where(ItemCatalog.deleted_at.is_(None), _item_search_filter(search))
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.scalars(
        base.order_by(ItemCatalog.name_norm)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    return Page[ItemOut](
        items=[to_item_out(item) for item in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


def get_item(session: Session, item_id: UUID) -> ItemCatalog | None:
    return session.scalar(select(ItemCatalog).where(ItemCatalog.id == item_id))


def get_item_by_name_norm(session: Session, name_norm: str) -> ItemCatalog | None:
    """Duplicate lookup among active rows (soft-deleted rows never block)."""
    return session.scalar(
        select(ItemCatalog).where(
            ItemCatalog.name_norm == name_norm, ItemCatalog.deleted_at.is_(None)
        )
    )


def get_item_by_code_norm(session: Session, code_norm: str) -> ItemCatalog | None:
    return session.scalar(
        select(ItemCatalog).where(
            ItemCatalog.code_norm == code_norm, ItemCatalog.deleted_at.is_(None)
        )
    )


# --- Warehouses & shelves (US2) ---


def to_warehouse_out(warehouse: Warehouse) -> WarehouseOut:
    return WarehouseOut(
        id=warehouse.id,
        version=warehouse.version,
        workplace_id=warehouse.workplace_id,
        code=warehouse.code,
        name=warehouse.name,
        name_fa=warehouse.name_fa,
        is_active=warehouse.deleted_at is None,
        created_at=warehouse.created_at,
    )


def to_shelf_out(shelf: Shelf) -> ShelfOut:
    return ShelfOut(
        id=shelf.id,
        version=shelf.version,
        warehouse_id=shelf.warehouse_id,
        code=shelf.code,
        name=shelf.name,
        name_fa=shelf.name_fa,
        is_active=shelf.deleted_at is None,
        created_at=shelf.created_at,
    )


def _warehouse_scope_filter(context: ScopeContext, operation: str) -> ColumnElement[bool]:
    """Scope filter over warehouses via their org columns; deny-all otherwise."""
    units = allowed_units(context, operation)
    if units.global_access:
        return sa_true()
    conditions = []
    if units.complex_ids:
        conditions.append(Warehouse.complex_id.in_(units.complex_ids))
    if units.workplace_ids:
        conditions.append(Warehouse.workplace_id.in_(units.workplace_ids))
    if not conditions:
        return sa_false()
    return or_(*conditions)


def list_warehouses(
    session: Session,
    context: ScopeContext,
    params: PageParams,
    *,
    operation: str = "warehouse:warehouse:read",
    workplace_id: UUID | None = None,
) -> Page[WarehouseOut]:
    base = select(Warehouse).where(
        _warehouse_scope_filter(context, operation),
        Warehouse.deleted_at.is_(None),
    )
    if workplace_id is not None:
        base = base.where(Warehouse.workplace_id == workplace_id)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.scalars(
        base.order_by(Warehouse.code)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    return Page[WarehouseOut](
        items=[to_warehouse_out(warehouse) for warehouse in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


def get_warehouse(session: Session, warehouse_id: UUID) -> Warehouse | None:
    return session.scalar(select(Warehouse).where(Warehouse.id == warehouse_id))


def get_warehouse_in_scope(
    session: Session, warehouse_id: UUID, context: ScopeContext, operation: str
) -> Warehouse | None:
    """Scope-checked read without existence leak (FR-020).

    Global coverage returns the row or None (caller maps None to 404); any
    non-global coverage makes missing AND out-of-scope indistinguishable
    (AUTHORIZATION_DENIED).
    """
    warehouse = get_warehouse(session, warehouse_id)
    units = allowed_units(context, operation)
    if units.global_access:
        return warehouse
    if warehouse is None:
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
    if (
        str(warehouse.workplace_id) in units.workplace_ids
        or str(warehouse.complex_id) in units.complex_ids
    ):
        return warehouse
    raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)


def get_warehouse_by_code(session: Session, code: str) -> Warehouse | None:
    return session.scalar(
        select(Warehouse).where(Warehouse.code == code, Warehouse.deleted_at.is_(None))
    )


def list_shelves(
    session: Session,
    context: ScopeContext,
    params: PageParams,
    *,
    warehouse_id: UUID,
    operation: str = "warehouse:shelf:read",
) -> Page[ShelfOut]:
    base = (
        select(Shelf)
        .join(Warehouse, Shelf.warehouse_id == Warehouse.id)
        .where(
            _warehouse_scope_filter(context, operation),
            Shelf.deleted_at.is_(None),
            Shelf.warehouse_id == warehouse_id,
        )
    )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.scalars(
        base.order_by(Shelf.code)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    return Page[ShelfOut](
        items=[to_shelf_out(shelf) for shelf in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


def get_shelf(session: Session, shelf_id: UUID) -> Shelf | None:
    return session.scalar(select(Shelf).where(Shelf.id == shelf_id))


def get_shelf_in_scope(
    session: Session, shelf_id: UUID, context: ScopeContext, operation: str
) -> Shelf | None:
    shelf = get_shelf(session, shelf_id)
    units = allowed_units(context, operation)
    if units.global_access:
        return shelf
    if shelf is None:
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
    warehouse = get_warehouse(session, shelf.warehouse_id)
    if warehouse is None:
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
    if (
        str(warehouse.workplace_id) in units.workplace_ids
        or str(warehouse.complex_id) in units.complex_ids
    ):
        return shelf
    raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)


def get_shelf_by_code(session: Session, warehouse_id: UUID, code: str) -> Shelf | None:
    return session.scalar(
        select(Shelf).where(
            Shelf.warehouse_id == warehouse_id,
            Shelf.code == code,
            Shelf.deleted_at.is_(None),
        )
    )


def list_blocking_placements(
    session: Session, *, warehouse_id: UUID | None = None, shelf_id: UUID | None = None
) -> list[InventoryPlacement]:
    """Active placements holding a non-zero quantity under the given scope."""
    base = (
        select(InventoryPlacement)
        .join(Shelf, InventoryPlacement.shelf_id == Shelf.id)
        .where(
            InventoryPlacement.quantity != 0,
            Shelf.deleted_at.is_(None),
        )
    )
    if warehouse_id is not None:
        base = base.where(Shelf.warehouse_id == warehouse_id)
    if shelf_id is not None:
        base = base.where(InventoryPlacement.shelf_id == shelf_id)
    return list(session.scalars(base.order_by(InventoryPlacement.id)).all())


# --- Placements & stock movements (US3) ---


def _placement_base(session: Session, context: ScopeContext, operation: str):  # type: ignore[no-untyped-def]
    return (
        select(InventoryPlacement, ItemCatalog, Shelf, Warehouse)
        .join(Shelf, InventoryPlacement.shelf_id == Shelf.id)
        .join(Warehouse, Shelf.warehouse_id == Warehouse.id)
        .join(ItemCatalog, InventoryPlacement.item_id == ItemCatalog.id)
        .where(_warehouse_scope_filter(context, operation))
    )


def list_placements(
    session: Session,
    context: ScopeContext,
    params: PageParams,
    *,
    warehouse_id: UUID | None = None,
    item_id: UUID | None = None,
    search: str | None = None,
    include_empty: bool = False,
) -> Page[PlacementOut]:
    base = _placement_base(session, context, "warehouse:stock:read")
    if not include_empty:
        base = base.where(InventoryPlacement.quantity > 0)
    if warehouse_id is not None:
        base = base.where(Shelf.warehouse_id == warehouse_id)
    if item_id is not None:
        base = base.where(InventoryPlacement.item_id == item_id)
    if search:
        pattern = f"%{search.strip()}%"
        base = base.where(
            or_(
                ItemCatalog.name_norm.ilike(pattern),
                ItemCatalog.name_fa.ilike(pattern),
                ItemCatalog.code_norm.ilike(pattern),
            )
        )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.execute(
        base.order_by(ItemCatalog.name_norm, Shelf.code)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    items = [to_placement_out(*row) for row in rows]
    return Page[PlacementOut](
        items=items, total=total, page=params.page, page_size=params.page_size
    )


def to_placement_out(
    placement: InventoryPlacement,
    item: ItemCatalog,
    shelf: Shelf,
    warehouse: Warehouse,
) -> PlacementOut:
    from app.modules.warehouse.schemas import (
        ItemBriefOut,
        ShelfBriefOut,
        WarehouseBriefOut,
    )

    return PlacementOut(
        id=placement.id,
        item=ItemBriefOut(
            id=item.id,
            name=item.name,
            name_fa=item.name_fa,
            code=item.code,
            unit=item.unit,
            min_quantity=format_quantity(item.min_quantity),
        ),
        shelf=ShelfBriefOut(id=shelf.id, code=shelf.code, name=shelf.name),
        warehouse=WarehouseBriefOut(id=warehouse.id, code=warehouse.code, name=warehouse.name),
        quantity=format_quantity(placement.quantity),
        below_min_threshold=placement.quantity < item.min_quantity,
    )


def to_movement_out(movement: StockMovement) -> MovementOut:
    return MovementOut(
        id=movement.id,
        movement_type=str(movement.movement_type.value),
        quantity_delta=format_quantity(movement.quantity_delta),
        resulting_quantity=format_quantity(movement.resulting_quantity),
        reason=movement.reason,
        actor_user_id=movement.created_by,
        created_at=movement.created_at,
    )


def get_placement(session: Session, placement_id: UUID) -> InventoryPlacement | None:
    return session.scalar(select(InventoryPlacement).where(InventoryPlacement.id == placement_id))


def get_placement_bundle(
    session: Session, placement_id: UUID
) -> tuple[InventoryPlacement, ItemCatalog, Shelf, Warehouse] | None:
    row = session.execute(
        select(InventoryPlacement, ItemCatalog, Shelf, Warehouse)
        .join(Shelf, InventoryPlacement.shelf_id == Shelf.id)
        .join(Warehouse, Shelf.warehouse_id == Warehouse.id)
        .join(ItemCatalog, InventoryPlacement.item_id == ItemCatalog.id)
        .where(InventoryPlacement.id == placement_id)
    ).first()
    if row is None:
        return None
    return row[0], row[1], row[2], row[3]


def lock_placement(session: Session, placement_id: UUID) -> InventoryPlacement | None:
    """SELECT ... FOR UPDATE — the decrement serialization point (constitution III).

    `populate_existing` forces a fresh read of the locked row so the quantity
    reflects the committed state, not an earlier snapshot in this transaction.
    """
    return session.scalar(
        select(InventoryPlacement)
        .where(InventoryPlacement.id == placement_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def lock_placement_for_stock(
    session: Session, shelf_id: UUID, item_id: UUID
) -> InventoryPlacement | None:
    return session.scalar(
        select(InventoryPlacement)
        .where(
            InventoryPlacement.shelf_id == shelf_id,
            InventoryPlacement.item_id == item_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def record_movement(
    session: Session,
    *,
    placement_id: UUID,
    item_id: UUID,
    movement_type: str,
    quantity_delta: Decimal,
    resulting_quantity: Decimal,
    reason: str | None,
    actor_user_id: UUID,
) -> StockMovement:
    from app.modules.warehouse.models import MovementType

    movement = StockMovement(
        placement_id=placement_id,
        item_id=item_id,
        movement_type=MovementType(movement_type),
        quantity_delta=quantity_delta,
        resulting_quantity=resulting_quantity,
        reason=reason,
        created_by=actor_user_id,
    )
    session.add(movement)
    session.flush()
    return movement


def list_movements(
    session: Session,
    context: ScopeContext,
    params: PageParams,
    *,
    placement_id: UUID,
) -> Page[MovementOut]:
    base = (
        select(StockMovement)
        .join(InventoryPlacement, StockMovement.placement_id == InventoryPlacement.id)
        .join(Shelf, InventoryPlacement.shelf_id == Shelf.id)
        .join(Warehouse, Shelf.warehouse_id == Warehouse.id)
        .where(
            _warehouse_scope_filter(context, "warehouse:stock:read"),
            StockMovement.placement_id == placement_id,
        )
    )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.scalars(
        base.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    return Page[MovementOut](
        items=[to_movement_out(movement) for movement in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


# --- Low-stock alerts (US4) ---


def to_alert_out(
    alert: StockAlert,
    placement: InventoryPlacement,
    item: ItemCatalog,
    shelf: Shelf,
    warehouse: Warehouse,
) -> AlertOut:
    from app.modules.warehouse.schemas import ItemBriefOut, ShelfBriefOut, WarehouseBriefOut

    return AlertOut(
        id=alert.id,
        placement_id=alert.placement_id,
        item=ItemBriefOut(
            id=item.id,
            name=item.name,
            name_fa=item.name_fa,
            code=item.code,
            unit=item.unit,
            min_quantity=format_quantity(item.min_quantity),
        ),
        shelf=ShelfBriefOut(id=shelf.id, code=shelf.code, name=shelf.name),
        warehouse=WarehouseBriefOut(id=warehouse.id, code=warehouse.code, name=warehouse.name),
        quantity_at_alert=format_quantity(alert.quantity_at_alert),
        threshold_at_alert=format_quantity(alert.threshold_at_alert),
        current_quantity=format_quantity(placement.quantity),
        raised_at=alert.created_at,
        resolved_at=alert.resolved_at,
    )


def list_alerts(
    session: Session,
    context: ScopeContext,
    params: PageParams,
    *,
    status: str = "active",
) -> Page[AlertOut]:
    base = (
        select(StockAlert, InventoryPlacement, ItemCatalog, Shelf, Warehouse)
        .join(InventoryPlacement, StockAlert.placement_id == InventoryPlacement.id)
        .join(ItemCatalog, StockAlert.item_id == ItemCatalog.id)
        .join(Shelf, InventoryPlacement.shelf_id == Shelf.id)
        .join(Warehouse, Shelf.warehouse_id == Warehouse.id)
        .where(_warehouse_scope_filter(context, "warehouse:alert:read"))
    )
    if status == "active":
        base = base.where(StockAlert.resolved_at.is_(None))
    elif status == "resolved":
        base = base.where(StockAlert.resolved_at.is_not(None))
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.execute(
        base.order_by(StockAlert.created_at.desc(), StockAlert.id.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    items = [to_alert_out(*row) for row in rows]
    return Page[AlertOut](items=items, total=total, page=params.page, page_size=params.page_size)
