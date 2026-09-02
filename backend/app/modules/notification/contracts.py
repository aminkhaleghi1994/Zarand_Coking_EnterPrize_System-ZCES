"""Public capture API for other modules (constitution VI): emitters call
these inside their own transaction so outbox rows commit or roll back with
the business change. Critical events additionally write their in-app
notification rows in the same transaction (§20 + research R4)."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.tracing import get_trace_id
from app.modules.notification.models import EVENT_TYPES, EventOutbox, Notification

CRITICAL_EVENTS: frozenset[str] = frozenset({"InventoryLowStock"})


def record_event(
    session: Session,
    event_type: str,
    payload: dict[str, Any],
    actor_user_id: uuid.UUID | None,
) -> EventOutbox:
    """Append an EventOutbox row in the caller's transaction (US1)."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown event type: {event_type}")
    event = EventOutbox(
        event_type=event_type,
        payload=payload,
        actor_user_id=actor_user_id,
        trace_id=get_trace_id(),
        status="pending",
    )
    session.add(event)
    session.flush()
    return event


def deliver_critical(
    session: Session,
    event: EventOutbox,
    recipient_user_ids: list[uuid.UUID],
) -> list[Notification]:
    """Write in-app notification rows inside the caller's transaction for a
    Critical event (a failure fails the caller's transaction — §20 rule).
    The event is marked delivered: the relay must not re-deliver rows that
    were written in the business commit."""
    rows = [
        Notification(
            user_id=recipient_id,
            outbox_event_id=event.id,
            event_type=event.event_type,
            payload=event.payload,
        )
        for recipient_id in recipient_user_ids
    ]
    session.add_all(rows)
    event.status = "delivered"
    session.flush()
    return rows


def event_is_critical(event_type: str) -> bool:
    return event_type in CRITICAL_EVENTS
