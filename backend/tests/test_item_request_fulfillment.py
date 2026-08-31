import os
import uuid
from decimal import Decimal
from threading import Thread

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.core.errors import INSUFFICIENT_STOCK
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.warehouse.models import InventoryPlacement, StockMovement
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="item-request fulfillment tests require a real database (PG service in CI)",
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


def _create_item(client: TestClient, token: str, tag: str) -> str:
    response = client.post(
        "/api/v1/warehouse/items",
        json={
            "name": f"Fulfill item {tag}",
            "name_fa": f"کالای تحویل {tag}",
            "code": f"FLF-{tag}",
            "unit": "ad",
            "min_quantity": "0",
        },
        headers=_bearer(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _setup_stock(client: TestClient, token: str, item_id: str, quantity: str) -> str:
    workplace = client.get("/api/v1/org/workplaces", headers=_bearer(token)).json()["items"][0]
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": workplace["id"],
            "code": f"WH-{_unique_tag()}",
            "name": "Fulfill warehouse",
            "name_fa": "انبار تحویل",
        },
        headers=_bearer(token),
    ).json()
    shelf = client.post(
        f"/api/v1/warehouse/warehouses/{warehouse['id']}/shelves",
        json={"code": "F-01"},
        headers=_bearer(token),
    ).json()
    placement = client.post(
        "/api/v1/warehouse/placements/receive",
        json={"item_id": item_id, "shelf_id": shelf["id"], "quantity": quantity},
        headers=_bearer(token),
    ).json()
    return placement["id"]


def _composed_request(client: TestClient, token: str, lines: list[tuple[str, str]]) -> dict:  # type: ignore[no-untyped-def]
    created = client.post(
        "/api/v1/warehouse/requests",
        json={
            "purpose_description": f"Fulfill flow {_unique_tag()}",
            "lines": [{"item_id": item_id, "quantity": quantity} for item_id, quantity in lines],
        },
        headers=_bearer(token),
    )
    assert created.status_code == 201, created.text
    request = created.json()
    approved = client.post(
        f"/api/v1/warehouse/requests/{request['id']}/approve",
        json={"version": request["version"]},
        headers=_bearer(token),
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


@requires_db
def test_fulfill_happy_path_and_atomic_overdraw(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    item_a = _create_item(client, token, _unique_tag())
    item_b = _create_item(client, token, _unique_tag())
    placement_a = _setup_stock(client, token, item_a, "10")
    placement_b = _setup_stock(client, token, item_b, "5")

    request = _composed_request(client, token, [(item_a, "4"), (item_b, "2")])
    line_a = next(line for line in request["lines"] if line["item"]["id"] == item_a)
    line_b = next(line for line in request["lines"] if line["item"]["id"] == item_b)

    fulfilled = client.post(
        f"/api/v1/warehouse/requests/{request['id']}/fulfill",
        json={
            "version": request["version"],
            "lines": [
                {"line_id": line_a["id"], "placement_id": placement_a},
                {"line_id": line_b["id"], "placement_id": placement_b},
            ],
        },
        headers=_bearer(token),
    )
    assert fulfilled.status_code == 200, fulfilled.text
    assert fulfilled.json()["status"] == "fulfilled"
    assert fulfilled.json()["fulfilled_at"] is not None

    with factory() as session:
        qty_a = session.scalar(
            select(InventoryPlacement.quantity).where(
                InventoryPlacement.id == uuid.UUID(placement_a)
            )
        )
        qty_b = session.scalar(
            select(InventoryPlacement.quantity).where(
                InventoryPlacement.id == uuid.UUID(placement_b)
            )
        )
        fulfillment_movements = session.scalars(
            select(StockMovement).where(
                StockMovement.movement_type == "fulfillment",
                StockMovement.placement_id.in_([uuid.UUID(placement_a), uuid.UUID(placement_b)]),
            )
        ).all()
    assert qty_a == Decimal("6.000")
    assert qty_b == Decimal("3.000")
    assert len(fulfillment_movements) == 2

    with factory() as session:
        entry = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "REQUEST_FULFILLED",
                AuditLog.entity_id == uuid.UUID(request["id"]),
            )
        )
    assert entry is not None
    assert entry.after_snapshot is not None
    assert len(entry.after_snapshot["movements"]) == 2

    # Atomic overdraw: a request whose line exceeds available stock
    overdraw_request = _composed_request(client, token, [(item_a, "99")])
    overdraw_line = overdraw_request["lines"][0]
    refused = client.post(
        f"/api/v1/warehouse/requests/{overdraw_request['id']}/fulfill",
        json={
            "version": overdraw_request["version"],
            "lines": [{"line_id": overdraw_line["id"], "placement_id": placement_a}],
        },
        headers=_bearer(token),
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "INSUFFICIENT_STOCK"
    assert refused.json()["details"]["available"] == "6.000"

    with factory() as session:
        qty_a_after = session.scalar(
            select(InventoryPlacement.quantity).where(
                InventoryPlacement.id == uuid.UUID(placement_a)
            )
        )
        fulfillment_count_after = len(
            session.scalars(
                select(StockMovement).where(
                    StockMovement.movement_type == "fulfillment",
                    StockMovement.placement_id == uuid.UUID(placement_a),
                )
            ).all()
        )
    assert qty_a_after == Decimal("6.000")  # unchanged
    assert fulfillment_count_after == 1  # no orphan movement from the refused attempt


@requires_db
def test_double_fulfillment_and_pending_refusal(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    item_a = _create_item(client, token, _unique_tag())
    placement_a = _setup_stock(client, token, item_a, "10")

    request = _composed_request(client, token, [(item_a, "2")])
    line = request["lines"][0]

    first = client.post(
        f"/api/v1/warehouse/requests/{request['id']}/fulfill",
        json={
            "version": request["version"],
            "lines": [{"line_id": line["id"], "placement_id": placement_a}],
        },
        headers=_bearer(token),
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/v1/warehouse/requests/{request['id']}/fulfill",
        json={
            "version": first.json()["version"],
            "lines": [{"line_id": line["id"], "placement_id": placement_a}],
        },
        headers=_bearer(token),
    )
    assert second.status_code == 422
    assert second.json()["code"] == "BUSINESS_RULE_VIOLATION"

    pending = client.post(
        "/api/v1/warehouse/requests",
        json={
            "purpose_description": f"Pending refusal {_unique_tag()}",
            "lines": [{"item_id": item_a, "quantity": "1"}],
        },
        headers=_bearer(token),
    ).json()
    pending_fulfill = client.post(
        f"/api/v1/warehouse/requests/{pending['id']}/fulfill",
        json={
            "version": pending["version"],
            "lines": [{"line_id": pending["lines"][0]["id"], "placement_id": placement_a}],
        },
        headers=_bearer(token),
    )
    assert pending_fulfill.status_code == 422
    assert pending_fulfill.json()["code"] == "BUSINESS_RULE_VIOLATION"


@requires_db
def test_concurrent_fulfillments_of_different_requests(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    item_a = _create_item(client, token, _unique_tag())
    placement_a = _setup_stock(client, token, item_a, "6")

    request_one = _composed_request(client, token, [(item_a, "6")])
    request_two = _composed_request(client, token, [(item_a, "6")])

    line_one = request_one["lines"][0]
    line_two = request_two["lines"][0]

    outcomes: list[str] = []

    def fulfill(request: dict, line: dict) -> None:  # type: ignore[no-untyped-def]
        response = client.post(
            f"/api/v1/warehouse/requests/{request['id']}/fulfill",
            json={
                "version": request["version"],
                "lines": [{"line_id": line["id"], "placement_id": placement_a}],
            },
            headers=_bearer(token),
        )
        if response.status_code == 200:
            outcomes.append("ok")
        elif response.json().get("code") == INSUFFICIENT_STOCK:
            outcomes.append(INSUFFICIENT_STOCK)
        else:
            outcomes.append(response.json().get("code", "unknown"))

    thread_one = Thread(target=fulfill, args=(request_one, line_one))
    thread_two = Thread(target=fulfill, args=(request_two, line_two))
    thread_one.start()
    thread_two.start()
    thread_one.join()
    thread_two.join()

    assert outcomes.count("ok") == 1
    assert outcomes.count(INSUFFICIENT_STOCK) == 1

    with factory() as session:
        final = session.scalar(
            select(InventoryPlacement.quantity).where(
                InventoryPlacement.id == uuid.UUID(placement_a)
            )
        )
    assert final == Decimal("0.000")
