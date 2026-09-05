"""Item-request services (Phase 5): composition, decisions, fulfillment.

Visibility/authorization model (research R5):
- create + own-view: active authentication, ownership-scoped (requested_by);
- decide/fulfill/scope-list: `warehouse:request:*` permissions + scope
  coverage over the request's workplace anchor (or global coverage for
  unanchored requests).
Fulfillment decrements stock through the module's published contract
(`apply_fulfillment_issue`) inside ONE transaction owned by this service.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.common.scope import ScopeContext, ScopeTarget, can
from app.core.errors import (
    AUTHORIZATION_DENIED,
    BUSINESS_RULE_VIOLATION,
    STALE_VERSION,
    AppError,
    validation_error,
)
from app.modules.audit.contracts import write_audit
from app.modules.notification import contracts as notification_contracts
from app.modules.user import contracts as user_contracts
from app.modules.warehouse import repository, request_repository
from app.modules.warehouse.models import ItemRequest, RequestStatus, Warehouse
from app.modules.warehouse.schemas import (
    DecisionIn,
    FulfillIn,
    RequestCreateIn,
    format_quantity,
    quantize_quantity,
)

_REQUEST_READ = "warehouse:request:read"
_REQUEST_DECIDE = "warehouse:request:decide"
_REQUEST_FULFILL = "warehouse:request:fulfill"


def _require_request_scope(context: ScopeContext, operation: str, request: ItemRequest) -> None:
    """Scope gate over the request's workplace anchor; unanchored requests
    (requesters without an employee record) require global coverage."""
    if request.workplace_id is None:
        target = ScopeTarget()
    else:
        target = ScopeTarget(
            complex_id=str(request.complex_id) if request.complex_id else None,
            workplace_id=str(request.workplace_id),
        )
    if not can(context, operation, target):
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)


def _request_snapshot(request: ItemRequest, lines: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": str(request.id),
        "requested_by": str(request.requested_by),
        "purpose_description": request.purpose_description,
        "status": str(request.status.value),
        "version": request.version,
        "lines": lines,
    }


def _line_snapshot(line, item) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {
        "line_id": str(line.id),
        "item_id": str(item.id),
        "quantity": format_quantity(line.quantity),
        "note": line.note,
    }


def create_request(
    session: Session, context: ScopeContext, payload: RequestCreateIn
) -> ItemRequest:
    """Self-service composition (FR-001..FR-003): any active authenticated
    user raises requests for themselves; the requester is immutable."""
    caller = uuid.UUID(context.user_id)
    purpose = payload.purpose_description.strip()
    if not purpose:
        raise validation_error("Purpose description is required")

    seen_items: set[uuid.UUID] = set()
    validated: list[tuple[uuid.UUID, Decimal, str | None]] = []
    for index, line in enumerate(payload.lines):
        quantity = quantize_quantity(line.quantity)
        if quantity <= 0:
            raise validation_error(
                "Line quantity must be greater than zero",
                details={"line_index": index, "field": "quantity"},
            )
        item = repository.get_item(session, line.item_id)
        if item is None or item.deleted_at is not None:
            raise validation_error(
                "Line references an unknown or retired item",
                details={"line_index": index, "field": "item_id"},
            )
        if line.item_id in seen_items:
            raise validation_error(
                "The same item appears on more than one line",
                details={"line_index": index, "field": "item_id"},
            )
        seen_items.add(line.item_id)
        validated.append((line.item_id, quantity, line.note))

    anchor = user_contracts.get_user_workplace_anchor(session, caller)
    request = request_repository.create_request(
        session,
        requested_by=caller,
        purpose_description=purpose,
        company_id=anchor.company_id if anchor else None,
        complex_id=anchor.complex_id if anchor else None,
        workplace_id=anchor.workplace_id if anchor else None,
        actor_user_id=caller,
    )
    line_snapshots: list[dict[str, object]] = []
    for item_id, quantity, note in validated:
        created_line = request_repository.create_request_line(
            session,
            request_id=request.id,
            item_id=item_id,
            quantity=quantity,
            note=note,
            actor_user_id=caller,
        )
        item = repository.get_item(session, item_id)
        assert item is not None
        line_snapshots.append(_line_snapshot(created_line, item))

    write_audit(
        session,
        action="REQUEST_CREATED",
        entity_type="item_request",
        entity_id=request.id,
        actor_user_id=caller,
        after=_request_snapshot(request, line_snapshots),
        critical=True,
    )
    notification_contracts.record_event(
        session,
        "ItemRequestCreated",
        {
            "entity_id": str(request.id),
            "actor_user_id": str(caller),
            "title": "request_created",
            "workplace_id": str(request.workplace_id) if request.workplace_id else None,
            "requester_user_id": str(caller),
            "line_count": len(line_snapshots),
            "audience": {
                "users": [str(caller)],
                "scope": {
                    "permission": _REQUEST_DECIDE,
                    "workplace_id": str(request.workplace_id) if request.workplace_id else None,
                },
            },
        },
        actor_user_id=caller,
    )
    session.commit()
    return request


def _load_request_for_decision(
    session: Session, context: ScopeContext, request_id: uuid.UUID, operation: str
) -> ItemRequest:
    request = request_repository.get_request(session, request_id)
    if request is None:
        # No existence leak: a missing request is indistinguishable from an
        # out-of-scope one for non-global callers (spec US2/AC5).
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)
    _require_request_scope(context, operation, request)
    return request


def decide_request(
    session: Session,
    context: ScopeContext,
    request_id: uuid.UUID,
    payload: DecisionIn,
    *,
    approve: bool,
) -> ItemRequest:
    request = _load_request_for_decision(session, context, request_id, _REQUEST_DECIDE)
    if request.version != payload.version:
        raise AppError(
            STALE_VERSION,
            "This record changed since you opened it — refresh and retry",
            status_code=409,
        )
    if request.status.value != "pending":
        raise AppError(
            BUSINESS_RULE_VIOLATION,
            "Only pending requests can be approved or rejected",
            status_code=422,
        )

    lines = request_repository.get_request_lines(session, request.id)
    line_snapshots = [_line_snapshot(line, item) for line, item in lines]
    before = _request_snapshot(request, line_snapshots)
    request.status = RequestStatus.APPROVED if approve else RequestStatus.REJECTED
    request.decision_note = payload.note
    request.decided_by = uuid.UUID(context.user_id)
    request.decided_at = datetime.now(UTC)
    request.updated_by = uuid.UUID(context.user_id)
    request.version += 1
    session.add(request)

    write_audit(
        session,
        action="REQUEST_APPROVED" if approve else "REQUEST_REJECTED",
        entity_type="item_request",
        entity_id=request.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after=_request_snapshot(request, line_snapshots),
        critical=True,
    )
    audience: dict[str, object] = {"users": [str(request.requested_by)]}
    if approve:
        audience["scope"] = {
            "permission": _REQUEST_FULFILL,
            "workplace_id": str(request.workplace_id) if request.workplace_id else None,
        }
    notification_contracts.record_event(
        session,
        "ItemRequestApproved" if approve else "ItemRequestRejected",
        {
            "entity_id": str(request.id),
            "actor_user_id": str(uuid.UUID(context.user_id)),
            "title": "request_approved" if approve else "request_rejected",
            "workplace_id": str(request.workplace_id) if request.workplace_id else None,
            "requester_user_id": str(request.requested_by),
            "decision_note": payload.note,
            "audience": audience,
        },
        actor_user_id=uuid.UUID(context.user_id),
    )
    session.commit()
    return request


def fulfill_request(
    session: Session, context: ScopeContext, request_id: uuid.UUID, payload: FulfillIn
) -> ItemRequest:
    from app.modules.warehouse import contracts

    request = _load_request_for_decision(session, context, request_id, _REQUEST_FULFILL)
    if request.version != payload.version:
        raise AppError(
            STALE_VERSION,
            "This record changed since you opened it — refresh and retry",
            status_code=409,
        )
    if request.status.value != "approved":
        raise AppError(
            BUSINESS_RULE_VIOLATION,
            "Only approved requests can be fulfilled",
            status_code=422,
        )

    lines = request_repository.get_request_lines(session, request.id)
    lines_by_id = {line.id: (line, item) for line, item in lines}
    picks: dict[uuid.UUID, uuid.UUID] = {}
    for fulfill_line in payload.lines:
        if fulfill_line.line_id not in lines_by_id:
            raise validation_error(
                "Fulfillment payload references an unknown line",
                details={"line_id": str(fulfill_line.line_id)},
            )
        if fulfill_line.line_id in picks:
            raise validation_error(
                "A line appears more than once in the fulfillment payload",
                details={"line_id": str(fulfill_line.line_id)},
            )
        picks[fulfill_line.line_id] = fulfill_line.placement_id
    if set(picks) != set(lines_by_id):
        raise validation_error("Fulfillment must cover every line exactly once")

    line_snapshots = [_line_snapshot(line, item) for line, item in lines]
    before = _request_snapshot(request, line_snapshots)
    movements: list[dict[str, object]] = []
    for line, item in lines:
        placement_id = picks[line.id]
        bundle = repository.get_placement_bundle(session, placement_id)
        if bundle is None:
            raise validation_error(
                "Selected stock placement was not found",
                details={"line_id": str(line.id), "placement_id": str(placement_id)},
            )
        placement, _placement_item, shelf, warehouse = bundle
        if placement.item_id != line.item_id:
            raise validation_error(
                "The selected placement holds a different item than the line",
                details={"line_id": str(line.id)},
            )
        if shelf.deleted_at is not None:
            raise AppError(
                BUSINESS_RULE_VIOLATION,
                "The selected placement is on a retired shelf",
                status_code=422,
                details={"line_id": str(line.id)},
            )
        _require_stock_placement_scope(context, _REQUEST_FULFILL, warehouse)
        movement = contracts.apply_fulfillment_issue(
            session,
            placement_id=placement.id,
            quantity=line.quantity,
            actor_user_id=uuid.UUID(context.user_id),
            reason=f"Request {str(request.id)[:8]} · {item.name}",
        )
        movements.append(
            {
                "line_id": str(line.id),
                "placement_id": str(placement.id),
                "movement_id": str(movement.id),
                "quantity_before": format_quantity(placement.quantity + movement.quantity_delta),
                "quantity_after": format_quantity(movement.resulting_quantity),
            }
        )

    request.status = RequestStatus.FULFILLED
    request.fulfilled_at = datetime.now(UTC)
    request.updated_by = uuid.UUID(context.user_id)
    request.version += 1
    session.add(request)

    write_audit(
        session,
        action="REQUEST_FULFILLED",
        entity_type="item_request",
        entity_id=request.id,
        actor_user_id=uuid.UUID(context.user_id),
        before=before,
        after={**_request_snapshot(request, line_snapshots), "movements": movements},
        critical=True,
    )
    notification_contracts.record_event(
        session,
        "ItemRequestFulfilled",
        {
            "entity_id": str(request.id),
            "actor_user_id": str(uuid.UUID(context.user_id)),
            "title": "request_fulfilled",
            "workplace_id": str(request.workplace_id) if request.workplace_id else None,
            "requester_user_id": str(request.requested_by),
            "line_count": len(movements),
            "audience": {"users": [str(request.requested_by)]},
        },
        actor_user_id=uuid.UUID(context.user_id),
    )
    session.commit()
    return request


def _require_stock_placement_scope(
    context: ScopeContext, operation: str, warehouse: Warehouse
) -> None:
    if not can(
        context,
        operation,
        ScopeTarget(
            complex_id=str(warehouse.complex_id),
            workplace_id=str(warehouse.workplace_id),
        ),
    ):
        raise AppError(AUTHORIZATION_DENIED, "Access denied", status_code=403)


__all__ = [
    "create_request",
    "decide_request",
    "fulfill_request",
]
