"""Loan business logic: policy management, the exact §19 validation cascade,
and version-guarded lifecycle transitions.

Transaction discipline (research R2): submissions lock the governing policy
row with `SELECT … FOR UPDATE`, so concurrent submissions at a count or
amount boundary resolve to exactly one winner. Every lifecycle action is
audited with masked before/after snapshots (§21: loan amounts are masked).
"""

import uuid
from datetime import UTC, datetime
from typing import NoReturn

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.jalali import current_jalali_year
from app.common.scope import ScopeContext, ScopeTarget, can
from app.core.errors import (
    BUSINESS_RULE_VIOLATION,
    STALE_VERSION,
    AppError,
    duplicate_resource,
    not_found,
    validation_error,
)
from app.modules.audit.contracts import write_audit
from app.modules.loan import repository
from app.modules.loan.models import LoanPolicy, LoanRequest, LoanStatus, LoanType
from app.modules.loan.schemas import (
    LoanPolicyCreateIn,
    LoanPolicyRetireIn,
    LoanPolicyUpdateIn,
    LoanRequestCreateIn,
    format_money,
    parse_money,
)
from app.modules.user import contracts as user_contracts
from app.modules.user.models import Workplace

STALE_MESSAGE = "This record changed since you opened it — refresh and retry"
MIN_YEAR = 1300
MAX_YEAR = 1500

_POLICY_CREATE = "loan:policy:create"
_POLICY_UPDATE = "loan:policy:update"
_POLICY_RETIRE = "loan:policy:retire"
_REQUEST_ACTIVATE = "loan:request:activate"
_REQUEST_SETTLE = "loan:request:settle"
_REQUEST_CANCEL = "loan:request:cancel"


def _policy_snapshot(policy: LoanPolicy, workplace: Workplace | None) -> dict[str, object]:
    return {
        "id": str(policy.id),
        "workplace_id": str(policy.workplace_id),
        "year": policy.year,
        "max_loan_amount": format_money(policy.max_loan_amount),
        "max_guarantee_amount": format_money(policy.max_guarantee_amount),
        "max_request_count_per_year": policy.max_request_count_per_year,
        "max_request_count_lifetime": policy.max_request_count_lifetime,
        "is_active": policy.is_active,
        "workplace_code": workplace.code if workplace else None,
    }


def _require_workplace_scope(
    context: ScopeContext, operation: str, workplace_id: uuid.UUID
) -> None:
    if not can(context, operation, ScopeTarget(workplace_id=str(workplace_id))):
        raise AppError("AUTHORIZATION_DENIED", "Access denied", status_code=403)


_POLICY_READ = "loan:policy:read"


def load_policy_for_read(
    session: Session, context: ScopeContext, policy_id: uuid.UUID
) -> LoanPolicy:
    policy = repository.get_policy(session, policy_id)
    if policy is None:
        raise not_found("Loan policy not found")
    if not can(context, _POLICY_READ, ScopeTarget(workplace_id=str(policy.workplace_id))):
        raise not_found("Loan policy not found")
    return policy


def requester_employee_id(session: Session, context: ScopeContext) -> uuid.UUID | None:
    requester = user_contracts.get_loan_requester(session, uuid.UUID(context.user_id))
    return requester.employee_id if requester else None


def load_request_for_read(
    session: Session, context: ScopeContext, request_id: uuid.UUID
) -> LoanRequest:
    """Ownership-OR-scope detail access (FR-013): the owner always sees their
    request; `loan:request:read` holders see covered units. Everyone else
    gets the standard not-found (no existence leak)."""
    request = repository.get_request(session, request_id)
    if request is None:
        raise not_found("Loan request not found")
    if request.created_by == uuid.UUID(context.user_id):
        return request
    if can(
        context,
        repository.REQUEST_READ_OPERATION,
        ScopeTarget(
            complex_id=str(request.complex_id) if request.complex_id else None,
            workplace_id=str(request.workplace_id),
        ),
    ):
        return request
    raise not_found("Loan request not found")


def _get_workplace(session: Session, workplace_id: uuid.UUID) -> Workplace | None:
    return session.get(Workplace, workplace_id)


# --- Policies (US1) ---


def create_policy(
    session: Session, context: ScopeContext, payload: LoanPolicyCreateIn
) -> LoanPolicy:
    workplace = _get_workplace(session, payload.workplace_id)
    if workplace is None:
        raise not_found("Workplace not found")
    _require_workplace_scope(context, _POLICY_CREATE, payload.workplace_id)
    if repository.get_policy_by_workplace_year(session, payload.workplace_id, payload.year):
        raise duplicate_resource(
            "An active policy already exists for this workplace and year"
        )
    policy = LoanPolicy(
        workplace_id=payload.workplace_id,
        year=payload.year,
        max_loan_amount=parse_money(payload.max_loan_amount),
        max_guarantee_amount=parse_money(payload.max_guarantee_amount),
        max_request_count_per_year=payload.max_request_count_per_year,
        max_request_count_lifetime=payload.max_request_count_lifetime,
        created_by=uuid.UUID(context.user_id),
        updated_by=uuid.UUID(context.user_id),
    )
    session.add(policy)
    session.flush()
    write_audit(
        session,
        action="LOAN_POLICY_CREATED",
        entity_type="loan_policy",
        entity_id=policy.id,
        actor_user_id=uuid.UUID(context.user_id),
        after=_policy_snapshot(policy, workplace),
        critical=True,
    )
    session.commit()
    session.refresh(policy)
    return policy


def update_policy(
    session: Session, context: ScopeContext, policy_id: uuid.UUID, payload: LoanPolicyUpdateIn
) -> LoanPolicy:
    policy = repository.get_policy(session, policy_id)
    if policy is None:
        raise not_found("Loan policy not found")
    _require_workplace_scope(context, _POLICY_UPDATE, policy.workplace_id)
    if policy.version != payload.version:
        raise AppError(STALE_VERSION, STALE_MESSAGE, status_code=409)
    workplace = _get_workplace(session, policy.workplace_id)
    before = _policy_snapshot(policy, workplace)

    updates = payload.model_dump(exclude={"version"}, exclude_unset=True)
    if "year" in updates and updates["year"] is not None and updates["year"] != policy.year:
        if repository.get_policy_by_workplace_year(
            session, policy.workplace_id, updates["year"], exclude_id=policy.id
        ):
            raise duplicate_resource(
                "An active policy already exists for this workplace and year"
            )
        policy.year = updates["year"]
    if "max_loan_amount" in updates and updates["max_loan_amount"] is not None:
        policy.max_loan_amount = parse_money(updates["max_loan_amount"])
    if "max_guarantee_amount" in updates and updates["max_guarantee_amount"] is not None:
        policy.max_guarantee_amount = parse_money(updates["max_guarantee_amount"])
    if (
        "max_request_count_per_year" in updates
        and updates["max_request_count_per_year"] is not None
    ):
        policy.max_request_count_per_year = updates["max_request_count_per_year"]
    if (
        "max_request_count_lifetime" in updates
        and updates["max_request_count_lifetime"] is not None
    ):
        policy.max_request_count_lifetime = updates["max_request_count_lifetime"]
    if "is_active" in updates and updates["is_active"] is not None:
        policy.is_active = updates["is_active"]
    policy.updated_by = uuid.UUID(context.user_id)
    policy.version += 1
    session.add(policy)
    session.flush()
    write_audit(
        session,
        action="LOAN_POLICY_UPDATED",
        entity_type="loan_policy",
        entity_id=policy.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after=_policy_snapshot(policy, workplace),
        critical=True,
    )
    session.commit()
    session.refresh(policy)
    return policy


def retire_policy(
    session: Session, context: ScopeContext, policy_id: uuid.UUID, payload: LoanPolicyRetireIn
) -> LoanPolicy:
    policy = repository.get_policy(session, policy_id)
    if policy is None:
        raise not_found("Loan policy not found")
    _require_workplace_scope(context, _POLICY_RETIRE, policy.workplace_id)
    if policy.version != payload.version:
        raise AppError(STALE_VERSION, STALE_MESSAGE, status_code=409)
    workplace = _get_workplace(session, policy.workplace_id)
    before = _policy_snapshot(policy, workplace)
    policy.deleted_at = datetime.now(tz=UTC)
    policy.updated_by = uuid.UUID(context.user_id)
    policy.version += 1
    session.add(policy)
    session.flush()
    write_audit(
        session,
        action="LOAN_POLICY_RETIRED",
        entity_type="loan_policy",
        entity_id=policy.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        critical=True,
    )
    session.commit()
    session.refresh(policy)
    return policy


# --- Requests (US2/US3) ---


def _request_snapshot(request: LoanRequest) -> dict[str, object]:
    return {
        "id": str(request.id),
        "employee_id": str(request.employee_id),
        "workplace_id": str(request.workplace_id),
        "type": str(request.type.value),
        "amount": format_money(request.amount),
        "year": request.year,
        "status": str(request.status.value),
        "settled_at": request.settled_at.isoformat() if request.settled_at else None,
    }


def _policy_for(session: Session, workplace_id: uuid.UUID, year: int) -> LoanPolicy | None:
    """Fetch the governing policy row with a row lock so concurrent
    submissions serialize (research R2)."""
    return session.scalars(
        select(LoanPolicy)
        .where(
            LoanPolicy.workplace_id == workplace_id,
            LoanPolicy.year == year,
            LoanPolicy.deleted_at.is_(None),
        )
        .with_for_update()
    ).first()


def _refuse(rule: str, **details: object) -> NoReturn:
    raise AppError(
        BUSINESS_RULE_VIOLATION,
        "Loan policy validation failed",
        details={"rule": rule, **details},
        status_code=422,
    )


def submit_request(
    session: Session, context: ScopeContext, payload: LoanRequestCreateIn
) -> LoanRequest:
    """Self-service submission validated against the requester's workplace
    policy in the exact §19 order (FR-005)."""
    requester = user_contracts.get_loan_requester(session, uuid.UUID(context.user_id))
    if requester is None:
        raise not_found("No employee record is linked to this account")
    if not requester.is_active:
        raise validation_error("The employee is deactivated")

    now = datetime.now(tz=UTC)
    year = current_jalali_year(now)

    policy = _policy_for(session, requester.workplace_id, year)
    if policy is None or not policy.is_active:
        _refuse(
            "no_policy",
            workplace_id=str(requester.workplace_id),
            year=year,
        )

    # §19 order — first failing rule wins (FR-005).
    lifetime = repository.count_requests_lifetime(session, requester.employee_id)
    if lifetime >= policy.max_request_count_lifetime:
        _refuse(
            "lifetime_count",
            used=lifetime,
            limit=policy.max_request_count_lifetime,
        )
    yearly = repository.count_requests_year(session, requester.employee_id, year)
    if yearly >= policy.max_request_count_per_year:
        _refuse(
            "yearly_count",
            used=yearly,
            limit=policy.max_request_count_per_year,
        )
    loan_type = LoanType(payload.type)
    if loan_type is LoanType.LOAN:
        active_sum = repository.sum_active_amount(
            session, requester.employee_id, year, LoanType.LOAN.value
        )
        if active_sum + parse_money(payload.amount) > policy.max_loan_amount:
            _refuse(
                "loan_cap",
                current_active=format_money(active_sum),
                limit=format_money(policy.max_loan_amount),
                requested=payload.amount,
            )
    else:
        active_sum = repository.sum_active_amount(
            session, requester.employee_id, year, LoanType.GUARANTEE.value
        )
        if active_sum + parse_money(payload.amount) > policy.max_guarantee_amount:
            _refuse(
                "guarantee_cap",
                current_active=format_money(active_sum),
                limit=format_money(policy.max_guarantee_amount),
                requested=payload.amount,
            )

    request = LoanRequest(
        employee_id=requester.employee_id,
        workplace_id=requester.workplace_id,
        complex_id=requester.complex_id,
        company_id=requester.company_id,
        type=loan_type,
        amount=parse_money(payload.amount),
        year=year,
        status=LoanStatus.PENDING,
        created_by=uuid.UUID(context.user_id),
    )
    session.add(request)
    session.flush()
    write_audit(
        session,
        action="LOAN_REQUEST_CREATED",
        entity_type="loan_request",
        entity_id=request.id,
        actor_user_id=uuid.UUID(context.user_id),
        after=_request_snapshot(request),
        critical=True,
    )
    session.commit()
    session.refresh(request)
    return request


def _load_request_for_transition(
    session: Session, context: ScopeContext, operation: str, request_id: uuid.UUID
) -> LoanRequest:
    request = repository.get_request(session, request_id)
    if request is None:
        raise not_found("Loan request not found")
    in_scope = can(
        context,
        operation,
        ScopeTarget(
            complex_id=str(request.complex_id) if request.complex_id else None,
            workplace_id=str(request.workplace_id),
        ),
    )
    if not in_scope:
        raise not_found("Loan request not found")
    return request


def activate_request(
    session: Session, context: ScopeContext, request_id: uuid.UUID, version: int
) -> LoanRequest:
    request = _load_request_for_transition(session, context, _REQUEST_ACTIVATE, request_id)
    if request.version != version:
        raise AppError(STALE_VERSION, STALE_MESSAGE, status_code=409)
    if request.status is not LoanStatus.PENDING:
        raise AppError(
            BUSINESS_RULE_VIOLATION,
            "Only pending requests can be activated",
            status_code=422,
        )
    holder = user_contracts.get_employee_holder(session, request.employee_id)
    if holder is None or not holder.is_active:
        raise AppError(
            BUSINESS_RULE_VIOLATION,
            "The requesting employee is deactivated",
            status_code=422,
        )
    before = _request_snapshot(request)
    request.status = LoanStatus.ACTIVE
    request.version += 1
    session.add(request)
    session.flush()
    write_audit(
        session,
        action="LOAN_REQUEST_ACTIVATED",
        entity_type="loan_request",
        entity_id=request.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after=_request_snapshot(request),
        critical=True,
    )
    session.commit()
    session.refresh(request)
    return request


def settle_request(
    session: Session, context: ScopeContext, request_id: uuid.UUID, version: int
) -> LoanRequest:
    request = _load_request_for_transition(session, context, _REQUEST_SETTLE, request_id)
    if request.version != version:
        raise AppError(STALE_VERSION, STALE_MESSAGE, status_code=409)
    if request.status is not LoanStatus.ACTIVE:
        raise AppError(
            BUSINESS_RULE_VIOLATION,
            "Only active requests can be settled",
            status_code=422,
        )
    before = _request_snapshot(request)
    request.status = LoanStatus.SETTLED
    request.settled_at = datetime.now(tz=UTC)
    request.version += 1
    session.add(request)
    session.flush()
    write_audit(
        session,
        action="LOAN_REQUEST_SETTLED",
        entity_type="loan_request",
        entity_id=request.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after=_request_snapshot(request),
        critical=True,
    )
    session.commit()
    session.refresh(request)
    return request


def cancel_request(
    session: Session, context: ScopeContext, request_id: uuid.UUID, version: int
) -> LoanRequest:
    request = _load_request_for_transition(session, context, _REQUEST_CANCEL, request_id)
    if request.version != version:
        raise AppError(STALE_VERSION, STALE_MESSAGE, status_code=409)
    if request.status not in (LoanStatus.PENDING, LoanStatus.ACTIVE):
        raise AppError(
            BUSINESS_RULE_VIOLATION,
            "Settled requests cannot be cancelled",
            status_code=422,
        )
    before = _request_snapshot(request)
    request.status = LoanStatus.CANCELLED
    request.version += 1
    session.add(request)
    session.flush()
    write_audit(
        session,
        action="LOAN_REQUEST_CANCELLED",
        entity_type="loan_request",
        entity_id=request.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after=_request_snapshot(request),
        critical=True,
    )
    session.commit()
    session.refresh(request)
    return request
