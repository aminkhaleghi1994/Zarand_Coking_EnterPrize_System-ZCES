"""Public contract of the user module for other modules (constitution VI).

Cross-module consumers import ONLY from this file — never from
``models.py``/``repository.py``/services directly.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.user.models import Company, Complex, Workplace

__all__ = ["WorkplaceParentsView", "get_workplace_with_parents"]


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
