import os
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.modules.notification import contracts
from app.modules.notification.models import EventOutbox, Notification
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="capture-contract tests require real PostgreSQL (JSONB payloads)",
)


@pytest.fixture()
def pg_session():
    from app.core.database import Base

    engine = create_engine(_TEST_DATABASE_URL)  # type: ignore[arg-type]
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        run_seed(session, prod=False)
        yield session
    engine.dispose()


@requires_db
def test_record_event_writes_pending_row_in_session(pg_session):  # type: ignore[no-untyped-def]
    actor = uuid.uuid4()
    event = contracts.record_event(
        pg_session,
        "ItemRequestCreated",
        {"entity_id": str(uuid.uuid4()), "title": "request_created"},
        actor_user_id=actor,
    )
    # In-session visibility BEFORE commit: the row joins the caller's transaction.
    row = pg_session.scalar(select(EventOutbox).where(EventOutbox.id == event.id))
    assert row is not None
    assert row.event_type == "ItemRequestCreated"
    assert row.status == "pending"
    assert row.attempts == 0
    assert row.actor_user_id == actor
    assert row.payload["title"] == "request_created"
    pg_session.rollback()  # keep the shared dev DB clean


@requires_db
def test_record_event_unknown_type_rejected(pg_session):  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="Unknown event type"):
        contracts.record_event(
            pg_session, "NotAnEventType", {"entity_id": str(uuid.uuid4())}, actor_user_id=None
        )


@requires_db
def test_criticality_mapping(pg_session):  # type: ignore[no-untyped-def]
    assert contracts.event_is_critical("InventoryLowStock")
    assert not contracts.event_is_critical("ItemRequestCreated")
    assert not contracts.event_is_critical("LoanRequestActivated")
    assert frozenset({"InventoryLowStock"}) == contracts.CRITICAL_EVENTS


@requires_db
def test_deliver_critical_writes_rows_and_marks_delivered(pg_session):  # type: ignore[no-untyped-def]
    from app.modules.user.models import User

    admin = pg_session.scalar(select(User).where(User.email.like("admin@%")))
    assert admin is not None
    event = contracts.record_event(
        pg_session,
        "InventoryLowStock",
        {"entity_id": str(uuid.uuid4()), "title": "low_stock"},
        actor_user_id=admin.id,
    )
    rows = contracts.deliver_critical(pg_session, event, [admin.id])
    assert len(rows) == 1
    pg_session.flush()
    notification = pg_session.scalar(
        select(Notification).where(Notification.outbox_event_id == event.id)
    )
    assert notification is not None
    assert notification.user_id == admin.id
    assert notification.read_at is None
    delivered = pg_session.get(EventOutbox, event.id)
    assert delivered is not None and delivered.status == "delivered"
    pg_session.rollback()


@requires_db
def test_deliver_critical_duplicate_recipient_blocked(pg_session):  # type: ignore[no-untyped-def]
    """The exactly-once backbone: a second write for the same (event, user)
    violates the unique index — the relay's insert path relies on this."""
    from sqlalchemy.exc import IntegrityError

    from app.modules.user.models import User

    admin = pg_session.scalar(select(User).where(User.email.like("admin@%")))
    assert admin is not None
    event = contracts.record_event(
        pg_session,
        "InventoryLowStock",
        {"entity_id": str(uuid.uuid4())},
        actor_user_id=admin.id,
    )
    contracts.deliver_critical(pg_session, event, [admin.id])
    pg_session.flush()
    with pytest.raises(IntegrityError):
        contracts.deliver_critical(pg_session, event, [admin.id])
        pg_session.flush()
    pg_session.rollback()
