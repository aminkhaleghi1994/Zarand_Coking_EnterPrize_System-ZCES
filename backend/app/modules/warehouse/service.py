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

from app.common.scope import ScopeContext
from app.core.errors import (
    AUTHORIZATION_DENIED,
    STALE_VERSION,
    AppError,
    duplicate_resource,
    not_found,
)
from app.modules.audit.contracts import write_audit
from app.modules.warehouse import repository
from app.modules.warehouse.models import ItemCatalog
from app.modules.warehouse.schemas import (
    ItemCreateIn,
    ItemRetireIn,
    ItemUpdateIn,
    format_quantity,
    quantize_quantity,
)

_ITEM_CREATE = "warehouse:item:create"
_ITEM_UPDATE = "warehouse:item:update"
_ITEM_RETIRE = "warehouse:item:retire"


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


__all__ = [
    "create_item",
    "retire_item",
    "update_item",
]
