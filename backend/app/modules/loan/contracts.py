"""Public contract of the loan module for other modules (constitution VI).

Cross-module consumers import ONLY from this file — never from
``models.py``/``repository.py``/services directly. Aggregates apply the
module's own scope filter (constitution II).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.scope import ScopeContext
from app.modules.loan import repository
from app.modules.loan.models import LoanRequest, LoanStatus

__all__ = [
    "count_active_loans",
    "loans_status_counts",
]


def count_active_loans(session: Session, context: ScopeContext) -> int:
    scope = repository._loan_scope_filter(context, repository.REQUEST_READ_OPERATION)
    return int(
        session.scalar(
            select(func.count())
            .select_from(LoanRequest)
            .where(
                scope,
                LoanRequest.status == LoanStatus.ACTIVE,
                LoanRequest.deleted_at.is_(None),
            )
        )
        or 0
    )


def loans_status_counts(session: Session, context: ScopeContext) -> dict[str, int]:
    """Counts by status over the caller's scope (active rows only)."""
    scope = repository._loan_scope_filter(context, repository.REQUEST_READ_OPERATION)
    rows = session.execute(
        select(LoanRequest.status, func.count())
        .where(scope, LoanRequest.deleted_at.is_(None))
        .group_by(LoanRequest.status)
    ).all()
    counts = {status.value: 0 for status in LoanStatus}
    for status, count in rows:
        counts[status.value] = int(count)
    return counts
