"""Public contract of the user module for other modules (constitution VI).

Cross-module consumers import ONLY from this file — never from
``models.py``/``repository.py``/services directly.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.user.models import Company, Complex, Employee, User, Workplace

__all__ = [
    "EmployeeHolderView",
    "RequesterAnchorView",
    "WorkplaceParentsView",
    "get_employee_holder",
    "get_user_workplace_anchor",
    "get_workplace_with_parents",
]


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
