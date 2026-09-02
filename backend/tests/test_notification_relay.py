import os
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.common.bus import bus
from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.main import create_app
from app.modules.notification.models import EventOutbox, Notification
from app.modules.notification.relay import RelayWorker
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="relay tests require real PostgreSQL (SKIP LOCKED claim)",
)


@pytest.fixture()
def pg():
    engine = create_engine(_TEST_DATABASE_URL)  # type: ignore[arg-type]
    Base.metadata.create_all(engine)
    dispose_engine()
    init_engine(get_settings())

    factory = sessionmaker(bind=engine)
    with factory() as session:
        run_seed(session, prod=False)

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client, factory

    dispose_engine()
    engine.dispose()


def _admin_id(pg):  # type: ignore[no-untyped-def]
    from app.modules.user.models import User

    with pg[1]() as session:
        return str(session.scalar(select(User.id).where(User.email.like("admin@%"))))


def _insert_pending(pg, audience: dict) -> uuid.UUID:  # type: ignore[no-untyped-def]
    with pg[1]() as session:
        event = EventOutbox(
            event_type="ItemRequestCreated",
            payload={"entity_id": str(uuid.uuid4()), "audience": audience},
            status="pending",
        )
        session.add(event)
        session.commit()
        return event.id


def _wait_for_delivery(pg, event_id: uuid.UUID, timeout: float = 5.0) -> str | None:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with pg[1]() as session:
            event = session.get(EventOutbox, event_id)
            if event is not None and event.status in ("delivered", "failed", "skipped"):
                return event.status
        time.sleep(0.05)
    return None


def _notification_count(pg, event_id: uuid.UUID) -> int:  # type: ignore[no-untyped-def]
    with pg[1]() as session:
        return len(
            list(
                session.scalars(
                    select(Notification).where(Notification.outbox_event_id == event_id)
                ).all()
            )
        )


@requires_db
def test_relay_delivers_pending_event_within_latency(pg):  # type: ignore[no-untyped-def]
    """SC-003: commit → in-app row within the relay latency (seconds)."""
    client, _factory = pg
    admin_id = _admin_id(pg)
    event_id = _insert_pending(pg, {"users": [admin_id]})
    worker = RelayWorker(poll_seconds=0.2)
    worker.start()
    try:
        status = _wait_for_delivery(pg, event_id, timeout=5.0)
        assert status == "delivered"
        assert _notification_count(pg, event_id) == 1
    finally:
        worker.stop()


@requires_db
def test_relay_reclaims_orphans_on_start_without_duplicates(pg):  # type: ignore[no-untyped-def]
    """Restart replay (SC-002/SC-003): an orphaned ``processing`` row left by
    a crashed relay is re-claimed and delivered exactly once."""
    admin_id = _admin_id(pg)
    with pg[1]() as session:
        orphan = EventOutbox(
            event_type="ItemRequestFulfilled",
            payload={"entity_id": str(uuid.uuid4()), "audience": {"users": [admin_id]}},
            status="processing",
        )
        session.add(orphan)
        session.commit()
        orphan_id = orphan.id

    worker = RelayWorker(poll_seconds=0.2)
    worker.start()
    try:
        status = _wait_for_delivery(pg, orphan_id, timeout=5.0)
        assert status == "delivered"
        assert _notification_count(pg, orphan_id) == 1
    finally:
        worker.stop()


@requires_db
def test_relay_publishes_delivered_rows_to_bus(pg, monkeypatch):  # type: ignore[no-untyped-def]
    """Research R5: each delivered row is pushed to the bus for SSE."""
    admin_id = _admin_id(pg)
    published: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        bus, "publish_threadsafe", lambda user_id, payload: published.append((user_id, payload))
    )
    event_id = _insert_pending(pg, {"users": [admin_id]})
    worker = RelayWorker(poll_seconds=0.2)
    worker.start()
    try:
        status = _wait_for_delivery(pg, event_id, timeout=5.0)
        assert status == "delivered"
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not published:
            time.sleep(0.05)
        assert [(user_id, payload["event_type"]) for user_id, payload in published] == [
            (admin_id, "ItemRequestCreated")
        ]
        assert published[0][1]["id"]  # notification id present in the frame payload
    finally:
        worker.stop()
