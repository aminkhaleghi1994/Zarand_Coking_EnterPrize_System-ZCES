import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.main import create_app
from app.modules.warehouse.models import StockAlert
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="warehouse integration tests require a real database (PG service in CI)",
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


@pytest.fixture()
def _setup(pg):  # type: ignore[no-untyped-def]
    """One warehouse + shelf + item(min 10) with 50 received; returns ids."""
    client, _factory = pg
    token = _admin_token(client)
    workplace = client.get("/api/v1/org/workplaces", headers=_bearer(token)).json()["items"][0]
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": workplace["id"],
            "code": f"WH-{_unique_tag()}",
            "name": "Alert warehouse",
            "name_fa": "انبار هشدار",
        },
        headers=_bearer(token),
    ).json()
    shelf = client.post(
        f"/api/v1/warehouse/warehouses/{warehouse['id']}/shelves",
        json={"code": "A-01"},
        headers=_bearer(token),
    ).json()
    item = client.post(
        "/api/v1/warehouse/items",
        json={
            "name": f"Alert item {_unique_tag()}",
            "name_fa": f"کالای هشدار {_unique_tag()}",
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
    return client, token, item, shelf, warehouse, placement


def _issue(client: TestClient, token: str, placement: dict, quantity: str) -> object:
    return client.post(
        "/api/v1/warehouse/placements/issue",
        json={"placement_id": placement["id"], "quantity": quantity},
        headers=_bearer(token),
    )


def _receive(client: TestClient, token: str, item: dict, shelf: dict, quantity: str) -> object:
    return client.post(
        "/api/v1/warehouse/placements/receive",
        json={"item_id": item["id"], "shelf_id": shelf["id"], "quantity": quantity},
        headers=_bearer(token),
    )


def _active_alerts(client: TestClient, token: str) -> list[dict]:
    response = client.get(
        "/api/v1/warehouse/alerts", params={"active": "true"}, headers=_bearer(token)
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


@requires_db
def test_alert_raised_when_dropping_below_threshold(_setup):  # type: ignore[no-untyped-def]
    client, token, _item, _shelf, warehouse, placement = _setup
    _issue(client, token, placement, "45")  # 50 -> 5 < 10

    alerts = _active_alerts(client, token)
    mine = [a for a in alerts if a["placement_id"] == placement["id"]]
    assert len(mine) == 1
    assert mine[0]["quantity_at_alert"] == "5.000"
    assert mine[0]["threshold_at_alert"] == "10.000"
    assert mine[0]["current_quantity"] == "5.000"
    assert mine[0]["warehouse"]["id"] == warehouse["id"]


@requires_db
def test_no_duplicate_alert_while_below(_setup):  # type: ignore[no-untyped-def]
    client, token, _item, _shelf, _warehouse, placement = _setup
    _issue(client, token, placement, "45")
    _issue(client, token, placement, "1")  # still below

    alerts = [a for a in _active_alerts(client, token) if a["placement_id"] == placement["id"]]
    assert len(alerts) == 1


@requires_db
def test_recovery_resolves_and_redrop_raises_new_alert(_setup):  # type: ignore[no-untyped-def]
    client, token, item, shelf, _warehouse, placement = _setup
    _issue(client, token, placement, "45")
    first = [a for a in _active_alerts(client, token) if a["placement_id"] == placement["id"]]
    assert len(first) == 1

    _receive(client, token, item, shelf, "20")  # 5 -> 25 >= 10: resolved
    assert [a for a in _active_alerts(client, token) if a["placement_id"] == placement["id"]] == []

    _issue(client, token, placement, "20")  # 25 -> 5 < 10 again
    second = [a for a in _active_alerts(client, token) if a["placement_id"] == placement["id"]]
    assert len(second) == 1
    assert second[0]["id"] != first[0]["id"]


@requires_db
def test_item_retirement_resolves_active_alert(pg, _setup):  # type: ignore[no-untyped-def]
    client, token, item, _shelf, _warehouse, placement = _setup
    _issue(client, token, placement, "45")
    assert len(_active_alerts(client, token)) >= 1

    retired = client.post(
        f"/api/v1/warehouse/items/{item['id']}/retire",
        json={"version": item["version"]},
        headers=_bearer(token),
    )
    assert retired.status_code == 200, retired.text

    resolved_ids = {a["id"] for a in _active_alerts(client, token)}
    _ = resolved_ids
    with pg[1]() as session:
        alert = session.scalar(
            select(StockAlert).where(StockAlert.placement_id == uuid.UUID(placement["id"]))
        )
    assert alert is not None
    assert alert.resolved_at is not None
    assert alert.resolve_reason == "item_retired"


@requires_db
def test_alerts_endpoint_requires_permission(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    response = client.get("/api/v1/warehouse/alerts")
    assert response.status_code == 401  # unauthenticated
