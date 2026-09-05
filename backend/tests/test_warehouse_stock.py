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
from app.core.security import hash_password
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.user import repository as user_repository
from app.modules.user.models import Role, ScopeAssignment, ScopeLevel, User, UserRole, Workplace
from app.modules.warehouse import service
from app.modules.warehouse.schemas import ReceiveIn
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


def _setup_warehouse_and_shelf(client: TestClient, token: str) -> tuple[str, str]:
    workplace = client.get(
        "/api/v1/org/workplaces", params={"search": "Coke Plant 1"}, headers=_bearer(token)
    ).json()["items"][0]
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": workplace["id"],
            "code": f"WH-{_unique_tag()}",
            "name": "Stock test warehouse",
            "name_fa": "انبار تست",
        },
        headers=_bearer(token),
    ).json()
    shelf = client.post(
        f"/api/v1/warehouse/warehouses/{warehouse['id']}/shelves",
        json={"code": "S-01"},
        headers=_bearer(token),
    ).json()
    return warehouse["id"], shelf["id"]


def _create_item(client: TestClient, token: str, tag: str) -> str:
    response = client.post(
        "/api/v1/warehouse/items",
        json={
            "name": f"Stock item {tag}",
            "name_fa": f"کالای موجودی {tag}",
            "code": f"ST-{tag}",
            "unit": "ad",
            "min_quantity": "10.000",
        },
        headers=_bearer(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@requires_db
def test_receive_creates_placement_and_receive_movement(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    warehouse_id, shelf_id = _setup_warehouse_and_shelf(client, token)
    item_id = _create_item(client, token, _unique_tag())

    response = client.post(
        "/api/v1/warehouse/placements/receive",
        json={"item_id": item_id, "shelf_id": shelf_id, "quantity": "50", "reason": "initial"},
        headers=_bearer(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["quantity"] == "50.000"

    movements = client.get(
        f"/api/v1/warehouse/placements/{body['id']}/movements", headers=_bearer(token)
    ).json()
    assert movements["total"] == 1
    movement = movements["items"][0]
    assert movement["movement_type"] == "receive"
    assert movement["quantity_delta"] == "50.000"
    assert movement["resulting_quantity"] == "50.000"


@requires_db
def test_issue_decrements_and_overdraw_rejected(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    warehouse_id, shelf_id = _setup_warehouse_and_shelf(client, token)
    item_id = _create_item(client, token, _unique_tag())
    placement = client.post(
        "/api/v1/warehouse/placements/receive",
        json={"item_id": item_id, "shelf_id": shelf_id, "quantity": "50"},
        headers=_bearer(token),
    ).json()

    issued = client.post(
        "/api/v1/warehouse/placements/issue",
        json={"placement_id": placement["id"], "quantity": "15", "reason": "work order"},
        headers=_bearer(token),
    )
    assert issued.status_code == 200, issued.text
    assert issued.json()["quantity"] == "35.000"

    overdraw = client.post(
        "/api/v1/warehouse/placements/issue",
        json={"placement_id": placement["id"], "quantity": "999"},
        headers=_bearer(token),
    )
    assert overdraw.status_code == 409
    assert overdraw.json()["code"] == "INSUFFICIENT_STOCK"
    assert overdraw.json()["details"]["available"] == "35.000"

    movements = client.get(
        f"/api/v1/warehouse/placements/{placement['id']}/movements", headers=_bearer(token)
    ).json()
    assert movements["total"] == 2  # receive + issue; overdraw left no trace
    total_delta = sum(Decimal(m["quantity_delta"]) for m in movements["items"])
    assert total_delta == Decimal("35.000")


@requires_db
def test_adjust_absolute_recount_semantics(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    warehouse_id, shelf_id = _setup_warehouse_and_shelf(client, token)
    item_id = _create_item(client, token, _unique_tag())
    placement = client.post(
        "/api/v1/warehouse/placements/receive",
        json={"item_id": item_id, "shelf_id": shelf_id, "quantity": "50"},
        headers=_bearer(token),
    ).json()

    adjusted = client.post(
        "/api/v1/warehouse/placements/adjust",
        json={"placement_id": placement["id"], "quantity": "48.5", "reason": "recount"},
        headers=_bearer(token),
    )
    assert adjusted.status_code == 200, adjusted.text
    assert adjusted.json()["quantity"] == "48.500"

    no_op = client.post(
        "/api/v1/warehouse/placements/adjust",
        json={"placement_id": placement["id"], "quantity": "48.5"},
        headers=_bearer(token),
    )
    assert no_op.status_code == 422
    assert no_op.json()["code"] == "VALIDATION_ERROR"

    negative = client.post(
        "/api/v1/warehouse/placements/adjust",
        json={"placement_id": placement["id"], "quantity": "-1"},
        headers=_bearer(token),
    )
    assert negative.status_code == 422


@requires_db
def test_adjust_permission_split_from_receive_issue(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    warehouse_id, shelf_id = _setup_warehouse_and_shelf(client, token)
    item_id = _create_item(client, token, _unique_tag())
    placement = client.post(
        "/api/v1/warehouse/placements/receive",
        json={"item_id": item_id, "shelf_id": shelf_id, "quantity": "50"},
        headers=_bearer(token),
    ).json()

    email = f"picker-{_RUN}@zarandsteel.ir"
    with factory() as session:
        from app.modules.warehouse.models import Warehouse

        warehouse_row = session.scalar(
            select(Warehouse).where(Warehouse.id == uuid.UUID(warehouse_id))
        )
        assert warehouse_row is not None
        workplace = session.scalar(
            select(Workplace).where(Workplace.id == warehouse_row.workplace_id)
        )
        assert workplace is not None
        user = User(
            email=email,
            username=f"picker-{_RUN}",
            hashed_password=hash_password("picker-password-1"),
            is_active=True,
        )
        session.add(user)
        session.flush()
        role = session.scalar(select(Role).where(Role.name == "WarehouseKeeper"))
        assert role is not None
        session.add(UserRole(user_id=user.id, role_id=role.id))
        session.flush()
        for code in ("warehouse:stock:receive", "warehouse:stock:issue", "warehouse:stock:read"):
            module, resource, operation = code.split(":", 2)
            session.add(
                ScopeAssignment(
                    user_id=user.id,
                    level=ScopeLevel.WORKPLACE,
                    module=module,
                    resource=resource,
                    operation=operation,
                    workplace_id=workplace.id,
                )
            )
        session.commit()

    picker_token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "picker-password-1"}
    ).json()["access_token"]

    can_issue = client.post(
        "/api/v1/warehouse/placements/issue",
        json={"placement_id": placement["id"], "quantity": "5"},
        headers=_bearer(picker_token),
    )
    assert can_issue.status_code == 200, can_issue.text

    denied_adjust = client.post(
        "/api/v1/warehouse/placements/adjust",
        json={"placement_id": placement["id"], "quantity": "40"},
        headers=_bearer(picker_token),
    )
    assert denied_adjust.status_code == 403
    assert denied_adjust.json()["code"] == "AUTHORIZATION_DENIED"


@requires_db
def test_stock_movements_audited(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    warehouse_id, shelf_id = _setup_warehouse_and_shelf(client, _admin_token(client))
    item_id = _create_item(client, _admin_token(client), _unique_tag())
    context = _admin_context(factory)

    with factory() as session:
        placement, _item, _shelf, _warehouse = service.receive_stock(
            session,
            context,
            ReceiveIn(
                item_id=uuid.UUID(item_id), shelf_id=uuid.UUID(shelf_id), quantity=Decimal("5")
            ),
        )
        placement_id = placement.id

    with factory() as session:
        entry = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "STOCK_RECEIVED",
                AuditLog.after_snapshot["placement_id"].astext == str(placement_id),
            )
        )
    assert entry is not None
    assert entry.after_snapshot is not None
    assert entry.after_snapshot["quantity_after"] == "5.000"
