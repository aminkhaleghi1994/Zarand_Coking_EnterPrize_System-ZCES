"""Asset queries. Every scope-aware function filters by the asset's workplace
anchor via `allowed_units` (constitution II); anchorless rows (creator
without an employee record) are visible only to global coverage."""

from decimal import Decimal  # noqa: F401  (typing parity with sibling modules)
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy import false as sa_false
from sqlalchemy import true as sa_true
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext, allowed_units
from app.modules.user.models import Employee
from app.modules.user.schemas import PageParams
from app.modules.warehouse.models import AssetHistory, AssetInstance, HolderType
from app.modules.warehouse.schemas import (
    AssetHistoryOut,
    AssetOut,
    EmployeeBriefOut,
    HistoryHolderOut,
    HolderOut,
)

ASSET_READ_OPERATION = "warehouse:asset:read"


def _holder_out(asset: AssetInstance, holder_name: str | None) -> HolderOut:
    if asset.holder_type is None:
        return HolderOut(type="available")
    if asset.holder_type.value == "employee":
        return HolderOut(
            type="employee",
            employee=EmployeeBriefOut(id=asset.holder_employee_id, name=holder_name or "—"),
        )
    return HolderOut(type="location", location=asset.holder_location)


def to_asset_out(asset: AssetInstance, holder_name: str | None = None) -> AssetOut:
    status = (
        "retired"
        if asset.deleted_at is not None
        else ("assigned" if asset.holder_type is not None else "available")
    )
    return AssetOut(
        id=asset.id,
        version=asset.version,
        name=asset.name,
        name_fa=asset.name_fa,
        serial=asset.serial,
        description=asset.description,
        status=status,
        holder=_holder_out(asset, holder_name),
        created_at=asset.created_at,
    )


def to_history_out(history: AssetHistory, holder_name: str | None = None) -> AssetHistoryOut:
    def holder_out(
        holder_type: HolderType | None,
        employee_id: UUID | None,
        location: str | None,
    ) -> HistoryHolderOut | None:
        if holder_type is None:
            return HistoryHolderOut(type="available")
        if holder_type.value == "employee":
            return HistoryHolderOut(
                type="employee",
                employee=EmployeeBriefOut(id=employee_id, name=holder_name or "—"),
            )
        return HistoryHolderOut(type="location", location=location)

    return AssetHistoryOut(
        id=history.id,
        action=str(history.action.value),
        from_holder=holder_out(history.from_type, history.from_employee_id, history.from_location),
        to_holder=holder_out(history.to_type, history.to_employee_id, history.to_location),
        note=history.note,
        actor_user_id=history.created_by,
        created_at=history.created_at,
    )


def _asset_scope_filter(context: ScopeContext, operation: str) -> ColumnElement[bool]:
    units = allowed_units(context, operation)
    if units.global_access:
        return sa_true()
    conditions = []
    if units.complex_ids:
        conditions.append(AssetInstance.complex_id.in_(units.complex_ids))
    if units.workplace_ids:
        conditions.append(AssetInstance.workplace_id.in_(units.workplace_ids))
    if not conditions:
        return sa_false()
    return or_(*conditions)


def _asset_search_filter(search: str | None) -> ColumnElement[bool]:
    if not search:
        return sa_true()
    pattern = f"%{search.strip()}%"
    return or_(
        AssetInstance.name.ilike(pattern),
        AssetInstance.name_fa.ilike(pattern),
        AssetInstance.serial_norm.ilike(pattern),
    )


def _status_filter(status: str | None) -> ColumnElement[bool]:
    if status is None or status == "all":
        return sa_true()
    if status == "retired":
        return AssetInstance.deleted_at.is_not(None)
    if status == "assigned":
        return AssetInstance.holder_type.is_not(None) & AssetInstance.deleted_at.is_(None)
    return AssetInstance.holder_type.is_(None) & AssetInstance.deleted_at.is_(None)


def list_assets(
    session: Session,
    context: ScopeContext,
    params: PageParams,
    *,
    search: str | None = None,
    status: str | None = "available",
) -> Page[AssetOut]:
    base = select(AssetInstance).where(
        _asset_scope_filter(context, ASSET_READ_OPERATION),
        _status_filter(status),
        _asset_search_filter(search),
    )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    assets = session.scalars(
        base.order_by(AssetInstance.created_at.desc(), AssetInstance.id.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()

    holder_ids = {asset.holder_employee_id for asset in assets if asset.holder_employee_id}
    holder_names: dict[UUID, str] = {}
    if holder_ids:
        rows = session.execute(
            select(Employee.id, Employee.first_name, Employee.last_name).where(
                Employee.id.in_(holder_ids)
            )
        ).all()
        for row_id, first_name, last_name in rows:
            holder_names[row_id] = f"{first_name} {last_name}".strip()

    return Page[AssetOut](
        items=[
            to_asset_out(
                asset,
                holder_names.get(asset.holder_employee_id)
                if asset.holder_employee_id is not None
                else None,
            )
            for asset in assets
        ],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


def get_asset(session: Session, asset_id: UUID) -> AssetInstance | None:
    return session.scalar(select(AssetInstance).where(AssetInstance.id == asset_id))


def get_asset_for_update(session: Session, asset_id: UUID) -> AssetInstance | None:
    """Mutation load with a row lock so concurrent version-guarded actions
    (assign/return/retire/update) serialize — exactly one winner."""
    return session.scalar(
        select(AssetInstance).where(AssetInstance.id == asset_id).with_for_update()
    )


def get_asset_by_serial_norm(session: Session, serial_norm: str) -> AssetInstance | None:
    return session.scalar(
        select(AssetInstance).where(
            AssetInstance.serial_norm == serial_norm, AssetInstance.deleted_at.is_(None)
        )
    )


def get_holder_name(session: Session, employee_id: UUID) -> str | None:
    return session.scalar(
        select(Employee.first_name + " " + Employee.last_name).where(Employee.id == employee_id)
    )


def get_history(session: Session, asset_id: UUID) -> list[tuple[AssetHistory, str | None]]:
    rows = (
        session.execute(
            select(AssetHistory)
            .where(AssetHistory.asset_id == asset_id)
            .order_by(AssetHistory.created_at.desc(), AssetHistory.id.desc())
        )
        .scalars()
        .all()
    )
    entries: list[tuple[AssetHistory, str | None]] = []
    holder_names: dict[UUID, str] = {}
    for history in rows:
        for employee_id in (history.from_employee_id, history.to_employee_id):
            if employee_id is not None and employee_id not in holder_names:
                holder_names[employee_id] = (
                    session.scalar(
                        select(Employee.first_name + " " + Employee.last_name).where(
                            Employee.id == employee_id
                        )
                    )
                    or "—"
                )
    for history in rows:
        name = None
        for employee_id in (history.from_employee_id, history.to_employee_id):
            if employee_id is not None:
                name = holder_names[employee_id]
                break
        entries.append((history, name))
    return entries


def write_history(
    session: Session,
    *,
    asset_id: UUID,
    action: str,
    from_type: str | None,
    from_employee_id: UUID | None,
    from_location: str | None,
    to_type: str | None,
    to_employee_id: UUID | None,
    to_location: str | None,
    note: str | None,
    actor_user_id: UUID,
) -> AssetHistory:
    from app.modules.warehouse.models import AssetAction

    history = AssetHistory(
        asset_id=asset_id,
        action=AssetAction(action),
        from_type=from_type,
        from_employee_id=from_employee_id,
        from_location=from_location,
        to_type=to_type,
        to_employee_id=to_employee_id,
        to_location=to_location,
        note=note,
        created_by=actor_user_id,
    )
    session.add(history)
    session.flush()
    return history
