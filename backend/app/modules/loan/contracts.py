"""Public contract of the loan module for other modules (constitution VI).

Cross-module consumers import ONLY from this file — never from
``models.py``/``repository.py``/services directly. Aggregates apply the
module's own scope filter (constitution II).
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.scope import ScopeContext
from app.modules.loan import repository
from app.modules.loan.models import LoanPolicy, LoanRequest, LoanStatus, LoanType
from app.modules.user.models import Workplace

__all__ = [
    "LoanReportRow",
    "count_active_loans",
    "loans_status_counts",
    "report_loan_rows",
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


@dataclass(frozen=True)
class LoanReportRow:
    """Per-workplace + Jalali-year aggregate for the loans report (US2)."""

    workplace_id: uuid.UUID
    workplace_code: str
    workplace_name: str
    workplace_name_fa: str
    year: int
    requests_total: int
    requests_pending: int
    requests_active: int
    requests_settled: int
    requests_cancelled: int
    active_loan_commitment: Decimal
    active_guarantee_commitment: Decimal
    policy_max_loan: Decimal | None
    policy_max_guarantee: Decimal | None


def report_loan_rows(
    session: Session,
    context: ScopeContext,
    *,
    year: int | None = None,
    workplace_id: uuid.UUID | None = None,
) -> list[LoanReportRow]:
    """Scope-filtered per-workplace/year loan aggregates (active rows).

    Commitment sums include only ACTIVE requests (per requirements §19,
    settled/cancelled free the caps); policy caps come from the active
    policy for that workplace+year when one exists.
    """
    scope = repository._loan_scope_filter(context, repository.REQUEST_READ_OPERATION)

    conditions = [scope, LoanRequest.deleted_at.is_(None)]
    if year is not None:
        conditions.append(LoanRequest.year == year)
    if workplace_id is not None:
        conditions.append(LoanRequest.workplace_id == workplace_id)

    pending = func.count().filter(LoanRequest.status == LoanStatus.PENDING)
    active = func.count().filter(LoanRequest.status == LoanStatus.ACTIVE)
    settled = func.count().filter(LoanRequest.status == LoanStatus.SETTLED)
    cancelled = func.count().filter(LoanRequest.status == LoanStatus.CANCELLED)
    loan_sum = func.coalesce(
        func.sum(LoanRequest.amount).filter(
            LoanRequest.status == LoanStatus.ACTIVE,
            LoanRequest.type == LoanType.LOAN,
        ),
        0,
    )
    guarantee_sum = func.coalesce(
        func.sum(LoanRequest.amount).filter(
            LoanRequest.status == LoanStatus.ACTIVE,
            LoanRequest.type == LoanType.GUARANTEE,
        ),
        0,
    )

    rows = session.execute(
        select(
            LoanRequest.workplace_id,
            LoanRequest.year,
            func.count(),
            pending,
            active,
            settled,
            cancelled,
            loan_sum,
            guarantee_sum,
        )
        .where(*conditions)
        .group_by(LoanRequest.workplace_id, LoanRequest.year)
    ).all()

    policies: dict[tuple[uuid.UUID, int], tuple[Decimal, Decimal]] = {}
    if rows:
        workplace_ids = {row[0] for row in rows}
        policy_rows = session.scalars(
            select(LoanPolicy)
            .where(
                LoanPolicy.workplace_id.in_(workplace_ids),
                LoanPolicy.is_active.is_(True),
                LoanPolicy.deleted_at.is_(None),
            )
        ).all()
        policies = {
            (policy.workplace_id, policy.year): (
                policy.max_loan_amount,
                policy.max_guarantee_amount,
            )
            for policy in policy_rows
        }

    projected: list[LoanReportRow] = []
    for workplace, request_year, total, p, a, s, c, loan_commitment, guarantee_commitment in rows:
        workplace_row = session.get(Workplace, workplace)
        if workplace_row is None:  # pragma: no cover - FK integrity
            continue
        max_loan, max_guarantee = policies.get((workplace, request_year), (None, None))
        projected.append(
            LoanReportRow(
                workplace_id=workplace,
                workplace_code=workplace_row.code,
                workplace_name=workplace_row.name,
                workplace_name_fa=workplace_row.name_fa,
                year=request_year,
                requests_total=int(total),
                requests_pending=int(p),
                requests_active=int(a),
                requests_settled=int(s),
                requests_cancelled=int(c),
                active_loan_commitment=Decimal(loan_commitment or 0),
                active_guarantee_commitment=Decimal(guarantee_commitment or 0),
                policy_max_loan=max_loan,
                policy_max_guarantee=max_guarantee,
            )
        )
    projected.sort(key=lambda row: (row.workplace_code, -row.year))
    return projected
