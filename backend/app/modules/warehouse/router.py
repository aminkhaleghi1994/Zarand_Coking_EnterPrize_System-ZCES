import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext
from app.core.database import get_db
from app.modules.user.dependencies import require_operation
from app.modules.user.schemas import PageParams
from app.modules.warehouse import repository, service
from app.modules.warehouse.schemas import (
    ItemCreateIn,
    ItemOut,
    ItemRetireIn,
    ItemUpdateIn,
    ShelfCreateIn,
    ShelfOut,
    ShelfRetireIn,
    ShelfUpdateIn,
    WarehouseCreateIn,
    WarehouseOut,
    WarehouseRetireIn,
    WarehouseUpdateIn,
)

require_item_read = require_operation("warehouse:item:read")
require_item_create = require_operation("warehouse:item:create")
require_item_update = require_operation("warehouse:item:update")
require_item_retire = require_operation("warehouse:item:retire")
require_warehouse_read = require_operation("warehouse:warehouse:read")
require_warehouse_create = require_operation("warehouse:warehouse:create")
require_warehouse_update = require_operation("warehouse:warehouse:update")
require_warehouse_retire = require_operation("warehouse:warehouse:retire")
require_shelf_read = require_operation("warehouse:shelf:read")
require_shelf_create = require_operation("warehouse:shelf:create")
require_shelf_update = require_operation("warehouse:shelf:update")
require_shelf_retire = require_operation("warehouse:shelf:retire")

router = APIRouter(tags=["warehouse"])


@router.get("/warehouse/items", response_model=Page[ItemOut])
def get_items(
    params: PageParams = Depends(),
    search: str | None = None,
    context: ScopeContext = Depends(require_item_read),
    session: Session = Depends(get_db),
) -> Page[ItemOut]:
    _ = context
    return repository.search_items(session, params, search=search)


@router.post("/warehouse/items", response_model=ItemOut, status_code=201)
def post_item(
    payload: ItemCreateIn,
    context: ScopeContext = Depends(require_item_create),
    session: Session = Depends(get_db),
) -> ItemOut:
    item = service.create_item(session, context, payload)
    return repository.to_item_out(item)


@router.get("/warehouse/items/{item_id}", response_model=ItemOut)
def get_item_detail(
    item_id: uuid.UUID,
    context: ScopeContext = Depends(require_item_read),
    session: Session = Depends(get_db),
) -> ItemOut:
    item = repository.get_item(session, item_id)
    if item is None or item.deleted_at is not None:
        from app.core.errors import not_found

        raise not_found("Item not found")
    return repository.to_item_out(item)


@router.patch("/warehouse/items/{item_id}", response_model=ItemOut)
def patch_item(
    item_id: uuid.UUID,
    payload: ItemUpdateIn,
    context: ScopeContext = Depends(require_item_update),
    session: Session = Depends(get_db),
) -> ItemOut:
    item = service.update_item(session, context, item_id, payload)
    return repository.to_item_out(item)


@router.post("/warehouse/items/{item_id}/retire", response_model=ItemOut)
def post_item_retire(
    item_id: uuid.UUID,
    payload: ItemRetireIn,
    context: ScopeContext = Depends(require_item_retire),
    session: Session = Depends(get_db),
) -> ItemOut:
    item = service.retire_item(session, context, item_id, payload)
    return repository.to_item_out(item)


# --- Warehouses & shelves (US2) ---


@router.get("/warehouse/warehouses", response_model=Page[WarehouseOut])
def get_warehouses(
    params: PageParams = Depends(),
    workplace_id: uuid.UUID | None = None,
    context: ScopeContext = Depends(require_warehouse_read),
    session: Session = Depends(get_db),
) -> Page[WarehouseOut]:
    return repository.list_warehouses(session, context, params, workplace_id=workplace_id)


@router.post("/warehouse/warehouses", response_model=WarehouseOut, status_code=201)
def post_warehouse(
    payload: WarehouseCreateIn,
    context: ScopeContext = Depends(require_warehouse_create),
    session: Session = Depends(get_db),
) -> WarehouseOut:
    warehouse = service.create_warehouse(session, context, payload)
    return repository.to_warehouse_out(warehouse)


@router.patch("/warehouse/warehouses/{warehouse_id}", response_model=WarehouseOut)
def patch_warehouse(
    warehouse_id: uuid.UUID,
    payload: WarehouseUpdateIn,
    context: ScopeContext = Depends(require_warehouse_update),
    session: Session = Depends(get_db),
) -> WarehouseOut:
    warehouse = service.update_warehouse(session, context, warehouse_id, payload)
    return repository.to_warehouse_out(warehouse)


@router.post("/warehouse/warehouses/{warehouse_id}/retire", response_model=WarehouseOut)
def post_warehouse_retire(
    warehouse_id: uuid.UUID,
    payload: WarehouseRetireIn,
    context: ScopeContext = Depends(require_warehouse_retire),
    session: Session = Depends(get_db),
) -> WarehouseOut:
    warehouse = service.retire_warehouse(session, context, warehouse_id, payload)
    return repository.to_warehouse_out(warehouse)


@router.get("/warehouse/warehouses/{warehouse_id}/shelves", response_model=Page[ShelfOut])
def get_shelves(
    warehouse_id: uuid.UUID,
    params: PageParams = Depends(),
    context: ScopeContext = Depends(require_shelf_read),
    session: Session = Depends(get_db),
) -> Page[ShelfOut]:
    return repository.list_shelves(session, context, params, warehouse_id=warehouse_id)


@router.post(
    "/warehouse/warehouses/{warehouse_id}/shelves", response_model=ShelfOut, status_code=201
)
def post_shelf(
    warehouse_id: uuid.UUID,
    payload: ShelfCreateIn,
    context: ScopeContext = Depends(require_shelf_create),
    session: Session = Depends(get_db),
) -> ShelfOut:
    shelf = service.create_shelf(session, context, warehouse_id, payload)
    return repository.to_shelf_out(shelf)


@router.patch("/warehouse/shelves/{shelf_id}", response_model=ShelfOut)
def patch_shelf(
    shelf_id: uuid.UUID,
    payload: ShelfUpdateIn,
    context: ScopeContext = Depends(require_shelf_update),
    session: Session = Depends(get_db),
) -> ShelfOut:
    shelf = service.update_shelf(session, context, shelf_id, payload)
    return repository.to_shelf_out(shelf)


@router.post("/warehouse/shelves/{shelf_id}/retire", response_model=ShelfOut)
def post_shelf_retire(
    shelf_id: uuid.UUID,
    payload: ShelfRetireIn,
    context: ScopeContext = Depends(require_shelf_retire),
    session: Session = Depends(get_db),
) -> ShelfOut:
    shelf = service.retire_shelf(session, context, shelf_id, payload)
    return repository.to_shelf_out(shelf)
