import os
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.core.security import hash_password
from app.main import create_app
from app.modules.user.models import Role, ScopeAssignment, ScopeLevel, User, UserRole
from app.modules.warehouse.models import InventoryPlacement, ItemCatalog, Shelf, Warehouse
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


def _workplace_id(factory, code: str) -> uuid.UUID:  # type: ignore[no-untyped-def]
    from app.modules.user.models import Workplace

    with factory() as session:
        workplace = session.scalar(select(Workplace).where(Workplace.code == code))
        assert workplace is not None
        return workplace.id


def _scoped_keeper_token(
    client: TestClient,
    factory,
    tag: str,
    workplace_id: uuid.UUID,  # type: ignore[no-untyped-def]
) -> str:
    """User with WarehouseKeeper role + workplace-level warehouse scope."""
    email = f"keeper-{_RUN}-{tag}@zarandsteel.ir"
    with factory() as session:
        user = User(
            email=email,
            username=f"keeper-{_RUN}-{tag}",
            hashed_password=hash_password("keeper-password-1"),
            is_active=True,
        )
        session.add(user)
        session.flush()
        role = session.scalar(select(Role).where(Role.name == "WarehouseKeeper"))
        assert role is not None
        session.add(UserRole(user_id=user.id, role_id=role.id))
        session.flush()
        for code in (
            "warehouse:warehouse:read",
            "warehouse:warehouse:create",
            "warehouse:shelf:create",
            "warehouse:shelf:read",
        ):
            module, resource, operation = code.split(":", 2)
            session.add(
                ScopeAssignment(
                    user_id=user.id,
                    level=ScopeLevel.WORKPLACE,
                    module=module,
                    resource=resource,
                    operation=operation,
                    workplace_id=workplace_id,
                )
            )
        session.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "keeper-password-1"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _seed_stock(
    factory,
    warehouse: Warehouse,
    shelf: Shelf,
    quantity: str = "5.000",  # type: ignore[no-untyped-def]
) -> uuid.UUID:
    with factory() as session:
        item = ItemCatalog(
            name=f"Blocking item {_unique_tag()}",
            name_fa="کالای مسدودکننده",
            name_norm=f"blocking item {_unique_tag()}",
            unit="ad",
        )
        session.add(item)
        session.flush()
        placement = InventoryPlacement(
            shelf_id=shelf.id,
            item_id=item.id,
            quantity=Decimal(quantity),
        )
        session.add(placement)
        session.commit()
        return placement.id


@requires_db
def test_create_warehouse_anchored_to_workplace(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    workplace = _workplace_id(factory, "CP1")
    response = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": str(workplace),
            "code": f"WH-{_unique_tag()}",
            "name": "Main warehouse",
            "name_fa": "انبار اصلی",
        },
        headers=_bearer(token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["workplace_id"] == str(workplace)
    assert body["is_active"] is True

    with factory() as session:
        stored = session.scalar(select(Warehouse).where(Warehouse.id == uuid.UUID(body["id"])))
    assert stored is not None
    assert stored.company_id is not None
    assert stored.complex_id is not None


@requires_db
def test_duplicate_warehouse_code_rejected(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    workplace = _workplace_id(factory, "CP1")
    code = f"WH-{_unique_tag()}"
    first = client.post(
        "/api/v1/warehouse/warehouses",
        json={"workplace_id": str(workplace), "code": code, "name": "A", "name_fa": "الف"},
        headers=_bearer(token),
    )
    assert first.status_code == 201, first.text
    duplicate = client.post(
        "/api/v1/warehouse/warehouses",
        json={"workplace_id": str(workplace), "code": code, "name": "B", "name_fa": "ب"},
        headers=_bearer(token),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "DUPLICATE_RESOURCE"


@requires_db
def test_shelf_code_unique_per_warehouse(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    workplace = _workplace_id(factory, "CP1")
    code = f"WH-{_unique_tag()}"
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={"workplace_id": str(workplace), "code": code, "name": "A", "name_fa": "الف"},
        headers=_bearer(token),
    ).json()
    first = client.post(
        f"/api/v1/warehouse/warehouses/{warehouse['id']}/shelves",
        json={"code": "A-01"},
        headers=_bearer(token),
    )
    assert first.status_code == 201, first.text
    duplicate = client.post(
        f"/api/v1/warehouse/warehouses/{warehouse['id']}/shelves",
        json={"code": "A-01"},
        headers=_bearer(token),
    )
    assert duplicate.status_code == 409


@requires_db
def test_retire_shelf_blocked_while_stock_remains(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    workplace = _workplace_id(factory, "CP1")
    code = f"WH-{_unique_tag()}"
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={"workplace_id": str(workplace), "code": code, "name": "A", "name_fa": "الف"},
        headers=_bearer(token),
    ).json()
    shelf = client.post(
        f"/api/v1/warehouse/warehouses/{warehouse['id']}/shelves",
        json={"code": "A-01"},
        headers=_bearer(token),
    ).json()

    with factory() as session:
        stored_shelf = session.scalar(select(Shelf).where(Shelf.id == uuid.UUID(shelf["id"])))
        assert stored_shelf is not None
        stored_warehouse = session.scalar(
            select(Warehouse).where(Warehouse.id == uuid.UUID(warehouse["id"]))
        )
        assert stored_warehouse is not None
        placement_id = _seed_stock(factory, stored_warehouse, stored_shelf, quantity="5.000")

    blocked = client.post(
        f"/api/v1/warehouse/shelves/{shelf['id']}/retire",
        json={"version": shelf["version"]},
        headers=_bearer(token),
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "BUSINESS_RULE_VIOLATION"
    blocking_ids = {
        entry["placement_id"] for entry in blocked.json()["details"]["blocking_placements"]
    }
    assert str(placement_id) in blocking_ids

    with factory() as session:
        stored = session.scalar(
            select(InventoryPlacement).where(InventoryPlacement.id == placement_id)
        )
        assert stored is not None
        stored.quantity = Decimal("0")
        session.commit()

    retired = client.post(
        f"/api/v1/warehouse/shelves/{shelf['id']}/retire",
        json={"version": shelf["version"]},
        headers=_bearer(token),
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["is_active"] is False


@requires_db
def test_retire_warehouse_blocked_by_any_shelf_stock(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    workplace = _workplace_id(factory, "SP")
    code = f"WH-{_unique_tag()}"
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={"workplace_id": str(workplace), "code": code, "name": "A", "name_fa": "الف"},
        headers=_bearer(token),
    ).json()
    shelf = client.post(
        f"/api/v1/warehouse/warehouses/{warehouse['id']}/shelves",
        json={"code": "B-01"},
        headers=_bearer(token),
    ).json()

    with factory() as session:
        stored_shelf = session.scalar(select(Shelf).where(Shelf.id == uuid.UUID(shelf["id"])))
        stored_warehouse = session.scalar(
            select(Warehouse).where(Warehouse.id == uuid.UUID(warehouse["id"]))
        )
        assert stored_shelf is not None and stored_warehouse is not None
        _seed_stock(factory, stored_warehouse, stored_shelf, quantity="2.000")

    blocked = client.post(
        f"/api/v1/warehouse/warehouses/{warehouse['id']}/retire",
        json={"version": warehouse["version"]},
        headers=_bearer(token),
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "BUSINESS_RULE_VIOLATION"


@requires_db
def test_workplace_scoped_keeper_sees_only_own_warehouse(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    admin_token = _admin_token(client)
    cp1 = _workplace_id(factory, "CP1")
    sp = _workplace_id(factory, "SP")
    own = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": str(cp1),
            "code": f"WH-{_unique_tag()}",
            "name": "Own",
            "name_fa": "خود",
        },
        headers=_bearer(admin_token),
    ).json()
    other = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": str(sp),
            "code": f"WH-{_unique_tag()}",
            "name": "Other",
            "name_fa": "دیگر",
        },
        headers=_bearer(admin_token),
    ).json()

    keeper_token = _scoped_keeper_token(client, factory, "scope", cp1)
    listing = client.get(
        "/api/v1/warehouse/warehouses",
        params={"workplace_id": str(cp1), "page_size": 100},
        headers=_bearer(keeper_token),
    )
    assert listing.status_code == 200, listing.text
    ids = [item["id"] for item in listing.json()["items"]]
    assert own["id"] in ids
    assert other["id"] not in ids

    full_listing = client.get(
        "/api/v1/warehouse/warehouses", params={"page_size": 100}, headers=_bearer(keeper_token)
    )
    all_ids = [item["id"] for item in full_listing.json()["items"]]
    assert other["id"] not in all_ids

    denied = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": str(sp),
            "code": f"WH-{_unique_tag()}",
            "name": "X",
            "name_fa": "س",
        },
        headers=_bearer(keeper_token),
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "AUTHORIZATION_DENIED"


@requires_db
def test_warehouse_update_stale_version(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    workplace = _workplace_id(factory, "CP1")
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": str(workplace),
            "code": f"WH-{_unique_tag()}",
            "name": "A",
            "name_fa": "الف",
        },
        headers=_bearer(token),
    ).json()
    stale = client.patch(
        f"/api/v1/warehouse/warehouses/{warehouse['id']}",
        json={"name": "Renamed", "version": warehouse["version"] + 3},
        headers=_bearer(token),
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_VERSION"
