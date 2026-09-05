"""Public contract of the user module for other modules (constitution VI).

Cross-module consumers import ONLY from this file — never from
``models.py``/``repository.py``/services directly.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.common.scope import ScopeContext
from app.modules.user.models import (
    Company,
    Complex,
    Employee,
    Permission,
    RolePermission,
    ScopeAssignment,
    ScopeLevel,
    User,
    UserRole,
    Workplace,
)

__all__ = [
    "EmployeeHolderView",
    "RequesterAnchorView",
    "WorkplaceParentsView",
    "count_active_employees",
    "get_employee_holder",
    "get_recipient_user_ids",
    "get_user_id_for_employee",
    "get_user_workplace_anchor",
    "get_workplace_with_parents",
    "filter_active_user_ids",
]


def count_active_employees(session: Session, context: ScopeContext) -> int:
    """Scope-filtered count of active employees (dashboard contract).

    Applies the employee scope filter (permission AND scope coverage —
    constitution II); a caller without coverage counts zero.
    """
    from app.modules.user import employee_repository

    scope = employee_repository._employee_scope_filter(
        context, employee_repository.EMPLOYEE_READ_OPERATION
    )
    return int(
        session.scalar(
            select(func.count())
            .select_from(Employee)
            .where(scope, Employee.deleted_at.is_(None), Employee.is_active.is_(True))
        )
        or 0
    )


@dataclass(frozen=True)
class EmployeeHolderView:
    id: uuid.UUID
    display_name: str
    company_id: uuid.UUID
    complex_id: uuid.UUID
    workplace_id: uuid.UUID
    is_active: bool


def get_employee_holder(session: Session, employee_id: uuid.UUID) -> EmployeeHolderView | None:
    """Employee snapshot for asset assignment targets (or None if unknown)."""
    row = session.execute(
        select(Employee, Workplace, Complex, Company)
        .join(Workplace, Employee.workplace_id == Workplace.id)
        .join(Complex, Workplace.complex_id == Complex.id)
        .join(Company, Complex.company_id == Company.id)
        .where(Employee.id == employee_id)
    ).first()
    if row is None:
        return None
    employee, workplace, complex_, company = row
    display_name = f"{employee.first_name} {employee.last_name}".strip()
    return EmployeeHolderView(
        id=employee.id,
        display_name=display_name,
        company_id=company.id,
        complex_id=complex_.id,
        workplace_id=workplace.id,
        is_active=employee.deleted_at is None and employee.is_active,
    )


@dataclass(frozen=True)
class WorkplaceParentsView:
    id: uuid.UUID
    code: str
    name: str
    name_fa: str
    is_active: bool
    complex_id: uuid.UUID
    complex_code: str
    company_id: uuid.UUID


def get_workplace_with_parents(
    session: Session, workplace_id: uuid.UUID
) -> WorkplaceParentsView | None:
    """Workplace snapshot with parent complex/company ids (or None if unknown).

    Deactivated workplaces are still returned (historical scopes and existing
    warehouses must stay resolvable); callers decide whether to reject.
    """
    row = session.execute(
        select(Workplace, Complex, Company)
        .join(Complex, Workplace.complex_id == Complex.id)
        .join(Company, Complex.company_id == Company.id)
        .where(Workplace.id == workplace_id)
    ).first()
    if row is None:
        return None
    workplace, complex_, company = row
    return WorkplaceParentsView(
        id=workplace.id,
        code=workplace.code,
        name=workplace.name,
        name_fa=workplace.name_fa,
        is_active=workplace.deleted_at is None,
        complex_id=complex_.id,
        complex_code=complex_.code,
        company_id=company.id,
    )


@dataclass(frozen=True)
class RequesterAnchorView:
    company_id: uuid.UUID | None
    complex_id: uuid.UUID | None
    workplace_id: uuid.UUID | None


def get_user_workplace_anchor(session: Session, user_id: uuid.UUID) -> RequesterAnchorView | None:
    """Organizational anchor of a user via their employee record.

    Returns None when the user has no employee record (bootstrap identities) —
    callers anchor such requests as unanchored (global-scope-only visibility).
    """
    user = session.get(User, user_id)
    if user is None or user.employee_id is None:
        return None
    employee = session.get(Employee, user.employee_id)
    if employee is None:
        return None
    row = session.execute(
        select(Workplace, Complex, Company)
        .join(Complex, Workplace.complex_id == Complex.id)
        .join(Company, Complex.company_id == Company.id)
        .where(Workplace.id == employee.workplace_id)
    ).first()
    if row is None:
        return None
    workplace, complex_, company = row
    return RequesterAnchorView(
        company_id=company.id,
        complex_id=complex_.id,
        workplace_id=workplace.id,
    )


@dataclass(frozen=True)
class LoanRequesterView:
    """Identity + anchor facts the loan module needs for a signed-in user
    (contracts-only access per constitution VI)."""

    employee_id: uuid.UUID
    display_name: str
    first_name_fa: str | None
    last_name_fa: str | None
    company_id: uuid.UUID | None
    complex_id: uuid.UUID | None
    workplace_id: uuid.UUID
    is_active: bool


def get_loan_requester(session: Session, user_id: uuid.UUID) -> LoanRequesterView | None:
    """Resolve a signed-in user to their employee record for loan requests.

    Returns None when the user has no employee record or the employee has no
    workplace (bootstrap identities cannot hold loans).
    """
    user = session.get(User, user_id)
    if user is None or user.employee_id is None:
        return None
    employee = session.get(Employee, user.employee_id)
    if employee is None or employee.workplace_id is None:
        return None
    row = session.execute(
        select(Workplace, Complex, Company)
        .join(Complex, Workplace.complex_id == Complex.id)
        .join(Company, Complex.company_id == Company.id)
        .where(Workplace.id == employee.workplace_id)
    ).first()
    if row is None:
        return None
    workplace, complex_, company = row
    return LoanRequesterView(
        employee_id=employee.id,
        display_name=f"{employee.first_name} {employee.last_name}".strip(),
        first_name_fa=employee.first_name_fa,
        last_name_fa=employee.last_name_fa,
        company_id=company.id,
        complex_id=complex_.id,
        workplace_id=workplace.id,
        is_active=employee.is_active,
    )


def get_user_id_for_employee(session: Session, employee_id: uuid.UUID) -> uuid.UUID | None:
    """Linked account id of an employee (employee↔user is 1:1), or None when
    the employee has no user account (never the case for created pairs, but
    guards against partial data)."""
    return session.scalar(select(User.id).where(User.employee_id == employee_id))


def filter_active_user_ids(
    session: Session, user_ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    """The subset of the given ids whose accounts are active (delivery-time
    skip rule for deactivated recipients, spec edge case 2)."""
    if not user_ids:
        return []
    rows = session.execute(
        select(User.id).where(
            User.id.in_(user_ids), User.is_active.is_(True), User.deleted_at.is_(None)
        )
    ).all()
    return [row[0] for row in rows]


def get_recipient_user_ids(
    session: Session, permission_code: str, workplace_id: uuid.UUID | None
) -> list[uuid.UUID]:
    """Active users whose scope assignments cover the workplace for the
    permission code (implicit deny — research R3). Global/complex/workplace
    scopes union; deactivated users and those without the role holding the
    permission are excluded. ``workplace_id=None`` matches global-level
    assignments only (unanchored events notify globally-scoped holders)."""
    module, resource, operation = permission_code.split(":", 2)
    conditions: list[ColumnElement[bool]] = [
        User.is_active.is_(True),
        User.deleted_at.is_(None),
        Permission.code == permission_code,
        ScopeAssignment.module == module,
        ScopeAssignment.resource == resource,
        ScopeAssignment.operation == operation,
    ]
    if workplace_id is None:
        conditions.append(ScopeAssignment.level == ScopeLevel.GLOBAL)
    else:
        workplace = session.get(Workplace, workplace_id)
        if workplace is None:
            return []
        conditions.append(
            or_(
                ScopeAssignment.level == ScopeLevel.GLOBAL,
                (ScopeAssignment.level == ScopeLevel.COMPLEX)
                & (ScopeAssignment.complex_id == workplace.complex_id),
                (ScopeAssignment.level == ScopeLevel.WORKPLACE)
                & (ScopeAssignment.workplace_id == workplace.id),
            )
        )
    rows = session.execute(
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(RolePermission, RolePermission.role_id == UserRole.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .join(ScopeAssignment, ScopeAssignment.user_id == User.id)
        .where(*conditions)
        .distinct()
    ).all()
    return [row[0] for row in rows]
