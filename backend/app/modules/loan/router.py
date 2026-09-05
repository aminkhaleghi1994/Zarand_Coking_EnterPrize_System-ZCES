"""Loan endpoints. Permission gates per code (`require_operation`); the
mandatory scope filter is applied by the repository/service. Request
listing/detail are ownership-aware: any authenticated user sees their own
requests, and `loan:request:read` widens visibility to covered units."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.pagination import Page
from app.common.scope import ScopeContext
from app.core.database import get_db
from app.modules.loan import repository, service
from app.modules.loan.schemas import (
    LoanPolicyCreateIn,
    LoanPolicyOut,
    LoanPolicyRetireIn,
    LoanPolicyUpdateIn,
    LoanRequestCreateIn,
    LoanRequestOut,
    LoanRequestTransitionIn,
)
from app.modules.user.dependencies import load_context, require_operation
from app.modules.user.schemas import PageParams

router = APIRouter(tags=["loans"])

require_policy_create = require_operation("loan:policy:create")
require_policy_read = require_operation("loan:policy:read")
require_policy_update = require_operation("loan:policy:update")
require_policy_retire = require_operation("loan:policy:retire")
require_request_activate = require_operation("loan:request:activate")
require_request_settle = require_operation("loan:request:settle")
require_request_cancel = require_operation("loan:request:cancel")


@router.get("/loan/policies", response_model=Page[LoanPolicyOut])
def get_policies(
    params: PageParams = Depends(),
    workplace_id: uuid.UUID | None = Query(default=None),
    year: int | None = Query(default=None, ge=1300, le=1500),
    include_retired: bool = Query(default=False),
    context: ScopeContext = Depends(require_policy_read),
    session: Session = Depends(get_db),
) -> Page[LoanPolicyOut]:
    return repository.list_policies(
        session,
        context,
        params,
        workplace_id=workplace_id,
        year=year,
        include_retired=include_retired,
    )


@router.post("/loan/policies", response_model=LoanPolicyOut, status_code=201)
def post_policy(
    payload: LoanPolicyCreateIn,
    context: ScopeContext = Depends(require_policy_create),
    session: Session = Depends(get_db),
) -> LoanPolicyOut:
    policy = service.create_policy(session, context, payload)
    return repository.policy_out(session, policy)


@router.get("/loan/policies/{policy_id}", response_model=LoanPolicyOut)
def get_policy_detail(
    policy_id: uuid.UUID,
    context: ScopeContext = Depends(require_policy_read),
    session: Session = Depends(get_db),
) -> LoanPolicyOut:
    policy = service.load_policy_for_read(session, context, policy_id)
    return repository.policy_out(session, policy)


@router.patch("/loan/policies/{policy_id}", response_model=LoanPolicyOut)
def patch_policy(
    policy_id: uuid.UUID,
    payload: LoanPolicyUpdateIn,
    context: ScopeContext = Depends(require_policy_update),
    session: Session = Depends(get_db),
) -> LoanPolicyOut:
    policy = service.update_policy(session, context, policy_id, payload)
    return repository.policy_out(session, policy)


@router.post("/loan/policies/{policy_id}/retire", response_model=LoanPolicyOut)
def post_policy_retire(
    policy_id: uuid.UUID,
    payload: LoanPolicyRetireIn,
    context: ScopeContext = Depends(require_policy_retire),
    session: Session = Depends(get_db),
) -> LoanPolicyOut:
    policy = service.retire_policy(session, context, policy_id, payload)
    return repository.policy_out(session, policy)


@router.get("/loan/requests", response_model=Page[LoanRequestOut])
def get_requests(
    params: PageParams = Depends(),
    type: str | None = Query(default=None, pattern="^(loan|guarantee)$"),
    status: str = Query(default="all", pattern="^(pending|active|settled|cancelled|all)$"),
    year: int | None = Query(default=None, ge=1300, le=1500),
    search: str | None = Query(default=None, max_length=200),
    context: ScopeContext = Depends(load_context),
    session: Session = Depends(get_db),
) -> Page[LoanRequestOut]:
    return repository.list_requests(
        session,
        context,
        service.requester_employee_id(session, context),
        params,
        type=type,
        status=status,
        year=year,
        search=search,
    )


@router.post("/loan/requests", response_model=LoanRequestOut, status_code=201)
def post_request(
    payload: LoanRequestCreateIn,
    context: ScopeContext = Depends(load_context),
    session: Session = Depends(get_db),
) -> LoanRequestOut:
    """Self-service submission (own request only — contracts, research R6)."""
    request = service.submit_request(session, context, payload)
    return repository.request_out(session, request)


@router.get("/loan/requests/{request_id}", response_model=LoanRequestOut)
def get_request_detail(
    request_id: uuid.UUID,
    context: ScopeContext = Depends(load_context),
    session: Session = Depends(get_db),
) -> LoanRequestOut:
    request = service.load_request_for_read(session, context, request_id)
    return repository.request_out(session, request)


@router.post("/loan/requests/{request_id}/activate", response_model=LoanRequestOut)
def post_request_activate(
    request_id: uuid.UUID,
    payload: LoanRequestTransitionIn,
    context: ScopeContext = Depends(require_request_activate),
    session: Session = Depends(get_db),
) -> LoanRequestOut:
    request = service.activate_request(session, context, request_id, payload.version)
    return repository.request_out(session, request)


@router.post("/loan/requests/{request_id}/settle", response_model=LoanRequestOut)
def post_request_settle(
    request_id: uuid.UUID,
    payload: LoanRequestTransitionIn,
    context: ScopeContext = Depends(require_request_settle),
    session: Session = Depends(get_db),
) -> LoanRequestOut:
    request = service.settle_request(session, context, request_id, payload.version)
    return repository.request_out(session, request)


@router.post("/loan/requests/{request_id}/cancel", response_model=LoanRequestOut)
def post_request_cancel(
    request_id: uuid.UUID,
    payload: LoanRequestTransitionIn,
    context: ScopeContext = Depends(require_request_cancel),
    session: Session = Depends(get_db),
) -> LoanRequestOut:
    request = service.cancel_request(session, context, request_id, payload.version)
    return repository.request_out(session, request)
