import os
import uuid
from threading import Thread

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.core.errors import STALE_VERSION
from app.core.security import hash_password
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.user.models import (
    Employee,
    Role,
    ScopeAssignment,
    ScopeLevel,
    User,
    UserRole,
    Workplace,
)
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="asset integration tests require a real database (PG service in CI)",
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


def _register(client: TestClient, token: str, serial: str, **overrides: object) -> object:
    payload: dict[str, object] = {
        "name": f"Asset {_unique_tag()}",
        "name_fa": f"دارایی {_unique_tag()}",
        "serial": serial,
    }
    payload.update(overrides)
    return client.post("/api/v1/warehouse/assets", json=payload, headers=_bearer(token))


def _create_employee_via_api(client: TestClient, token: str, workplace_code: str, tag: str) -> str:
    workplaces = client.get(
        "/api/v1/org/workplaces", params={"page_size": 50}, headers=_bearer(token)
    ).json()["items"]
    workplace = next(w for w in workplaces if w["code"] == workplace_code)
    national_id = f"8{uuid.uuid4().int % 10**9:09d}"[:10]
    created = client.post(
        "/api/v1/employees",
        json={
            "national_id": national_id,
            "personnel_code": f"AST-{_unique_tag()}",
            "first_name": "Asset",
            "last_name": f"Holder {tag}",
            "workplace_id": workplace["id"],
            "user": {
                "email": f"ast-{_RUN}-{tag}@zarandsteel.ir",
                "username": f"ast-{_RUN}-{tag}",
                "password": "ast-password-1",
            },
        },
        headers=_bearer(token),
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _deactivate_employee(client: TestClient, token: str, employee_id: str) -> None:
    detail = client.get(f"/api/v1/employees/{employee_id}", headers=_bearer(token)).json()
    response = client.post(
        f"/api/v1/employees/{employee_id}/deactivate",
        json={"version": detail["version"]},
        headers=_bearer(token),
    )
    assert response.status_code == 200, response.text


def _create_anchored_creator(
    client: TestClient,
    factory,
    workplace_code: str,
    tag: str,  # type: ignore[no-untyped-def]
) -> str:
    """User + employee (anchored) with the full asset permission set scoped
    to the workplace â€” used to create anchored assets and test scope purity."""
    email = f"asset-owner-{_RUN}-{tag}@zarandsteel.ir"
    with factory() as session:
        workplace = session.scalar(select(Workplace).where(Workplace.code == workplace_code))
        assert workplace is not None
        user = User(
            email=email,
            username=f"asset-owner-{_RUN}-{tag}",
            hashed_password=hash_password("asset-password-1"),
            is_active=True,
        )
        session.add(user)
        session.flush()
        employee = Employee(
            workplace_id=workplace.id,
            national_id=f"7{uuid.uuid4().int % 10**9:09d}"[:10],
            personnel_code=f"OWN-{_unique_tag()}",
            first_name="Asset",
            last_name=f"Owner {tag}",
            is_active=True,
        )
        session.add(employee)
        session.flush()
        user.employee_id = employee.id
        session.flush()
        role = session.scalar(select(Role).where(Role.name == "WarehouseKeeper"))
        assert role is not None
        session.add(UserRole(user_id=user.id, role_id=role.id))
        session.flush()
        for code in (
            "warehouse:asset:create",
            "warehouse:asset:read",
            "warehouse:asset:update",
            "warehouse:asset:retire",
            "warehouse:asset:assign",
            "warehouse:asset:return",
        ):
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
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "asset-password-1"}
    ).json()["access_token"]
    return token


@requires_db
def test_register_and_duplicate_serial_variants(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    serial = f"TW-{_unique_tag()}"

    created = _register(client, token, serial)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "available"
    assert body["holder"]["type"] == "available"

    for variant in (serial.lower(), f"  {serial}  "):
        duplicate = _register(client, token, variant)
        assert duplicate.status_code == 409, duplicate.text
        assert duplicate.json()["code"] == "DUPLICATE_RESOURCE"

    with factory() as session:
        entry = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "ASSET_CREATED",
                AuditLog.entity_id == uuid.UUID(body["id"]),
            )
        )
    assert entry is not None


@requires_db
def test_update_and_serial_editable(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    serial = f"TW-{_unique_tag()}"
    created = _register(client, token, serial).json()

    stale = client.patch(
        f"/api/v1/warehouse/assets/{created['id']}",
        json={"description": "x", "version": created["version"] + 3},
        headers=_bearer(token),
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_VERSION"

    updated = client.patch(
        f"/api/v1/warehouse/assets/{created['id']}",
        json={"description": "calibrated", "version": created["version"]},
        headers=_bearer(token),
    )
    assert updated.status_code == 200, updated.text

    # serial edit to a free serial succeeds (FR-003); stored value is stripped
    new_serial = f"TW-{_unique_tag()}-R"
    serial_change = client.patch(
        f"/api/v1/warehouse/assets/{created['id']}",
        json={"serial": f"  {new_serial}  ", "version": updated.json()["version"]},
        headers=_bearer(token),
    )
    assert serial_change.status_code == 200, serial_change.text
    assert serial_change.json()["serial"] == new_serial

    # case/whitespace-normalized: editing to the same normalized serial is a no-op
    same = client.patch(
        f"/api/v1/warehouse/assets/{created['id']}",
        json={"serial": new_serial.upper(), "version": serial_change.json()["version"]},
        headers=_bearer(token),
    )
    assert same.status_code == 200, same.text

    # collision with another active asset is refused (FR-002)
    other = _register(client, token, f"TW-{_unique_tag()}").json()
    collision = client.patch(
        f"/api/v1/warehouse/assets/{created['id']}",
        json={"serial": other["serial"], "version": same.json()["version"]},
        headers=_bearer(token),
    )
    assert collision.status_code == 409
    assert collision.json()["code"] == "DUPLICATE_RESOURCE"

    # a freed serial can be taken again: retire, then register the same serial
    retired = client.post(
        f"/api/v1/warehouse/assets/{created['id']}/retire",
        json={"version": same.json()["version"]},
        headers=_bearer(token),
    )
    assert retired.status_code == 200, retired.text
    reuse = _register(client, token, new_serial)
    assert reuse.status_code == 201, reuse.text


@requires_db
def test_assign_location_and_return(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    serial = f"TW-{_unique_tag()}"
    created = _register(client, token, serial).json()

    assigned = client.post(
        f"/api/v1/warehouse/assets/{created['id']}/assign",
        json={
            "version": created["version"],
            "target_type": "location",
            "location": "Tool crib shelf 2",
            "note": "night shift",
        },
        headers=_bearer(token),
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status"] == "assigned"
    assert assigned.json()["holder"]["type"] == "location"
    assert assigned.json()["holder"]["location"] == "Tool crib shelf 2"

    history = client.get(
        f"/api/v1/warehouse/assets/{created['id']}/history", headers=_bearer(token)
    ).json()
    assert [entry["action"] for entry in history["items"]] == ["assigned", "created"]
    assert history["items"][0]["to_holder"]["location"] == "Tool crib shelf 2"

    returned = client.post(
        f"/api/v1/warehouse/assets/{created['id']}/return",
        json={"version": assigned.json()["version"], "note": "shift ended"},
        headers=_bearer(token),
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["status"] == "available"

    refused = client.post(
        f"/api/v1/warehouse/assets/{created['id']}/return",
        json={"version": returned.json()["version"]},
        headers=_bearer(token),
    )
    assert refused.status_code == 422
    assert refused.json()["code"] == "BUSINESS_RULE_VIOLATION"


@requires_db
def test_assign_employee_already_assigned_and_deactivated(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    employee_id = _create_employee_via_api(client, token, "CP1", "assignee")
    serial = f"TW-{_unique_tag()}"
    created = _register(client, token, serial).json()

    assigned = client.post(
        f"/api/v1/warehouse/assets/{created['id']}/assign",
        json={"version": created["version"], "target_type": "employee", "employee_id": employee_id},
        headers=_bearer(token),
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["holder"]["employee"]["id"] == employee_id

    second = client.post(
        f"/api/v1/warehouse/assets/{created['id']}/assign",
        json={
            "version": assigned.json()["version"],
            "target_type": "employee",
            "employee_id": employee_id,
        },
        headers=_bearer(token),
    )
    assert second.status_code == 422
    assert second.json()["code"] == "BUSINESS_RULE_VIOLATION"

    serial_two = f"TW-{_unique_tag()}"
    other = _register(client, token, serial_two).json()
    _deactivate_employee(client, token, employee_id)
    deactivated = client.post(
        f"/api/v1/warehouse/assets/{other['id']}/assign",
        json={"version": other["version"], "target_type": "employee", "employee_id": employee_id},
        headers=_bearer(token),
    )
    assert deactivated.status_code == 422


@requires_db
def test_retire_blocked_while_assigned_then_serial_reuse(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    serial = f"TW-{_unique_tag()}"
    created = _register(client, token, serial).json()
    employee_id = _create_employee_via_api(client, token, "CP1", "blocker")
    client.post(
        f"/api/v1/warehouse/assets/{created['id']}/assign",
        json={"version": created["version"], "target_type": "employee", "employee_id": employee_id},
        headers=_bearer(token),
    )

    blocked = client.post(
        f"/api/v1/warehouse/assets/{created['id']}/retire",
        json={"version": created["version"] + 1},
        headers=_bearer(token),
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "BUSINESS_RULE_VIOLATION"

    returned = client.post(
        f"/api/v1/warehouse/assets/{created['id']}/return",
        json={"version": created["version"] + 1},
        headers=_bearer(token),
    )
    assert returned.status_code == 200, returned.text

    retired = client.post(
        f"/api/v1/warehouse/assets/{created['id']}/retire",
        json={"version": returned.json()["version"]},
        headers=_bearer(token),
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["status"] == "retired"

    reused = _register(client, token, serial)
    assert reused.status_code == 201, reused.text


@requires_db
def test_concurrent_assignments_one_winner(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    serial = f"TW-{_unique_tag()}"
    created = _register(client, token=_admin_token(client), serial=serial).json()
    employee_id = _create_employee_via_api(client, _admin_token(client), "CP1", "racer")

    outcomes: list[str] = []

    def assign_once() -> None:
        response = client.post(
            f"/api/v1/warehouse/assets/{created['id']}/assign",
            json={
                "version": created["version"],
                "target_type": "employee",
                "employee_id": employee_id,
            },
            headers=_bearer(_admin_token(client)),
        )
        if response.status_code == 200:
            outcomes.append("ok")
        elif response.json().get("code") == STALE_VERSION:
            outcomes.append(STALE_VERSION)
        else:
            outcomes.append(response.json().get("code", "unknown"))

    thread_a = Thread(target=assign_once)
    thread_b = Thread(target=assign_once)
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    assert outcomes.count("ok") == 1, f"outcomes={outcomes}"
    assert outcomes.count(STALE_VERSION) == 1, f"outcomes={outcomes}"


@requires_db
def test_scope_purity_and_history_visibility(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    cp1_token = _create_anchored_creator(client, factory, "CP1", "cp1")
    sp_token = _create_anchored_creator(client, factory, "SP", "sp")

    cp1_asset = _register(client, cp1_token, f"TW-{_unique_tag()}").json()
    sp_asset = _register(client, sp_token, f"TW-{_unique_tag()}").json()

    cp1_list = client.get(
        "/api/v1/warehouse/assets", params={"page_size": 100}, headers=_bearer(cp1_token)
    )
    assert cp1_list.status_code == 200
    ids = {item["id"] for item in cp1_list.json()["items"]}
    assert cp1_asset["id"] in ids
    assert sp_asset["id"] not in ids

    denied = client.get(f"/api/v1/warehouse/assets/{sp_asset['id']}", headers=_bearer(cp1_token))
    assert denied.status_code == 403
    assert denied.json()["code"] == "AUTHORIZATION_DENIED"

    history = client.get(
        f"/api/v1/warehouse/assets/{cp1_asset['id']}/history", headers=_bearer(cp1_token)
    )
    assert history.status_code == 200
    actions = [entry["action"] for entry in history.json()["items"]]
    assert actions == ["created"]
