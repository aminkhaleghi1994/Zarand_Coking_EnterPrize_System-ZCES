import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext, allowed_units
from app.core.database import get_db
from app.core.errors import AUTHORIZATION_DENIED, AppError, not_found
from app.modules.user.dependencies import load_context, require_operation
from app.modules.user.schemas import PageParams
from app.modules.warehouse import repository, request_repository, request_service, service
from app.modules.warehouse.schemas import (
    AdjustIn,
    AlertOut,
    DecisionIn,
    FulfillIn,
    IssueIn,
    ItemCreateIn,
    ItemOut,
    ItemRetireIn,
    ItemUpdateIn,
    MovementOut,
    PlacementOut,
    ReceiveIn,
    RequestCreateIn,
    RequestOut,
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
require_stock_read = require_operation("warehouse:stock:read")
require_stock_receive = require_operation("warehouse:stock:receive")
require_stock_issue = require_operation("warehouse:stock:issue")
require_stock_adjust = require_operation("warehouse:stock:adjust")
require_alert_read = require_operation("warehouse:alert:read")
require_request_decide = require_operation("warehouse:request:decide")
require_request_fulfill = require_operation("warehouse:request:fulfill")

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


# --- Placements & stock (US3) ---


@router.get("/warehouse/placements", response_model=Page[PlacementOut])
def get_placements(
    params: PageParams = Depends(),
    warehouse_id: uuid.UUID | None = None,
    item_id: uuid.UUID | None = None,
    search: str | None = None,
    include_empty: bool = False,
    context: ScopeContext = Depends(require_stock_read),
    session: Session = Depends(get_db),
) -> Page[PlacementOut]:
    return repository.list_placements(
        session,
        context,
        params,
        warehouse_id=warehouse_id,
        item_id=item_id,
        search=search,
        include_empty=include_empty,
    )


@router.post("/warehouse/placements/receive", response_model=PlacementOut)
def post_receive(
    payload: ReceiveIn,
    context: ScopeContext = Depends(require_stock_receive),
    session: Session = Depends(get_db),
) -> PlacementOut:
    placement, item, shelf, warehouse = service.receive_stock(session, context, payload)
    return repository.to_placement_out(placement, item, shelf, warehouse)


@router.post("/warehouse/placements/issue", response_model=PlacementOut)
def post_issue(
    payload: IssueIn,
    context: ScopeContext = Depends(require_stock_issue),
    session: Session = Depends(get_db),
) -> PlacementOut:
    placement, item, shelf, warehouse = service.issue_stock(session, context, payload)
    return repository.to_placement_out(placement, item, shelf, warehouse)


@router.post("/warehouse/placements/adjust", response_model=PlacementOut)
def post_adjust(
    payload: AdjustIn,
    context: ScopeContext = Depends(require_stock_adjust),
    session: Session = Depends(get_db),
) -> PlacementOut:
    placement, item, shelf, warehouse = service.adjust_stock(session, context, payload)
    return repository.to_placement_out(placement, item, shelf, warehouse)


@router.get("/warehouse/placements/{placement_id}/movements", response_model=Page[MovementOut])
def get_movements(
    placement_id: uuid.UUID,
    params: PageParams = Depends(),
    context: ScopeContext = Depends(require_stock_read),
    session: Session = Depends(get_db),
) -> Page[MovementOut]:
    return repository.list_movements(session, context, params, placement_id=placement_id)


# --- Low-stock alerts (US4) ---


@router.get("/warehouse/alerts", response_model=Page[AlertOut])
def get_alerts(
    params: PageParams = Depends(),
    active: str = Query(default="active", pattern="^(true|false|all)$"),
    context: ScopeContext = Depends(require_alert_read),
    session: Session = Depends(get_db),
) -> Page[AlertOut]:
    status = {"true": "active", "false": "resolved", "all": "all"}[active]
    return repository.list_alerts(session, context, params, status=status)


# --- Item requests (Phase 5) ---


@router.post("/warehouse/requests", response_model=RequestOut, status_code=201)
def post_request(
    payload: RequestCreateIn,
    context: ScopeContext = Depends(load_context),
    session: Session = Depends(get_db),
) -> RequestOut:
    request = request_service.create_request(session, context, payload)
    lines = request_repository.get_request_lines(session, request.id)
    email = request_repository.get_requester_email(session, request.requested_by)
    return request_repository.to_request_out(session, request, lines, email)


@router.get("/warehouse/requests", response_model=Page[RequestOut])
def get_requests(
    params: PageParams = Depends(),
    status: str = Query(default="all", pattern="^(all|pending|approved|rejected|fulfilled)$"),
    context: ScopeContext = Depends(load_context),
    session: Session = Depends(get_db),
) -> Page[RequestOut]:
    return request_repository.list_requests(session, context, params, status=status)


@router.get("/warehouse/requests/{request_id}", response_model=RequestOut)
def get_request_detail(
    request_id: uuid.UUID,
    context: ScopeContext = Depends(load_context),
    session: Session = Depends(get_db),
) -> RequestOut:
    request = request_repository.get_request(session, request_id)
    if request is None:
        raise not_found("Request not found")
    if request.requested_by != uuid.UUID(context.user_id):
        units = allowed_units(context, "warehouse:request:read")
        covered = units.global_access or (
            (request.workplace_id is not None and str(request.workplace_id) in units.workplace_ids)
            or (request.complex_id is not None and str(request.complex_id) in units.complex_ids)
        )
        if not covered:
            raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
    lines = request_repository.get_request_lines(session, request.id)
    email = request_repository.get_requester_email(session, request.requested_by)
    return request_repository.to_request_out(session, request, lines, email)


@router.post("/warehouse/requests/{request_id}/approve", response_model=RequestOut)
def post_request_approve(
    request_id: uuid.UUID,
    payload: DecisionIn,
    context: ScopeContext = Depends(require_request_decide),
    session: Session = Depends(get_db),
) -> RequestOut:
    request = request_service.decide_request(session, context, request_id, payload, approve=True)
    lines = request_repository.get_request_lines(session, request.id)
    email = request_repository.get_requester_email(session, request.requested_by)
    return request_repository.to_request_out(session, request, lines, email)


@router.post("/warehouse/requests/{request_id}/reject", response_model=RequestOut)
def post_request_reject(
    request_id: uuid.UUID,
    payload: DecisionIn,
    context: ScopeContext = Depends(require_request_decide),
    session: Session = Depends(get_db),
) -> RequestOut:
    request = request_service.decide_request(session, context, request_id, payload, approve=False)
    lines = request_repository.get_request_lines(session, request.id)
    email = request_repository.get_requester_email(session, request.requested_by)
    return request_repository.to_request_out(session, request, lines, email)


@router.post("/warehouse/requests/{request_id}/fulfill", response_model=RequestOut)
def post_request_fulfill(
    request_id: uuid.UUID,
    payload: FulfillIn,
    context: ScopeContext = Depends(require_request_fulfill),
    session: Session = Depends(get_db),
) -> RequestOut:
    request = request_service.fulfill_request(session, context, request_id, payload)
    lines = request_repository.get_request_lines(session, request.id)
    email = request_repository.get_requester_email(session, request.requested_by)
    return request_repository.to_request_out(session, request, lines, email)
