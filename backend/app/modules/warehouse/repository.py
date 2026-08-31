"""Warehouse module queries. Every scope-aware function takes a ScopeContext
and applies the mandatory scope filter (constitution II) — a query without one
is a bug. Exception per spec FR-019/research R5: catalog reads are
company-wide reference data gated by permission alone."""

from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy import true as sa_true
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.modules.user.schemas import PageParams
from app.modules.warehouse.models import ItemCatalog
from app.modules.warehouse.schemas import ItemOut, format_quantity

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
