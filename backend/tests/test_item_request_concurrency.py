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
from app.modules.warehouse.models import InventoryPlacement, StockMovement
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="the fulfillment contention test requires real PostgreSQL row locking",
)

_RUN = uuid.uuid4().hex[:6]


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


@requires_db
def test_concurrent_fulfillments_of_different_requests(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)

    workplace = client.get("/api/v1/org/workplaces", headers=_bearer(token)).json()["items"][0]
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": workplace["id"],
            "code": f"WH-{_RUN}",
            "name": "Contention warehouse",
            "name_fa": "انبار رقابت",
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
            "name": f"Contention item {_RUN}",
            "name_fa": f"کالای رقابت {_RUN}",
            "unit": "ad",
        },
        headers=_bearer(token),
    ).json()
    placement = client.post(
        "/api/v1/warehouse/placements/receive",
        json={"item_id": item["id"], "shelf_id": shelf["id"], "quantity": "6"},
        headers=_bearer(token),
    ).json()
    placement_id = placement["id"]

    approved: list[dict] = []
    for _ in range(2):
        created = client.post(
            "/api/v1/warehouse/requests",
            json={
                "purpose_description": f"Contention {_RUN}",
                "lines": [{"item_id": item["id"], "quantity": "6.000"}],
            },
            headers=_bearer(token),
        ).json()
        approved_response = client.post(
            f"/api/v1/warehouse/requests/{created['id']}/approve",
            json={"version": created["version"]},
            headers=_bearer(token),
        )
        assert approved_response.status_code == 200, approved_response.text
        approved.append(approved_response.json())

    outcomes: list[str] = []

    def fulfill(request: dict) -> None:
        line = request["lines"][0]
        response = client.post(
            f"/api/v1/warehouse/requests/{request['id']}/fulfill",
            json={
                "version": request["version"],
                "lines": [{"line_id": line["id"], "placement_id": placement_id}],
            },
            headers=_bearer(token),
        )
        if response.status_code == 200:
            outcomes.append("ok")
        elif response.json().get("code") == INSUFFICIENT_STOCK:
            outcomes.append(INSUFFICIENT_STOCK)
        else:
            outcomes.append(response.json().get("code", "unknown"))

    thread_one = Thread(target=fulfill, args=(approved[0],))
    thread_two = Thread(target=fulfill, args=(approved[1],))
    thread_one.start()
    thread_two.start()
    thread_one.join()
    thread_two.join()

    assert outcomes.count("ok") == 1, f"outcomes={outcomes}"
    assert outcomes.count(INSUFFICIENT_STOCK) == 1, f"outcomes={outcomes}"

    with factory() as session:
        final = session.scalar(
            select(InventoryPlacement.quantity).where(
                InventoryPlacement.id == uuid.UUID(placement_id)
            )
        )
        movement_count = len(
            session.scalars(
                select(StockMovement).where(
                    StockMovement.movement_type == "fulfillment",
                    StockMovement.placement_id == uuid.UUID(placement_id),
                )
            ).all()
        )
    assert final == Decimal("0.000")
    assert movement_count == 1
