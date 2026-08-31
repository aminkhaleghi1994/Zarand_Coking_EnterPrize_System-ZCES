from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy import false as sa_false
from sqlalchemy import true as sa_true
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext, allowed_units
from app.modules.user.models import Complex, Employee, User, Workplace
from app.modules.user.schemas import (
    EmployeeSummaryOut,
    PageParams,
    StatusFilterIn,
)

EMPLOYEE_READ_OPERATION = "user:employee:read"


def _employee_scope_filter(context: ScopeContext, operation: str) -> ColumnElement[bool]:
    """Scope filter over employees; false (deny all rows) when no coverage."""
    units = allowed_units(context, operation)
    if units.global_access:
        return sa_true()
    conditions = []
    if units.complex_ids:
        conditions.append(
            Employee.workplace_id.in_(
                select(Workplace.id).where(Workplace.complex_id.in_(units.complex_ids))
            )
        )
    if units.workplace_ids:
        conditions.append(Employee.workplace_id.in_(units.workplace_ids))
    if not conditions:
        return sa_false()
    return or_(*conditions)


def _status_filter(status: StatusFilterIn) -> ColumnElement[bool]:
    if status == StatusFilterIn.ACTIVE:
        return Employee.deleted_at.is_(None)
    if status == StatusFilterIn.DEACTIVATED:
        return Employee.deleted_at.is_not(None)
    return sa_true()


def _search_filter(search: str | None) -> ColumnElement[bool]:
    if not search:
        return sa_true()
    pattern = f"%{search.strip()}%"
    return or_(
        Employee.first_name.ilike(pattern),
        Employee.last_name.ilike(pattern),
        Employee.first_name_fa.ilike(pattern),
        Employee.last_name_fa.ilike(pattern),
        Employee.national_id.like(f"{search.strip()}%"),
        Employee.personnel_code.ilike(pattern),
    )


def list_employees(
    session: Session,
    context: ScopeContext,
    params: PageParams,
    *,
    search: str | None = None,
    status: StatusFilterIn = StatusFilterIn.ACTIVE,
    workplace_id: UUID | None = None,
    complex_id: UUID | None = None,
) -> Page[EmployeeSummaryOut]:
    base = (
        select(
            Employee,
            Workplace,
            Complex,
        )
        .join(Workplace, Employee.workplace_id == Workplace.id)
        .join(Complex, Workplace.complex_id == Complex.id)
        .where(
            _employee_scope_filter(context, EMPLOYEE_READ_OPERATION),
            _status_filter(status),
            _search_filter(search),
        )
    )
    if workplace_id is not None:
        base = base.where(Employee.workplace_id == workplace_id)
    if complex_id is not None:
        base = base.where(Workplace.complex_id == complex_id)

    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.execute(
        base.order_by(Employee.last_name, Employee.first_name)
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    items = [
        EmployeeSummaryOut(
            id=employee.id,
            national_id=employee.national_id,
            personnel_code=employee.personnel_code,
            first_name=employee.first_name,
            last_name=employee.last_name,
            is_active=employee.is_active and employee.deleted_at is None,
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )
        for employee, workplace, _complex in rows
    ]
    return Page[EmployeeSummaryOut](
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


def get_employee(session: Session, employee_id: UUID) -> Employee | None:
    return session.scalar(select(Employee).where(Employee.id == employee_id))


def get_employee_in_scope(
    session: Session, employee_id: UUID, context: ScopeContext, operation: str
) -> Employee | None:
    """Scope-checked read with no existence leak (FR-017).

    - Global coverage: returns the employee or None (caller maps None to 404).
    - Non-global coverage: missing employee AND out-of-scope employee both
      raise AUTHORIZATION_DENIED — the two are indistinguishable.
    """
    from app.core.errors import AUTHORIZATION_DENIED, AppError

    employee = get_employee(session, employee_id)
    units = allowed_units(context, operation)
    if units.global_access:
        return employee
    if employee is None:
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
    workplace = session.scalar(select(Workplace).where(Workplace.id == employee.workplace_id))
    if workplace is None:
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
    if workplace.id in units.workplace_ids or workplace.complex_id in units.complex_ids:
        return employee
    raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)


def get_by_national_id(session: Session, national_id: str) -> Employee | None:
    """Duplicate lookup among active rows (soft-deleted rows never block)."""
    return session.scalar(
        select(Employee).where(Employee.national_id == national_id, Employee.deleted_at.is_(None))
    )


def get_by_personnel_code(session: Session, personnel_code: str) -> Employee | None:
    return session.scalar(
        select(Employee).where(
            Employee.personnel_code == personnel_code, Employee.deleted_at.is_(None)
        )
    )


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(
        select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
    )


def get_user_by_username(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username == username, User.deleted_at.is_(None)))


def get_user_by_employee_id(session: Session, employee_id: UUID) -> User | None:
    return session.scalar(select(User).where(User.employee_id == employee_id))
