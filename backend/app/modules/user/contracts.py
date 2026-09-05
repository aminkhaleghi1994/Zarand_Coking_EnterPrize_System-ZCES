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
    "RequesterAnchorView",
    "WorkplaceParentsView",
    "get_user_workplace_anchor",
    "get_workplace_with_parents",
]


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
