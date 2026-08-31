import os
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.common.scope import ScopeContext
from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.core.errors import AppError
from app.main import create_app
from app.modules.user import repository as user_repository
from app.modules.user.models import User
from app.modules.warehouse import contracts, service
from app.modules.warehouse.models import InventoryPlacement, StockAlert, StockMovement
from app.modules.warehouse.schemas import ReceiveIn
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="warehouse contract tests require a real database (PG service in CI)",
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


def _admin_context(factory) -> ScopeContext:  # type: ignore[no-untyped-def]
    with factory() as session:
        settings = get_settings()
        admin = session.scalar(
            select(User).where(User.email == (settings.INITIAL_ADMIN_EMAIL or "").lower())
        )
        assert admin is not None
        context = user_repository.load_scope_context(session, str(admin.id))
        user_id = admin.id
    assert context is not None
    return context, user_id


@pytest.fixture()
def _stock_setup(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    context, admin_user_id = _admin_context(factory)

    workplace = client.get("/api/v1/org/workplaces", headers=_bearer(token)).json()["items"][0]
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": workplace["id"],
            "code": f"WH-{_unique_tag()}",
            "name": "Contract warehouse",
            "name_fa": "انبار قرارداد",
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
            "name": f"Contract item {_unique_tag()}",
            "name_fa": f"کالای قرارداد {_unique_tag()}",
            "code": f"CNT-{_unique_tag()}",
            "unit": "ad",
            "min_quantity": "10.000",
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
                quantity=Decimal("10"),
            ),
        )
        placement_id = placement.id

    return {
        "factory": factory,
        "context": context,
        "admin_user_id": admin_user_id,
        "item_id": uuid.UUID(item["id"]),
        "shelf_id": uuid.UUID(shelf["id"]),
        "warehouse_id": uuid.UUID(warehouse["id"]),
        "placement_id": placement_id,
    }


@requires_db
def test_get_item_returns_view(pg, _stock_setup):  # type: ignore[no-untyped-def]
    _client, _factory = pg
    view = contracts.get_item(_stock_setup["factory"](), _stock_setup["item_id"])
    assert view is not None
    assert view.is_active
    assert view.min_quantity == Decimal("10.000")
    assert contracts.get_item(_stock_setup["factory"](), uuid.uuid4()) is None


@requires_db
def test_get_shelf_context_resolves_hierarchy(_stock_setup):  # type: ignore[no-untyped-def]
    session = _stock_setup["factory"]()
    shelf_context = contracts.get_shelf_context(session, _stock_setup["shelf_id"])
    session.close()
    assert shelf_context is not None
    assert shelf_context.warehouse_id == _stock_setup["warehouse_id"]
    assert shelf_context.complex_id is not None
    assert shelf_context.company_id is not None


@requires_db
def test_get_placement_for_stock_locks_and_returns(_stock_setup):  # type: ignore[no-untyped-def]
    session = _stock_setup["factory"]()
    placement = contracts.get_placement_for_stock(
        session, item_id=_stock_setup["item_id"], shelf_id=_stock_setup["shelf_id"]
    )
    session.close()
    assert placement is not None
    assert placement.quantity == Decimal("10.000")


@requires_db
def test_apply_fulfillment_issue_decrements_and_ledgers(_stock_setup):  # type: ignore[no-untyped-def]
    factory = _stock_setup["factory"]
    _context, admin_user_id = _stock_setup["context"], _stock_setup["admin_user_id"]
    with factory() as session:
        movement = contracts.apply_fulfillment_issue(
            session,
            placement_id=_stock_setup["placement_id"],
            quantity=Decimal("4"),
            actor_user_id=admin_user_id,
            reason="request 1",
        )
        session.commit()
    assert movement.quantity_delta == Decimal("-4.000")
    assert movement.resulting_quantity == Decimal("6.000")

    with factory() as session:
        final = session.scalar(
            select(InventoryPlacement.quantity).where(
                InventoryPlacement.id == _stock_setup["placement_id"]
            )
        )
        fulfillment = session.scalar(
            select(StockMovement).where(
                StockMovement.placement_id == _stock_setup["placement_id"],
                StockMovement.movement_type == "fulfillment",
            )
        )
    assert final == Decimal("6.000")
    assert fulfillment is not None


@requires_db
def test_apply_fulfillment_issue_overdraw_rejected_and_rolls_back(_stock_setup):  # type: ignore[no-untyped-def]
    factory = _stock_setup["factory"]
    _context, admin_user_id = _stock_setup["context"], _stock_setup["admin_user_id"]
    with (
        pytest.raises(AppError) as excinfo,
        factory() as session,
    ):
        contracts.apply_fulfillment_issue(
            session,
            placement_id=_stock_setup["placement_id"],
            quantity=Decimal("99"),
            actor_user_id=admin_user_id,
        )
    assert excinfo.value.code == "INSUFFICIENT_STOCK"

    with factory() as session:
        final = session.scalar(
            select(InventoryPlacement.quantity).where(
                InventoryPlacement.id == _stock_setup["placement_id"]
            )
        )
        movements = session.scalars(
            select(StockMovement.id).where(
                StockMovement.placement_id == _stock_setup["placement_id"]
            )
        ).all()
    assert final == Decimal("10.000")
    assert len(movements) == 1  # only the receive from setup


@requires_db
def test_apply_fulfillment_issue_evaluates_alerts(_stock_setup):  # type: ignore[no-untyped-def]
    factory = _stock_setup["factory"]
    _context, admin_user_id = _stock_setup["context"], _stock_setup["admin_user_id"]
    with factory() as session:
        contracts.apply_fulfillment_issue(
            session,
            placement_id=_stock_setup["placement_id"],
            quantity=Decimal("4"),  # 10 -> 6 < min 10
            actor_user_id=admin_user_id,
        )
        session.commit()
        alert = session.scalar(
            select(StockAlert).where(
                StockAlert.placement_id == _stock_setup["placement_id"],
                StockAlert.resolved_at.is_(None),
            )
        )
    assert alert is not None
    assert alert.quantity_at_alert == Decimal("6.000")


@requires_db
def test_apply_fulfillment_issue_does_not_commit_caller_transaction(_stock_setup):  # type: ignore[no-untyped-def]
    factory = _stock_setup["factory"]
    _context, admin_user_id = _stock_setup["context"], _stock_setup["admin_user_id"]
    with factory() as session:
        contracts.apply_fulfillment_issue(
            session,
            placement_id=_stock_setup["placement_id"],
            quantity=Decimal("2"),
            actor_user_id=admin_user_id,
        )
        session.rollback()

    with factory() as session:
        final = session.scalar(
            select(InventoryPlacement.quantity).where(
                InventoryPlacement.id == _stock_setup["placement_id"]
            )
        )
    assert final == Decimal("10.000")
