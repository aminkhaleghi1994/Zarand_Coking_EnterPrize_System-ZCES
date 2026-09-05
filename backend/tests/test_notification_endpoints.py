import asyncio
import gc
import json
import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.common.bus import bus
from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.main import create_app
from app.modules.notification import service
from app.modules.notification.models import EventOutbox, Notification
from app.modules.user.models import User
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="notification endpoint tests require real PostgreSQL",
)

_RUN = uuid.uuid4().hex[:6]
_counter = {"n": 0}


def _unique_tag() -> str:
    _counter["n"] += 1
    return f"{_RUN}-{_counter['n']}"


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


def _admin_token(client: TestClient) -> str:
    settings = get_settings()
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.INITIAL_ADMIN_EMAIL,
            "password": settings.INITIAL_ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin_id(client: TestClient, token: str) -> str:
    me = client.get("/api/v1/auth/me", headers=_bearer(token))
    assert me.status_code == 200, me.text
    return me.json()["user"]["id"]


def _make_user(factory, tag: str) -> uuid.UUID:  # type: ignore[no-untyped-def]
    from app.core.security import hash_password

    with factory() as session:
        existing = session.scalar(
            select(User).where(User.email == f"inbox-{tag}@zarandsteel.ir")
        )
        if existing is not None:
            user_id = existing.id
        else:
            user = User(
                email=f"inbox-{tag}@zarandsteel.ir",
                username=f"inbox-{tag}",
                hashed_password=hash_password("inbox-password-1"),
            )
            session.add(user)
            session.flush()
            user_id = user.id
        session.commit()
        return user_id


def _fresh_user(client: TestClient, factory, tag: str) -> tuple[str, str]:  # type: ignore[no-untyped-def]
    """Dedicated user + bearer token per test, so inbox tests stay isolated
    from each other's leftovers (the seed admin is shared across tests)."""
    user_id = _make_user(factory, tag)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": f"inbox-{tag}@zarandsteel.ir", "password": "inbox-password-1"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"], str(user_id)


def _make_notification(
    factory,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    *,
    created_at: datetime | None = None,
    read: bool = False,
    event_type: str = "ItemRequestCreated",
):
    with factory() as session:
        event = EventOutbox(
            event_type=event_type,
            payload={"entity_id": str(uuid.uuid4()), "title": "request_created"},
            status="delivered",
        )
        session.add(event)
        session.flush()
        row = Notification(
            user_id=user_id,
            outbox_event_id=event.id,
            event_type=event_type,
            payload=dict(event.payload),
            read_at=datetime.now(tz=UTC) if read else None,
            created_at=created_at or datetime.now(tz=UTC),
        )
        session.add(row)
        session.commit()
        return {"id": str(row.id), "created_at": row.created_at}


async def _drive_sse(
    app: Any,
    headers: dict[str, str],
    user_id: str,
    publish: Callable[[], None],
    marker: str,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Run the SSE stream endpoint at the raw ASGI level, inside the app's
    own event loop (``client.portal``). The buffered TestClient transport
    cannot stream: it awaits full app completion, which an infinite SSE
    stream never reaches — so ``client.stream()`` would deadlock. Here we
    drive the ASGI interface directly, publish through the real bus, then
    deliver ``http.disconnect`` once the wanted frame arrives — mirroring a
    real client disconnect, which starlette turns into generator teardown.
    ``anyio.fail_after`` bounds the whole exchange: this can never hang."""
    results: dict[str, Any] = {"status": None, "headers": {}, "lines": []}
    got_marker = asyncio.Event()
    disconnect = asyncio.Event()

    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/notifications/stream",
        "raw_path": b"/api/v1/notifications/stream",
        "query_string": b"",
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    async def receive() -> dict[str, Any]:
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            results["status"] = message["status"]
            results["headers"] = {
                k.decode(): v.decode() for k, v in message.get("headers", [])
            }
        elif message["type"] == "http.response.body":
            body = message.get("body", b"")
            if body:
                text = body.decode()
                results["lines"].extend(text.splitlines())
                if marker in text:
                    got_marker.set()

    with anyio.fail_after(timeout):
        async with anyio.create_task_group() as tg:
            tg.start_soon(app, scope, receive, send)
            while results["status"] is None:
                await asyncio.sleep(0.02)
            while bus.subscriber_count(user_id) < 1:
                await asyncio.sleep(0.02)
            publish()
            await got_marker.wait()
            disconnect.set()
        # The task group joins here only after the app completed via the
        # disconnect path — a wedged stream instead raises TimeoutError.

    # Deterministic teardown check: once the app task dropped its response,
    # the async generator finalizes (CPython refcount) and its ``finally``
    # unsubscribes — give the loop ticks to run the aclose task.
    gc.collect()
    for _ in range(100):
        if bus.subscriber_count(user_id) == 0:
            break
        await asyncio.sleep(0.02)

    return results


# --- US3: live SSE stream ---


@requires_db
def test_stream_requires_authentication(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    response = client.get("/api/v1/notifications/stream")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"
    bad = client.get(
        "/api/v1/notifications/stream", headers={"Authorization": "Bearer garbage"}
    )
    assert bad.status_code == 401
    assert bad.json()["code"] == "AUTHENTICATION_REQUIRED"


@requires_db
def test_stream_delivers_frames_to_owner_only(pg):  # type: ignore[no-untyped-def]
    """SC-003: the stream pushes only the caller's notifications — a foreign
    user's delivery must never appear in the frame stream."""
    client, factory = pg
    token = _admin_token(client)
    admin_id = _admin_id(client, token)
    other = _make_user(factory, _unique_tag())

    foreign_marker = f"FOREIGN-{_unique_tag()}"
    own_marker = f"OWN-{_unique_tag()}"

    def publish() -> None:
        bus.publish_threadsafe(str(other), {"id": foreign_marker})
        bus.publish_threadsafe(
            admin_id, {"id": own_marker, "event_type": "ItemRequestCreated"}
        )

    results = client.portal.call(
        _drive_sse, client.app, _bearer(token), admin_id, publish, own_marker
    )

    assert results["status"] == 200
    assert results["headers"]["content-type"].startswith("text/event-stream")
    assert results["headers"]["cache-control"] == "no-cache, no-transform"
    assert "event: notification" in results["lines"]
    assert any(
        line.startswith("data: ") and own_marker in line for line in results["lines"]
    )
    assert not any(foreign_marker in line for line in results["lines"])
    assert bus.subscriber_count(admin_id) == 0  # disconnect tore the stream down


@requires_db
def test_stream_frame_carries_notification_payload(pg):  # type: ignore[no-untyped-def]
    """The relay publishes NotificationOut dumps — the stream must forward
    them verbatim so the browser can render without a refetch."""
    client, _factory = pg
    token = _admin_token(client)
    admin_id = _admin_id(client, token)
    payload = {
        "id": str(uuid.uuid4()),
        "event_type": "InventoryLowStock",
        "payload": {"title": "low_stock", "body": "Item X below threshold"},
        "read_at": None,
        "created_at": "2026-09-05T10:00:00Z",
    }

    def publish() -> None:
        bus.publish_threadsafe(admin_id, payload)

    results = client.portal.call(
        _drive_sse, client.app, _bearer(token), admin_id, publish, payload["id"]
    )

    data_lines = [line for line in results["lines"] if line.startswith("data: ")]
    assert data_lines, "no data frame arrived"
    assert json.loads(data_lines[0][len("data: ") :]) == payload


# --- US3: inbox REST endpoints ---


@requires_db
def test_inbox_lists_own_notifications_newest_first(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token, owner = _fresh_user(client, factory, _unique_tag())
    other = _make_user(factory, _unique_tag())

    base = datetime.now(tz=UTC)
    oldest = _make_notification(factory, uuid.UUID(owner), created_at=base)
    read_one = _make_notification(
        factory, uuid.UUID(owner), created_at=base + timedelta(seconds=1), read=True
    )
    newest = _make_notification(
        factory, uuid.UUID(owner), created_at=base + timedelta(seconds=2)
    )
    _make_notification(factory, other)  # foreign — must never leak

    listed = client.get("/api/v1/notifications", headers=_bearer(token))
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total"] == 3
    ids = [item["id"] for item in body["items"]]
    assert ids[0] == newest["id"]
    assert ids[1] == read_one["id"]
    assert ids[2] == oldest["id"]
    assert all(item["payload"]["title"] == "request_created" for item in body["items"])

    unread = client.get(
        "/api/v1/notifications?unread_only=true", headers=_bearer(token)
    )
    assert unread.status_code == 200
    unread_ids = [item["id"] for item in unread.json()["items"]]
    assert unread_ids == [newest["id"], oldest["id"]]

    paged = client.get(
        "/api/v1/notifications?page=2&page_size=2", headers=_bearer(token)
    )
    assert paged.status_code == 200
    assert [item["id"] for item in paged.json()["items"]] == [oldest["id"]]
    assert paged.json()["total"] == 3


@requires_db
def test_unread_count_and_read_all(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token, owner = _fresh_user(client, factory, _unique_tag())
    _make_notification(factory, uuid.UUID(owner))
    _make_notification(factory, uuid.UUID(owner))

    count = client.get("/api/v1/notifications/unread-count", headers=_bearer(token))
    assert count.status_code == 200
    assert count.json() == {"unread": 2}

    marked = client.post("/api/v1/notifications/read-all", headers=_bearer(token))
    assert marked.status_code == 200
    assert marked.json() == {"marked": 2}

    after = client.get("/api/v1/notifications/unread-count", headers=_bearer(token))
    assert after.json() == {"unread": 0}
    again = client.post("/api/v1/notifications/read-all", headers=_bearer(token))
    assert again.json() == {"marked": 0}  # idempotent


@requires_db
def test_mark_read_idempotent_and_foreign_404(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token, owner = _fresh_user(client, factory, _unique_tag())
    other = _make_user(factory, _unique_tag())
    own = _make_notification(factory, uuid.UUID(owner))
    foreign = _make_notification(factory, other)

    first = client.post(
        f"/api/v1/notifications/{own['id']}/read", headers=_bearer(token)
    )
    assert first.status_code == 200, first.text
    assert first.json()["read_at"] is not None

    second = client.post(
        f"/api/v1/notifications/{own['id']}/read", headers=_bearer(token)
    )
    assert second.status_code == 200  # idempotent, no error
    # Same instant either way: a freshly stamped UTC value serializes as
    # ``...Z`` while a reloaded one carries the DB session timezone offset —
    # compare parsed datetimes, not strings.
    assert datetime.fromisoformat(second.json()["read_at"]) == datetime.fromisoformat(
        first.json()["read_at"]
    )

    missing = client.post(
        f"/api/v1/notifications/{uuid.uuid4()}/read", headers=_bearer(token)
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "RESOURCE_NOT_FOUND"

    leaked = client.post(
        f"/api/v1/notifications/{foreign['id']}/read", headers=_bearer(token)
    )
    assert leaked.status_code == 404  # foreign id — no existence leak
    assert leaked.json()["code"] == "RESOURCE_NOT_FOUND"


# --- US5: criticality observability (FR-010, SC-004) ---


@requires_db
def test_non_critical_delivery_failure_leaves_business_state_untouched(
    pg,
):  # type: ignore[no-untyped-def]
    """FR-010: when a NON-critical event's delivery fails, the business
    transaction stays committed and the event retries — notification
    failures never break the main flow (constitution IX)."""
    from unittest.mock import patch

    client, factory = pg
    token = _admin_token(client)
    tag = _unique_tag()

    # Business action whose capture is non-critical: create a catalog item.
    item = client.post(
        "/api/v1/warehouse/items",
        json={
            "name": f"Inbox item {tag}",
            "name_fa": f"کالای صندوق {tag}",
            "unit": "ad",
            "min_quantity": "1.000",
        },
        headers=_bearer(token),
    )
    assert item.status_code == 201, item.text
    item_id = item.json()["id"]

    with factory() as session:
        event = session.scalar(
            select(EventOutbox).where(
                EventOutbox.event_type == "ItemCatalogCreated",
                EventOutbox.payload["entity_id"].as_string() == item_id,
            )
        )
        assert event is not None
        assert event.status == "pending"
        event_id = event.id

    with factory() as session:
        event = session.get(EventOutbox, event_id)
        assert event is not None
        with patch.object(service, "_resolve_recipients", side_effect=RuntimeError("boom")):
            status = service.deliver_event(session, event)
        assert status == "pending"  # bounded retry, not a business failure
        session.commit()

    # The business state is untouched by the delivery failure.
    still_there = client.get(
        f"/api/v1/warehouse/items/{item_id}", headers=_bearer(token)
    )
    assert still_there.status_code == 200, still_there.text

    with factory() as session:
        retrying = session.get(EventOutbox, event_id)
        assert retrying is not None
        assert retrying.status == "pending"
        assert retrying.attempts == 1
        assert retrying.last_error is not None and "boom" in retrying.last_error
