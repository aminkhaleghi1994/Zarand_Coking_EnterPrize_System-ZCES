import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.common.jalali import current_jalali_year
from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.main import create_app
from app.modules.notification.models import EventOutbox, Notification
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="capture-matrix tests require real PostgreSQL (JSONB + CHECKs)",
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
        json={"email": settings.INITIAL_ADMIN_EMAIL, "password": settings.INITIAL_ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _rows(
    factory,  # type: ignore[no-untyped-def]
    event_type: str,
    entity_id: str | None = None,
):
    with factory() as session:
        stmt = select(EventOutbox).where(EventOutbox.event_type == event_type)
        if entity_id is not None:
            stmt = stmt.where(EventOutbox.payload["entity_id"].as_string() == entity_id)
        return [
            {
                "id": row.id,
                "status": row.status,
                "actor_user_id": row.actor_user_id,
                "payload": dict(row.payload),
            }
            for row in session.scalars(stmt).all()
        ]


def _notifications(
    factory,  # type: ignore[no-untyped-def]
    outbox_event_id: uuid.UUID | str,
):
    with factory() as session:
        return [
            {
                "user_id": str(row.user_id),
                "read_at": row.read_at,
            }
            for row in session.scalars(
                select(Notification).where(
                    Notification.outbox_event_id == uuid.UUID(str(outbox_event_id))
                )
            ).all()
        ]


def _admin_id(client: TestClient, token: str) -> str:
    me = client.get("/api/v1/auth/me", headers=_bearer(token))
    assert me.status_code == 200, me.text
    return me.json()["user"]["id"]


def _create_employee(client: TestClient, token: str, workplace_id: str, tag: str):
    email = f"cap-{tag}@zarandsteel.ir"
    created = client.post(
        "/api/v1/employees",
        json={
            "national_id": f"8{uuid.uuid4().int % 10**9:09d}",
            "personnel_code": f"CEN-{tag}",
            "first_name": "Capture",
            "last_name": f"Employee {tag}",
            "workplace_id": workplace_id,
            "user": {"email": email, "username": f"cap-{tag}", "password": "cap-password-1"},
        },
        headers=_bearer(token),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    return body["id"], body["user"]["id"], email


def _make_request(
    client: TestClient, token: str, item_id: str, quantity: str = "2"
) -> dict:
    created = client.post(
        "/api/v1/warehouse/requests",
        json={
            "purpose_description": f"Capture matrix {_unique_tag()}",
            "lines": [{"item_id": item_id, "quantity": quantity}],
        },
        headers=_bearer(token),
    )
    assert created.status_code == 201, created.text
    return created.json()


@requires_db
def test_user_created_capture(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    admin_id = _admin_id(client, token)
    workplace = client.get("/api/v1/org/workplaces", headers=_bearer(token)).json()["items"][0]
    employee_id, _user_id, _email = _create_employee(client, token, workplace["id"], _unique_tag())

    rows = _rows(factory, "UserCreated", entity_id=employee_id)
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "pending"
    assert row["actor_user_id"] and str(row["actor_user_id"]) == admin_id
    assert row["payload"]["title"] == "user_created"
    assert row["payload"]["workplace_id"] == workplace["id"]
    assert row["payload"]["audience"]["scope"]["permission"] == "user:employee:read"


@requires_db
def test_item_catalog_created_capture(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    admin_id = _admin_id(client, token)
    tag = _unique_tag()
    item = client.post(
        "/api/v1/warehouse/items",
        json={
            "name": f"Capture item {tag}",
            "name_fa": f"کالای capture {tag}",
            "unit": "ad",
            "min_quantity": "5.000",
        },
        headers=_bearer(token),
    )
    assert item.status_code == 201, item.text
    body = item.json()

    rows = _rows(factory, "ItemCatalogCreated", entity_id=body["id"])
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "pending"
    assert str(row["actor_user_id"]) == admin_id
    assert row["payload"]["title"] == "item_created"
    assert row["payload"]["item_name"] == body["name"]
    assert row["payload"]["audience"]["scope"]["permission"] == "warehouse:item:read"


@requires_db
def test_low_stock_critical_capture_in_same_commit(pg):  # type: ignore[no-untyped-def]
    """SC-004: the Critical event's notification rows exist in the business
    commit; the outbox row is born delivered."""
    client, factory = pg
    token = _admin_token(client)
    admin_id = _admin_id(client, token)
    workplace = client.get("/api/v1/org/workplaces", headers=_bearer(token)).json()["items"][0]
    tag = _unique_tag()
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": workplace["id"],
            "code": f"CAP-WH-{tag}",
            "name": f"Capture warehouse {tag}",
            "name_fa": f"انبار capture {tag}",
        },
        headers=_bearer(token),
    ).json()
    shelf = client.post(
        f"/api/v1/warehouse/warehouses/{warehouse['id']}/shelves",
        json={"code": "C-01"},
        headers=_bearer(token),
    ).json()
    item = client.post(
        "/api/v1/warehouse/items",
        json={
            "name": f"Low-stock item {tag}",
            "name_fa": f"کالای کمبود {tag}",
            "unit": "ad",
            "min_quantity": "10.000",
        },
        headers=_bearer(token),
    ).json()
    placement = client.post(
        "/api/v1/warehouse/placements/receive",
        json={"item_id": item["id"], "shelf_id": shelf["id"], "quantity": "50"},
        headers=_bearer(token),
    ).json()
    issued = client.post(
        "/api/v1/warehouse/placements/issue",
        json={"placement_id": placement["id"], "quantity": "45"},
        headers=_bearer(token),
    )
    assert issued.status_code == 200, issued.text

    rows = _rows(factory, "InventoryLowStock", entity_id=None)
    mine = [r for r in rows if r["payload"].get("placement_id") == placement["id"]]
    assert len(mine) == 1
    row = mine[0]
    assert row["status"] == "delivered"  # critical delivery happened in-commit
    assert row["payload"]["title"] == "low_stock"
    assert "body" in row["payload"]
    assert row["payload"]["workplace_id"] == workplace["id"]
    notifications = _notifications(factory, row["id"])
    assert admin_id in [n["user_id"] for n in notifications]


@requires_db
def test_request_lifecycle_capture(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    admin_id = _admin_id(client, token)
    item = client.post(
        "/api/v1/warehouse/items",
        json={
            "name": f"Request item {_unique_tag()}",
            "name_fa": "کالای درخواست",
            "unit": "ad",
            "min_quantity": "1.000",
        },
        headers=_bearer(token),
    ).json()

    # --- created ---
    request = _make_request(client, token, item["id"])
    rows = _rows(factory, "ItemRequestCreated", entity_id=request["id"])
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "pending"
    assert str(row["actor_user_id"]) == admin_id
    assert row["payload"]["requester_user_id"] == admin_id
    assert row["payload"]["line_count"] == 1
    assert row["payload"]["audience"]["users"] == [admin_id]
    assert row["payload"]["audience"]["scope"]["permission"] == "warehouse:request:decide"

    # --- approved ---
    approved = client.post(
        f"/api/v1/warehouse/requests/{request['id']}/approve",
        json={"version": request["version"], "note": "ok"},
        headers=_bearer(token),
    )
    assert approved.status_code == 200, approved.text
    rows = _rows(factory, "ItemRequestApproved", entity_id=request["id"])
    assert len(rows) == 1
    assert rows[0]["payload"]["audience"]["users"] == [admin_id]
    assert rows[0]["payload"]["audience"]["scope"]["permission"] == "warehouse:request:fulfill"

    # --- rejected ---
    rejected_request = _make_request(client, token, item["id"])
    rejected = client.post(
        f"/api/v1/warehouse/requests/{rejected_request['id']}/reject",
        json={"version": rejected_request["version"]},
        headers=_bearer(token),
    )
    assert rejected.status_code == 200, rejected.text
    rows = _rows(factory, "ItemRequestRejected", entity_id=rejected_request["id"])
    assert len(rows) == 1
    assert rows[0]["payload"]["audience"]["users"] == [admin_id]
    assert "scope" not in rows[0]["payload"]["audience"]


@requires_db
def test_request_fulfilled_capture(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    workplace = client.get("/api/v1/org/workplaces", headers=_bearer(token)).json()["items"][0]
    tag = _unique_tag()
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": workplace["id"],
            "code": f"FUL-WH-{tag}",
            "name": f"Fulfill warehouse {tag}",
            "name_fa": "انبار تحویل",
        },
        headers=_bearer(token),
    ).json()
    shelf = client.post(
        f"/api/v1/warehouse/warehouses/{warehouse['id']}/shelves",
        json={"code": "F-01"},
        headers=_bearer(token),
    ).json()
    item = client.post(
        "/api/v1/warehouse/items",
        json={
            "name": f"Fulfill item {tag}",
            "name_fa": "کالای تحویل",
            "unit": "ad",
            "min_quantity": "1.000",
        },
        headers=_bearer(token),
    ).json()
    placement = client.post(
        "/api/v1/warehouse/placements/receive",
        json={"item_id": item["id"], "shelf_id": shelf["id"], "quantity": "10"},
        headers=_bearer(token),
    ).json()
    request = _make_request(client, token, item["id"], quantity="3")
    approved = client.post(
        f"/api/v1/warehouse/requests/{request['id']}/approve",
        json={"version": request["version"]},
        headers=_bearer(token),
    )
    assert approved.status_code == 200, approved.text
    detail = client.get(
        f"/api/v1/warehouse/requests/{request['id']}", headers=_bearer(token)
    ).json()
    fulfilled = client.post(
        f"/api/v1/warehouse/requests/{request['id']}/fulfill",
        json={
            "version": detail["version"],
            "lines": [
                {"line_id": line["id"], "placement_id": placement["id"]}
                for line in detail["lines"]
            ],
        },
        headers=_bearer(token),
    )
    assert fulfilled.status_code == 200, fulfilled.text

    rows = _rows(factory, "ItemRequestFulfilled", entity_id=request["id"])
    assert len(rows) == 1
    assert rows[0]["payload"]["audience"]["users"] == [str(request["requested_by"])]


@requires_db
def test_refused_fulfillment_leaves_no_outbox_row(pg):  # type: ignore[no-untyped-def]
    """Rollback case (SC-001): a business action that fails (insufficient
    stock) rolls its capture back with it — no orphan outbox row."""
    client, factory = pg
    token = _admin_token(client)
    workplace = client.get("/api/v1/org/workplaces", headers=_bearer(token)).json()["items"][0]
    tag = _unique_tag()
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": workplace["id"],
            "code": f"REF-WH-{tag}",
            "name": f"Refuse warehouse {tag}",
            "name_fa": "انبار رد",
        },
        headers=_bearer(token),
    ).json()
    shelf = client.post(
        f"/api/v1/warehouse/warehouses/{warehouse['id']}/shelves",
        json={"code": "R-01"},
        headers=_bearer(token),
    ).json()
    item = client.post(
        "/api/v1/warehouse/items",
        json={
            "name": f"Refuse item {tag}",
            "name_fa": "کالای رد",
            "unit": "ad",
            "min_quantity": "1.000",
        },
        headers=_bearer(token),
    ).json()
    placement = client.post(
        "/api/v1/warehouse/placements/receive",
        json={"item_id": item["id"], "shelf_id": shelf["id"], "quantity": "2"},
        headers=_bearer(token),
    ).json()
    request = _make_request(client, token, item["id"], quantity="9")
    approved = client.post(
        f"/api/v1/warehouse/requests/{request['id']}/approve",
        json={"version": request["version"]},
        headers=_bearer(token),
    )
    assert approved.status_code == 200, approved.text
    detail = client.get(
        f"/api/v1/warehouse/requests/{request['id']}", headers=_bearer(token)
    ).json()
    refused = client.post(
        f"/api/v1/warehouse/requests/{request['id']}/fulfill",
        json={
            "version": detail["version"],
            "lines": [
                {"line_id": line["id"], "placement_id": placement["id"]}
                for line in detail["lines"]
            ],
        },
        headers=_bearer(token),
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "INSUFFICIENT_STOCK"

    assert _rows(factory, "ItemRequestFulfilled", entity_id=request["id"]) == []
    # The business transaction rolled back with the capture: still approved.
    after = client.get(
        f"/api/v1/warehouse/requests/{request['id']}", headers=_bearer(token)
    ).json()
    assert after["status"] == "approved"
    assert after["fulfilled_at"] is None


@requires_db
def test_asset_lifecycle_capture(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    admin_id = _admin_id(client, token)
    workplace = client.get("/api/v1/org/workplaces", headers=_bearer(token)).json()["items"][0]
    tag = _unique_tag()
    employee_id, user_id, _email = _create_employee(client, token, workplace["id"], tag)
    asset = client.post(
        "/api/v1/warehouse/assets",
        json={
            "name": f"Capture asset {tag}",
            "name_fa": f"دارایی capture {tag}",
            "serial": f"CAP-AS-{tag}",
        },
        headers=_bearer(token),
    ).json()
    assigned = client.post(
        f"/api/v1/warehouse/assets/{asset['id']}/assign",
        json={"version": asset["version"], "target_type": "employee", "employee_id": employee_id},
        headers=_bearer(token),
    )
    assert assigned.status_code == 200, assigned.text

    rows = _rows(factory, "AssetAssigned", entity_id=asset["id"])
    assert len(rows) == 1
    row = rows[0]
    assert str(row["actor_user_id"]) == admin_id
    assert row["payload"]["holder_user_id"] == user_id
    assert row["payload"]["employee_id"] == employee_id
    assert row["payload"]["asset_serial"] == asset["serial"]
    assert set(row["payload"]["audience"]["users"]) == {user_id, admin_id}

    returned = client.post(
        f"/api/v1/warehouse/assets/{asset['id']}/return",
        json={"version": assigned.json()["version"], "note": "handover"},
        headers=_bearer(token),
    )
    assert returned.status_code == 200, returned.text
    rows = _rows(factory, "AssetReturned", entity_id=asset["id"])
    assert len(rows) == 1
    assert rows[0]["payload"]["holder_user_id"] == user_id


@requires_db
def test_loan_lifecycle_capture(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    admin_id = _admin_id(client, token)
    workplace = client.get("/api/v1/org/workplaces", headers=_bearer(token)).json()["items"][0]
    tag = _unique_tag()
    _employee_id, user_id, email = _create_employee(client, token, workplace["id"], tag)
    year = current_jalali_year()
    listed = client.get(
        f"/api/v1/loan/policies?page_size=100&year={year}", headers=_bearer(token)
    ).json()
    for existing in listed["items"]:
        if existing["workplace"]["id"] == workplace["id"]:
            client.post(
                f"/api/v1/loan/policies/{existing['id']}/retire",
                json={"version": existing["version"]},
                headers=_bearer(token),
            )
    policy = client.post(
        "/api/v1/loan/policies",
        json={
            "workplace_id": workplace["id"],
            "year": year,
            "max_loan_amount": "100000000.00",
            "max_guarantee_amount": "50000000.00",
            "max_request_count_per_year": 5,
            "max_request_count_lifetime": 10,
        },
        headers=_bearer(token),
    )
    assert policy.status_code == 201, policy.text

    requester = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "cap-password-1"}
    )
    assert requester.status_code == 200, requester.text
    requester_token = requester.json()["access_token"]
    submitted = client.post(
        "/api/v1/loan/requests",
        json={"type": "loan", "amount": "10000000.00"},
        headers=_bearer(requester_token),
    )
    assert submitted.status_code == 201, submitted.text
    loan = submitted.json()

    rows = _rows(factory, "LoanRequestCreated", entity_id=loan["id"])
    assert len(rows) == 1
    row = rows[0]
    assert str(row["actor_user_id"]) == user_id
    assert row["payload"]["amount"] == "10000000.00"
    assert row["payload"]["loan_type"] == "loan"
    assert row["payload"]["requester_user_id"] == user_id
    assert user_id in row["payload"]["audience"]["users"]
    assert row["payload"]["audience"]["scope"]["permission"] == "loan:request:read"

    activated = client.post(
        f"/api/v1/loan/requests/{loan['id']}/activate",
        json={"version": loan["version"]},
        headers=_bearer(token),
    )
    assert activated.status_code == 200, activated.text
    rows = _rows(factory, "LoanRequestActivated", entity_id=loan["id"])
    assert len(rows) == 1
    assert str(rows[0]["actor_user_id"]) == admin_id
    assert rows[0]["payload"]["requester_user_id"] == user_id

    settled = client.post(
        f"/api/v1/loan/requests/{loan['id']}/settle",
        json={"version": activated.json()["version"]},
        headers=_bearer(token),
    )
    assert settled.status_code == 200, settled.text
    rows = _rows(factory, "LoanRequestSettled", entity_id=loan["id"])
    assert len(rows) == 1
    assert rows[0]["payload"]["requester_user_id"] == user_id
