from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy import false as sa_false
from sqlalchemy import true as sa_true
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext, allowed_units
from app.modules.user.models import Complex, Workplace
from app.modules.user.schemas import ComplexOut, PageParams, WorkplaceOut

ORG_READ_OPERATION = "user:org:read"


def _complex_scope_filter(context: ScopeContext) -> ColumnElement[bool]:
    """SQL filter limiting complexes to the caller's scope (false when denied)."""
    units = allowed_units(context, ORG_READ_OPERATION)
    if units.global_access:
        return sa_true()
    conditions = []
    if units.complex_ids:
        conditions.append(Complex.id.in_(units.complex_ids))
    if units.workplace_ids:
        conditions.append(
            Complex.id.in_(
                select(Workplace.complex_id).where(Workplace.id.in_(units.workplace_ids))
            )
        )
    if not conditions:
        return sa_false()
    return or_(*conditions)


def list_complexes(session: Session, context: ScopeContext, params: PageParams) -> Page[ComplexOut]:
    base = select(Complex).where(
        Complex.deleted_at.is_(None),
        _complex_scope_filter(context),
    )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.scalars(
        base.order_by(Complex.name)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    return Page[ComplexOut](
        items=[ComplexOut.model_validate(r) for r in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


def _workplace_scope_filter(context: ScopeContext) -> ColumnElement[bool]:
    """SQL filter limiting workplaces to the caller's scope (false when denied)."""
    units = allowed_units(context, ORG_READ_OPERATION)
    if units.global_access:
        return sa_true()
    conditions = []
    if units.complex_ids:
        conditions.append(Workplace.complex_id.in_(units.complex_ids))
    if units.workplace_ids:
        conditions.append(Workplace.id.in_(units.workplace_ids))
    if not conditions:
        return sa_false()
    return or_(*conditions)


def list_workplaces(
    session: Session,
    context: ScopeContext,
    params: PageParams,
    *,
    complex_id: UUID | None = None,
) -> Page[WorkplaceOut]:
    base = select(Workplace).where(
        Workplace.deleted_at.is_(None),
        _workplace_scope_filter(context),
    )
    if complex_id is not None:
        base = base.where(Workplace.complex_id == complex_id)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.scalars(
        base.order_by(Workplace.name)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    return Page[WorkplaceOut](
        items=[WorkplaceOut.model_validate(r) for r in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


def get_workplace(session: Session, workplace_id: UUID) -> Workplace | None:
    return session.scalar(
        select(Workplace).where(Workplace.id == workplace_id, Workplace.deleted_at.is_(None))
    )


def get_complex(session: Session, complex_id: UUID) -> Complex | None:
    return session.scalar(
        select(Complex).where(Complex.id == complex_id, Complex.deleted_at.is_(None))
    )
