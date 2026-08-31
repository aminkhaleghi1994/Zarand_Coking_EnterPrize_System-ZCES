import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.core.security import hash_password
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.user.models import Role, User, UserRole
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


def _item_payload(tag: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": f"Ball bearing {tag}",
        "name_fa": f"بلبرینگ {tag}",
        "code": f"BB-{tag}",
        "unit": "ad",
        "min_quantity": "10.000",
    }
    payload.update(overrides)
    return payload


def _create_user_with_role(
    factory,
    tag: str,
    role_name: str | None,  # type: ignore[no-untyped-def]
) -> tuple[str, str]:
    """Create a user (optionally with a role), return (email, password)."""
    email = f"wh-{_RUN}-{tag}@zarandsteel.ir"
    password = "wh-password-1"
    with factory() as session:
        user = User(
            email=email,
            username=f"wh-{_RUN}-{tag}",
            hashed_password=hash_password(password),
            is_active=True,
        )
        session.add(user)
        session.flush()
        if role_name is not None:
            role = session.scalar(select(Role).where(Role.name == role_name))
            assert role is not None
            session.add(UserRole(user_id=user.id, role_id=role.id))
        session.commit()
    return email, password


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@requires_db
def test_create_item_201_shape(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    tag = _unique_tag()
    response = client.post(
        "/api/v1/warehouse/items", json=_item_payload(tag), headers=_bearer(token)
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == f"Ball bearing {tag}"
    assert body["code"] == f"BB-{tag}"
    assert body["min_quantity"] == "10.000"
    assert body["is_active"] is True
    assert body["version"] == 1


@requires_db
def test_duplicate_name_rejected_case_and_whitespace_variants(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    tag = _unique_tag()
    first = client.post("/api/v1/warehouse/items", json=_item_payload(tag), headers=_bearer(token))
    assert first.status_code == 201, first.text

    for variant in (f"ball BEARING {tag}", f"  ball bearing {tag}  "):
        duplicate = client.post(
            "/api/v1/warehouse/items",
            json=_item_payload(tag, name=variant),
            headers=_bearer(token),
        )
        assert duplicate.status_code == 409, duplicate.text
        assert duplicate.json()["code"] == "DUPLICATE_RESOURCE"


@requires_db
def test_duplicate_code_rejected(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    tag = _unique_tag()
    first = client.post("/api/v1/warehouse/items", json=_item_payload(tag), headers=_bearer(token))
    assert first.status_code == 201, first.text
    duplicate = client.post(
        "/api/v1/warehouse/items",
        json=_item_payload(f"{tag}-other", code=f"bb-{tag}"),
        headers=_bearer(token),
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "DUPLICATE_RESOURCE"


@requires_db
def test_update_version_conflict_then_success(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    tag = _unique_tag()
    created = client.post(
        "/api/v1/warehouse/items", json=_item_payload(tag), headers=_bearer(token)
    ).json()

    stale = client.patch(
        f"/api/v1/warehouse/items/{created['id']}",
        json={"min_quantity": "5.000", "version": created["version"] + 5},
        headers=_bearer(token),
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_VERSION"

    updated = client.patch(
        f"/api/v1/warehouse/items/{created['id']}",
        json={"min_quantity": "5.000", "description": "counted", "version": created["version"]},
        headers=_bearer(token),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["min_quantity"] == "5.000"
    assert updated.json()["version"] == created["version"] + 1


@requires_db
def test_retire_is_idempotent_and_name_reusable(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    tag = _unique_tag()
    created = client.post(
        "/api/v1/warehouse/items", json=_item_payload(tag), headers=_bearer(token)
    ).json()

    retired = client.post(
        f"/api/v1/warehouse/items/{created['id']}/retire",
        json={"version": created["version"]},
        headers=_bearer(token),
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["is_active"] is False

    again = client.post(
        f"/api/v1/warehouse/items/{created['id']}/retire",
        json={"version": retired.json()["version"]},
        headers=_bearer(token),
    )
    assert again.status_code == 200, again.text

    reused = client.post("/api/v1/warehouse/items", json=_item_payload(tag), headers=_bearer(token))
    assert reused.status_code == 201, reused.text


@requires_db
def test_search_endpoint_case_insensitive(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    tag = _unique_tag()
    created = client.post(
        "/api/v1/warehouse/items", json=_item_payload(tag), headers=_bearer(token)
    ).json()
    response = client.get(
        "/api/v1/warehouse/items",
        params={"search": f"BEARING {tag}".upper()},
        headers=_bearer(token),
    )
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert created["id"] in ids


@requires_db
def test_roleless_user_gets_403(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    email, password = _create_user_with_role(factory, "roleless", None)
    token = _login(client, email, password)
    response = client.post(
        "/api/v1/warehouse/items",
        json=_item_payload(_unique_tag()),
        headers=_bearer(token),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "AUTHORIZATION_DENIED"


@requires_db
def test_keeper_without_scope_gets_403_on_catalog_write(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    email, password = _create_user_with_role(factory, "keeper-noscope", "WarehouseKeeper")
    token = _login(client, email, password)
    response = client.post(
        "/api/v1/warehouse/items",
        json=_item_payload(_unique_tag()),
        headers=_bearer(token),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "AUTHORIZATION_DENIED"


@requires_db
def test_item_created_audit_written(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    tag = _unique_tag()
    created = client.post(
        "/api/v1/warehouse/items", json=_item_payload(tag), headers=_bearer(token)
    ).json()
    with factory() as session:
        entry = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "ITEM_CREATED", AuditLog.entity_id == uuid.UUID(created["id"])
            )
        )
    assert entry is not None
    assert entry.after_snapshot is not None
    assert entry.after_snapshot["name"] == f"Ball bearing {tag}"
