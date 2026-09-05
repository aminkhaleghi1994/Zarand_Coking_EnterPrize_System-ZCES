import os
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.modules.notification import repository, service
from app.modules.notification.models import EventOutbox, Notification
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="delivery tests require real PostgreSQL (JSONB + upsert semantics)",
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


def _pending_event(
    pg_session,  # type: ignore[no-untyped-def]
    event_type: str,
    payload: dict,
):  # type: ignore[no-untyped-def]
    event = EventOutbox(event_type=event_type, payload=payload, status="pending")
    pg_session.add(event)
    pg_session.commit()
    return event


def _claim(pg_session, event):  # type: ignore[no-untyped-def]
    """Put the event through the same claim path the relay uses."""
    event.status = "processing"
    pg_session.commit()
    return event


def _notification_count(pg_session, event_id):  # type: ignore[no-untyped-def]
    return len(
        list(
            pg_session.scalars(
                select(Notification).where(Notification.outbox_event_id == event_id)
            ).all()
        )
    )


@requires_db
def test_delivers_to_explicit_users_and_scope_holders(pg_session):  # type: ignore[no-untyped-def]
    from app.modules.user.models import User, Workplace

    admin = pg_session.scalar(select(User).where(User.email.like("admin@%")))
    workplace = pg_session.scalar(select(Workplace).where(Workplace.code == "CP1"))
    assert admin is not None and workplace is not None
    event = _pending_event(
        pg_session,
        "ItemRequestCreated",
        {
            "entity_id": str(uuid.uuid4()),
            "audience": {
                "users": [str(admin.id)],
                "scope": {
                    "permission": "warehouse:request:decide",
                    "workplace_id": str(workplace.id),
                },
            },
        },
    )
    session = pg_session
    status = service.deliver_event(session, _claim(session, event))
    assert status == "delivered"
    count = _notification_count(pg_session, event.id)
    assert count >= 1  # admin (explicit + scope overlap dedupes to one row)
    delivered = pg_session.get(EventOutbox, event.id)
    assert delivered is not None and delivered.status == "delivered"


@requires_db
def test_replay_is_exactly_once(pg_session):  # type: ignore[no-untyped-def]
    """Re-delivering a delivered event (relay restart crash) must not
    duplicate notifications (research R2)."""
    from app.modules.user.models import User

    admin = pg_session.scalar(select(User).where(User.email.like("admin@%")))
    assert admin is not None
    event = _pending_event(
        pg_session,
        "ItemRequestFulfilled",
        {"entity_id": str(uuid.uuid4()), "audience": {"users": [str(admin.id)]}},
    )
    first = service.deliver_event(pg_session, event)
    assert first == "delivered"
    count_after_first = _notification_count(pg_session, event.id)
    second = service.deliver_event(pg_session, event)  # simulated replay
    assert second == "delivered"
    assert _notification_count(pg_session, event.id) == count_after_first


@requires_db
def test_skips_all_deactivated_recipients(pg_session):  # type: ignore[no-untyped-def]
    """FR-006: delivery to a deactivated account is skipped and recorded,
    never retried forever."""
    from sqlalchemy import update

    from app.modules.user.models import User

    admin = pg_session.scalar(select(User).where(User.email.like("admin@%")))
    assert admin is not None
    pg_session.execute(update(User).where(User.id == admin.id).values(is_active=False))
    pg_session.commit()
    try:
        event = _pending_event(
            pg_session,
            "ItemRequestRejected",
            {"entity_id": str(uuid.uuid4()), "audience": {"users": [str(admin.id)]}},
        )
        status = service.deliver_event(pg_session, event)
        assert status == "skipped"
        delivered = pg_session.get(EventOutbox, event.id)
        assert delivered is not None and delivered.status == "skipped"
        assert _notification_count(pg_session, event.id) == 0
    finally:
        pg_session.execute(update(User).where(User.id == admin.id).values(is_active=True))
        pg_session.commit()


@requires_db
def test_recipientless_event_marked_skipped(pg_session):  # type: ignore[no-untyped-def]
    event = _pending_event(
        pg_session,
        "ItemReturned",  # deferred emitter: no audience payload yet
        {"entity_id": str(uuid.uuid4())},
    )
    status = service.deliver_event(pg_session, event)
    assert status == "skipped"
    delivered = pg_session.get(EventOutbox, event.id)
    assert delivered is not None and delivered.status == "skipped"


@requires_db
def test_bounded_retries_then_terminal_failure(pg_session):  # type: ignore[no-untyped-def]
    from unittest.mock import patch

    from app.modules.user.models import User

    admin = pg_session.scalar(select(User).where(User.email.like("admin@%")))
    assert admin is not None
    event = _pending_event(
        pg_session,
        "LoanRequestActivated",
        {"entity_id": str(uuid.uuid4()), "audience": {"users": [str(admin.id)]}},
    )
    with patch.object(service, "_resolve_recipients", side_effect=RuntimeError("boom")):
        for _ in range(repository.MAX_ATTEMPTS - 1):
            assert service.deliver_event(pg_session, event) == "pending"
        assert service.deliver_event(pg_session, event) == "failed"
    delivered = pg_session.get(EventOutbox, event.id)
    assert delivered is not None
    assert delivered.status == "failed"
    assert delivered.attempts == repository.MAX_ATTEMPTS
    assert delivered.last_error is not None and "boom" in delivered.last_error
    assert _notification_count(pg_session, event.id) == 0


@requires_db
def test_unknown_event_type_is_immediately_failed(pg_session):  # type: ignore[no-untyped-def]
    """Defensive terminal path: a type the running code doesn't know (e.g. a
    newer DB row after a partial deploy) must fail immediately, not retry."""
    from unittest.mock import patch

    event = _pending_event(
        pg_session,
        "LoanRequestSettled",
        {"entity_id": str(uuid.uuid4()), "audience": {}},
    )
    with patch.object(service, "EVENT_TYPES", ()):  # code "doesn't know" the type
        status = service.deliver_event(pg_session, event)
    assert status == "failed"
    delivered = pg_session.get(EventOutbox, event.id)
    assert delivered is not None and delivered.status == "failed"
    assert delivered.attempts == 0
