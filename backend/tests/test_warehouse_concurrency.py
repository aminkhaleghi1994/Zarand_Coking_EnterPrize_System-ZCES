import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.common.scope import ScopeContext
from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.core.errors import INSUFFICIENT_STOCK, AppError
from app.main import create_app
from app.modules.user import repository as user_repository
from app.modules.user.models import User
from app.modules.warehouse import service
from app.modules.warehouse.models import InventoryPlacement, MovementType, StockMovement
from app.modules.warehouse.schemas import IssueIn, ReceiveIn
from app.seeds.seed_dev import run_seed


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


_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="the concurrency test requires real PostgreSQL row locking",
)

_RUN = uuid.uuid4().hex[:6]

ISSUE_QUANTITY = Decimal("3")
INITIAL_QUANTITY = Decimal("10")
THREADS = 8
EXPECTED_SUCCESSES = 3  # floor(10 / 3)
EXPECTED_FINAL = Decimal("1.000")


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


def _admin_context(factory) -> ScopeContext:  # type: ignore[no-untyped-def]
    with factory() as session:
        settings = get_settings()
        admin = session.scalar(
            select(User).where(User.email == (settings.INITIAL_ADMIN_EMAIL or "").lower())
        )
        assert admin is not None
        context = user_repository.load_scope_context(session, str(admin.id))
    assert context is not None
    return context


@requires_db
def test_concurrent_issues_never_oversell(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    context = _admin_context(factory)
    token = _admin_token(client)

    workplace = client.get("/api/v1/org/workplaces", headers=_bearer(token)).json()["items"][0]
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": workplace["id"],
            "code": f"WH-{_RUN}",
            "name": "Concurrency warehouse",
            "name_fa": "انبار همزمانی",
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
            "name": f"Concurrency item {_RUN}",
            "name_fa": f"کالای همزمانی {_RUN}",
            "unit": "ad",
        },
        headers=_bearer(token),
    ).json()

    with factory() as session:
        placement, _item, _shelf, _warehouse = service.receive_stock(
            session,
            context,
            ReceiveIn(
                item_id=uuid.UUID(item["id"]),
                shelf_id=uuid.UUID(shelf["id"]),
                quantity=INITIAL_QUANTITY,
            ),
        )
        placement_id = placement.id

    def issue_one(index: int) -> str:
        try:
            with factory() as session:
                service.issue_stock(
                    session,
                    context,
                    IssueIn(placement_id=placement_id, quantity=ISSUE_QUANTITY, reason=f"t{index}"),
                )
            return "ok"
        except AppError as exc:
            assert exc.code == INSUFFICIENT_STOCK, exc.code
            return exc.code

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        outcomes = list(executor.map(issue_one, range(THREADS)))

    successes = outcomes.count("ok")
    assert successes == EXPECTED_SUCCESSES
    assert outcomes.count(INSUFFICIENT_STOCK) == THREADS - EXPECTED_SUCCESSES

    with factory() as session:
        final = session.scalar(
            select(InventoryPlacement.quantity).where(InventoryPlacement.id == placement_id)
        )
        movement_count = session.scalar(
            select(func.count())
            .select_from(StockMovement)
            .where(
                StockMovement.placement_id == placement_id,
                StockMovement.movement_type == MovementType.ISSUE,
            )
        )
        deltas = session.scalars(
            select(StockMovement.quantity_delta).where(StockMovement.placement_id == placement_id)
        ).all()

    assert final == EXPECTED_FINAL
    assert movement_count == EXPECTED_SUCCESSES
    assert sum(deltas) == EXPECTED_FINAL
