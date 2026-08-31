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
)

require_item_read = require_operation("warehouse:item:read")
require_item_create = require_operation("warehouse:item:create")
require_item_update = require_operation("warehouse:item:update")
require_item_retire = require_operation("warehouse:item:retire")

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
