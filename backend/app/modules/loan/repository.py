"""Loan queries. Scope-filtered reads use `allowed_units` on the workplace
anchor (constitution II).

Deliberate exception (research R9, requirements §19): the two count
aggregates and the amount-cap sum read ALL rows of the employee — including
soft-deleted ones — because settled, cancelled, and soft-deleted requests
never free the count limits, and an active request that was soft-deleted
still binds its cap until settled. Every other read is active-only.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy import false as sa_false
from sqlalchemy import true as sa_true
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext, allowed_units
from app.modules.loan.models import LoanPolicy, LoanRequest
from app.modules.loan.schemas import (
    EmployeeBriefOut,
    LoanPolicyOut,
    LoanRequestOut,
    WorkplaceBriefOut,
    format_money,
)
from app.modules.user.models import Employee, Workplace
from app.modules.user.schemas import PageParams

POLICY_READ_OPERATION = "loan:policy:read"
REQUEST_READ_OPERATION = "loan:request:read"


def _loan_scope_filter(context: ScopeContext, operation: str) -> ColumnElement[bool]:
    units = allowed_units(context, operation)
    if units.global_access:
        return sa_true()
    conditions = []
    if units.complex_ids:
        conditions.append(LoanRequest.complex_id.in_(units.complex_ids))
    if units.workplace_ids:
        conditions.append(LoanRequest.workplace_id.in_(units.workplace_ids))
    if not conditions:
        return sa_false()
    return or_(*conditions)


def _policy_scope_filter(context: ScopeContext, operation: str) -> ColumnElement[bool]:
    """Policies carry only a workplace anchor, so complex-scope coverage
    resolves through the workplaces join."""
    units = allowed_units(context, operation)
    if units.global_access:
        return sa_true()
    conditions = []
    if units.complex_ids:
        conditions.append(Workplace.complex_id.in_(units.complex_ids))
    if units.workplace_ids:
        conditions.append(LoanPolicy.workplace_id.in_(units.workplace_ids))
    if not conditions:
        return sa_false()
    return or_(*conditions)


# --- Policies ---


def get_active_policy(
    session: Session, workplace_id: UUID, year: int
) -> LoanPolicy | None:
    """The policy governing a workplace + Jalali year (active rows only).

    Returns None when retired; callers also refuse when `is_active` is
    False (paused behaves like absent per data-model semantics).
    """
    return session.scalar(
        select(LoanPolicy)
        .where(
            LoanPolicy.workplace_id == workplace_id,
            LoanPolicy.year == year,
            LoanPolicy.deleted_at.is_(None),
        )
        .order_by(LoanPolicy.created_at.desc())
        .limit(1)
    )


def get_policy_by_workplace_year(
    session: Session, workplace_id: UUID, year: int, *, exclude_id: UUID | None = None
) -> LoanPolicy | None:
    statement = select(LoanPolicy).where(
        LoanPolicy.workplace_id == workplace_id,
        LoanPolicy.year == year,
        LoanPolicy.deleted_at.is_(None),
    )
    if exclude_id is not None:
        statement = statement.where(LoanPolicy.id != exclude_id)
    return session.scalar(statement.limit(1))


def get_policy(session: Session, policy_id: UUID) -> LoanPolicy | None:
    return session.scalar(
        select(LoanPolicy).where(
            LoanPolicy.id == policy_id, LoanPolicy.deleted_at.is_(None)
        )
    )


def to_policy_out(policy: LoanPolicy, workplace: Workplace) -> LoanPolicyOut:
    return LoanPolicyOut(
        id=policy.id,
        version=policy.version,
        workplace=WorkplaceBriefOut(
            id=workplace.id, code=workplace.code, name=workplace.name, name_fa=workplace.name_fa
        ),
        year=policy.year,
        max_loan_amount=format_money(policy.max_loan_amount),
        max_guarantee_amount=format_money(policy.max_guarantee_amount),
        max_request_count_per_year=policy.max_request_count_per_year,
        max_request_count_lifetime=policy.max_request_count_lifetime,
        is_active=policy.is_active,
        created_at=policy.created_at,
    )


def list_policies(
    session: Session,
    context: ScopeContext,
    params: PageParams,
    *,
    year: int | None = None,
    include_retired: bool = False,
) -> Page[LoanPolicyOut]:
    base = (
        select(LoanPolicy)
        .join(Workplace, LoanPolicy.workplace_id == Workplace.id)
        .where(_policy_scope_filter(context, POLICY_READ_OPERATION))
    )
    if not include_retired:
        base = base.where(LoanPolicy.deleted_at.is_(None))
    if year is not None:
        base = base.where(LoanPolicy.year == year)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    policies = session.scalars(
        base.order_by(LoanPolicy.year.desc(), LoanPolicy.created_at.desc(), LoanPolicy.id.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()

    workplace_ids = {policy.workplace_id for policy in policies}
    workplaces: dict[UUID, Workplace] = {}
    if workplace_ids:
        rows = session.scalars(select(Workplace).where(Workplace.id.in_(workplace_ids))).all()
        workplaces = {w.id: w for w in rows}

    items = [to_policy_out(policy, workplaces[policy.workplace_id]) for policy in policies]
    return Page[LoanPolicyOut](
        items=items, total=total, page=params.page, page_size=params.page_size
    )


# --- Requests ---


def get_request(session: Session, request_id: UUID) -> LoanRequest | None:
    return session.scalar(
        select(LoanRequest).where(
            LoanRequest.id == request_id, LoanRequest.deleted_at.is_(None)
        )
    )


def load_request_context(
    session: Session, request: LoanRequest
) -> tuple[Employee, Workplace]:
    employee = session.get(Employee, request.employee_id)
    workplace = session.get(Workplace, request.workplace_id)
    if employee is None or workplace is None:
        from app.core.errors import not_found  # noqa: PLC0415

        raise not_found("Loan request not found")
    return employee, workplace


def request_out(session: Session, request: LoanRequest) -> LoanRequestOut:
    employee, workplace = load_request_context(session, request)
    return to_request_out(request, employee, workplace)


def policy_out(session: Session, policy: LoanPolicy) -> LoanPolicyOut:
    workplace = session.get(Workplace, policy.workplace_id)
    if workplace is None:
        from app.core.errors import not_found  # noqa: PLC0415

        raise not_found("Loan policy not found")
    return to_policy_out(policy, workplace)


def _visibility_filter(context: ScopeContext) -> ColumnElement[bool]:
    caller = UUID(context.user_id)
    return or_(
        LoanRequest.created_by == caller,
        _loan_scope_filter(context, REQUEST_READ_OPERATION),
    )


def to_request_out(
    request: LoanRequest, employee: Employee, workplace: Workplace
) -> LoanRequestOut:
    return LoanRequestOut(
        id=request.id,
        version=request.version,
        employee=EmployeeBriefOut(
            id=employee.id,
            name=f"{employee.first_name} {employee.last_name}".strip(),
            name_fa=(
                f"{employee.first_name_fa or ''} {employee.last_name_fa or ''}".strip() or None
            ),
        ),
        workplace=WorkplaceBriefOut(
            id=workplace.id, code=workplace.code, name=workplace.name, name_fa=workplace.name_fa
        ),
        type=str(request.type.value),
        amount=format_money(request.amount),
        year=request.year,
        status=str(request.status.value),
        settled_at=request.settled_at,
        created_at=request.created_at,
    )


def list_requests(
    session: Session,
    context: ScopeContext,
    requester_employee_id: UUID | None,
    params: PageParams,
    *,
    type: str | None = None,
    status: str | None = None,
    year: int | None = None,
) -> Page[LoanRequestOut]:
    """Ownership-OR-scope visibility (research R6): the caller always sees
    requests they created; `loan:request:read` holders additionally see their
    units' requests (union, implicit deny)."""
    conditions: list[ColumnElement[bool]] = []
    if requester_employee_id is not None:
        conditions.append(LoanRequest.employee_id == requester_employee_id)
    conditions.append(_loan_scope_filter(context, REQUEST_READ_OPERATION))
    base = select(LoanRequest).where(or_(*conditions)).where(LoanRequest.deleted_at.is_(None))
    if type is not None:
        base = base.where(LoanRequest.type == type)
    if status is not None and status != "all":
        base = base.where(LoanRequest.status == status)
    if year is not None:
        base = base.where(LoanRequest.year == year)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    requests = session.scalars(
        base.order_by(LoanRequest.created_at.desc(), LoanRequest.id.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()

    employee_ids = {request.employee_id for request in requests}
    workplace_ids = {request.workplace_id for request in requests}
    employees: dict[UUID, Employee] = {}
    workplaces: dict[UUID, Workplace] = {}
    if employee_ids:
        employee_rows = session.scalars(
            select(Employee).where(Employee.id.in_(employee_ids))
        ).all()
        employees = {e.id: e for e in employee_rows}
    if workplace_ids:
        workplace_rows = session.scalars(
            select(Workplace).where(Workplace.id.in_(workplace_ids))
        ).all()
        workplaces = {w.id: w for w in workplace_rows}

    items = [
        to_request_out(request, employees[request.employee_id], workplaces[request.workplace_id])
        for request in requests
    ]
    return Page[LoanRequestOut](
        items=items, total=total, page=params.page, page_size=params.page_size
    )


# --- §19 aggregates (the documented soft-deleted-row exception, research R9) ---


def count_requests_lifetime(session: Session, employee_id: UUID) -> int:
    """§19 rule 1: every request ever made counts — status and soft-delete
    are ignored (settled/cancelled/soft-deleted never free the limits)."""
    return session.scalar(
        select(func.count()).select_from(LoanRequest).where(LoanRequest.employee_id == employee_id)
    ) or 0


def count_requests_year(session: Session, employee_id: UUID, year: int) -> int:
    """§19 rule 2: yearly count — same all-rows semantics, filtered on the
    request's Jalali year snapshot."""
    return session.scalar(
        select(func.count())
        .select_from(LoanRequest)
        .where(LoanRequest.employee_id == employee_id, LoanRequest.year == year)
    ) or 0


def sum_active_amount(
    session: Session, employee_id: UUID, year: int, type: str
) -> Decimal:
    """§19 rules 3/4: only ACTIVE requests of the validated year and matching
    type bind the amount cap (clarified Q3; settled/cancelled free)."""
    total = session.scalar(
        select(func.sum(LoanRequest.amount)).where(
            LoanRequest.employee_id == employee_id,
            LoanRequest.year == year,
            LoanRequest.type == type,
            LoanRequest.status == "active",
        )
    )
    return Decimal(total) if total is not None else Decimal("0")
