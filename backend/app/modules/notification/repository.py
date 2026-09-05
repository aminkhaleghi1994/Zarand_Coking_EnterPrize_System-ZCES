"""Notification module queries: relay claim (row-locked, at-least-once) and
owner-scoped reads. Claim discipline mirrors the platform's stock-row
locking: concurrent relays skip locked rows (research R2)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.notification.models import EventOutbox, Notification

MAX_ATTEMPTS = 5


def claim_pending(session: Session, limit: int = 50) -> list[EventOutbox]:
    """Claim up to ``limit`` pending events oldest-first with
    FOR UPDATE SKIP LOCKED so concurrent relays never double-claim."""
    ids = session.scalars(
        select(EventOutbox.id)
        .where(EventOutbox.status == "pending")
        .order_by(EventOutbox.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    if not ids:
        return []
    events = list(
        session.scalars(
            select(EventOutbox)
            .where(EventOutbox.id.in_(ids))
            .order_by(EventOutbox.created_at)
        ).all()
    )
    for event in events:
        event.status = "processing"
    session.flush()
    return events


def reclaim_processing(session: Session) -> int:
    """Startup re-claim (research R2): orphaned ``processing`` rows (crashed
    relay) return to ``pending``; the exactly-once unique keeps re-delivery
    idempotent."""
    events = session.scalars(
        select(EventOutbox).where(EventOutbox.status == "processing")
    ).all()
    for event in events:
        event.status = "pending"
    session.flush()
    return len(events)


def mark_failed(session: Session, event: EventOutbox, error: str) -> None:
    event.status = "failed"
    event.last_error = error[:2000]
    session.flush()


def mark_skipped(session: Session, event: EventOutbox, reason: str) -> None:
    event.status = "skipped"
    event.last_error = reason[:2000]
    session.flush()


def mark_retry(session: Session, event: EventOutbox, error: str) -> str:
    """Bounded retry (research R2): attempts ≤ 5; beyond the bound the event
    is terminally failed (no physical deletion)."""
    event.attempts = (event.attempts or 0) + 1
    if event.attempts >= MAX_ATTEMPTS:
        mark_failed(session, event, f"exhausted {event.attempts} attempts: {error}")
        return "failed"
    event.status = "pending"
    event.last_error = error[:2000]
    session.flush()
    return "pending"


def list_for_owner(
    session: Session,
    user_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
    unread_only: bool,
) -> tuple[list[Notification], int]:
    """Owner-scoped list (constitution II): strictly the signed-in user's
    rows, newest first."""
    base = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        base = base.where(Notification.read_at.is_(None))
    total = session.scalar(
        select(func.count()).select_from(base.subquery())
    )
    rows = session.scalars(
        base.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(rows), int(total or 0)


def get_for_owner(
    session: Session, notification_id: uuid.UUID, user_id: uuid.UUID
) -> Notification | None:
    """Foreign ids return None (no existence leak — 404 for the caller)."""
    return session.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    )


def count_unread(session: Session, user_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        or 0
    )


def notifications_for_event(session: Session, event_id: uuid.UUID) -> list[Notification]:
    """Rows written for an outbox event (relay fan-out source)."""
    return list(
        session.scalars(
            select(Notification).where(Notification.outbox_event_id == event_id)
        ).all()
    )


def mark_read(session: Session, notification: Notification) -> bool:
    """Idempotent stamp; returns True when this call set the timestamp."""
    if notification.read_at is None:
        notification.read_at = datetime.now(tz=UTC)
        session.flush()
        return True
    return False


def mark_all_read(session: Session, user_id: uuid.UUID) -> int:
    unread = session.scalars(
        select(Notification).where(
            Notification.user_id == user_id, Notification.read_at.is_(None)
        )
    ).all()
    stamped = datetime.now(tz=UTC)
    for notification in unread:
        notification.read_at = stamped
    session.flush()
    return len(unread)
