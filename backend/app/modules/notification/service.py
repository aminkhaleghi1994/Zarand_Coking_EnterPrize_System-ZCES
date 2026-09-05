"""Relay delivery (US2, research R2/R3): turn a claimed outbox event into
per-recipient notification rows — idempotent (the exactly-once unique),
scope-driven recipients, deactivated recipients skipped, bounded retries,
terminal failed/skipped statuses. Delivery failures never raise into the
caller's business transaction (§20): the relay owns this transaction.

Also the owner-facing inbox service (US3): strictly owner-scoped reads and
idempotent mark-read transitions — a user's inbox is personal data."""

import uuid
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.modules.notification import repository
from app.modules.notification.models import EVENT_TYPES, EventOutbox, Notification
from app.modules.user import contracts as user_contracts


def _audience(payload: dict[str, Any]) -> dict[str, Any]:
    audience = payload.get("audience")
    return audience if isinstance(audience, dict) else {}


def _resolve_recipients(session: Session, payload: dict[str, Any]) -> list[uuid.UUID]:
    """Deterministic recipients (research R3): explicit user ids from the
    payload plus scope-covered holders, deduplicated, implicit deny."""
    audience = _audience(payload)
    resolved: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()

    def _add(user_id: uuid.UUID | None) -> None:
        if user_id is None or user_id in seen:
            return
        seen.add(user_id)
        resolved.append(user_id)

    for raw in audience.get("users") or []:
        _add(uuid.UUID(str(raw)))
    scope = audience.get("scope")
    if isinstance(scope, dict) and scope.get("permission"):
        workplace_raw = scope.get("workplace_id")
        workplace_id = uuid.UUID(str(workplace_raw)) if workplace_raw else None
        for user_id in user_contracts.get_recipient_user_ids(
            session, str(scope["permission"]), workplace_id
        ):
            _add(user_id)
    return resolved


def _filter_active(session: Session, user_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """Deactivated recipients are skipped at delivery (spec edge case 2)."""
    return user_contracts.filter_active_user_ids(session, user_ids)


def deliver_event(session: Session, event: EventOutbox) -> str:
    """Deliver one claimed event; returns its final status (research R2).

    - unknown event type → immediate terminal ``failed``;
    - recipient-less or all-deactivated → terminal ``skipped``;
    - idempotent inserts (partial unique) then terminal ``delivered``;
    - resolution/delivery errors → bounded retry, eventually ``failed``.
    """
    if event.event_type not in EVENT_TYPES:
        repository.mark_failed(session, event, f"unknown event type: {event.event_type}")
        return "failed"
    try:
        recipients = _resolve_recipients(session, event.payload)
        active = _filter_active(session, recipients)
    except Exception as exc:  # noqa: BLE001 — any failure must retry, not raise
        return repository.mark_retry(session, event, f"recipient resolution: {exc}")
    if not recipients or not active:
        repository.mark_skipped(
            session,
            event,
            "no eligible recipients"
            if not recipients
            else "all recipients deactivated",
        )
        return "skipped"
    try:
        stmt = pg_insert(Notification).values(
            [
                {
                    "user_id": user_id,
                    "outbox_event_id": event.id,
                    "event_type": event.event_type,
                    "payload": event.payload,
                }
                for user_id in active
            ]
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=("outbox_event_id", "user_id")
        )
        session.execute(stmt)
        event.status = "delivered"
        event.last_error = None
        session.flush()
    except Exception as exc:  # noqa: BLE001 — bounded retry, never raise
        return repository.mark_retry(session, event, f"notification insert: {exc}")
    return "delivered"


def deliver_claimed_batch(
    session: Session, events: list[EventOutbox]
) -> list[tuple[EventOutbox, str]]:
    """Deliver a claimed batch oldest-first; each event commits with the
    caller (the relay commits per event so a failure never blocks others)."""
    results: list[tuple[EventOutbox, str]] = []
    for event in events:
        results.append((event, deliver_event(session, event)))
    return results


# --- Owner-facing inbox (US3) ---


def list_inbox(
    session: Session,
    user_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
    unread_only: bool,
) -> tuple[list[Notification], int]:
    """Owner-scoped inbox page (newest first)."""
    return repository.list_for_owner(
        session,
        user_id,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
    )


def unread_inbox_count(session: Session, user_id: uuid.UUID) -> int:
    return repository.count_unread(session, user_id)


def mark_notification_read(
    session: Session, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification:
    """Idempotent read stamp; foreign/missing ids are 404 (no leak)."""
    notification = repository.get_for_owner(session, notification_id, user_id)
    if notification is None:
        raise not_found("Notification not found")
    repository.mark_read(session, notification)
    session.commit()
    return notification


def mark_inbox_all_read(session: Session, user_id: uuid.UUID) -> int:
    marked = repository.mark_all_read(session, user_id)
    session.commit()
    return marked
