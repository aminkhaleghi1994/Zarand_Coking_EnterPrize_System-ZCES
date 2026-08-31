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
    reason="item-request integration tests require a real database (PG service in CI)",
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
            "name": f"Request item {tag}",
            "name_fa": f"کالای درخواست {tag}",
            "code": f"RQ-{tag}",
            "unit": "ad",
            "min_quantity": "0",
        },
        headers=_bearer(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _request_payload(item_ids: list[str], **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "purpose_description": f"Purpose {_unique_tag()}",
        "lines": [{"item_id": item_id, "quantity": "2.000"} for item_id in item_ids],
    }
    payload.update(overrides)
    return payload


def _create_employee_user(
    factory,
    workplace_code: str,
    tag: str,  # type: ignore[no-untyped-def]
) -> tuple[str, str]:
    """Direct-insert an employee + user anchored to the workplace."""
    email = f"req-{_RUN}-{tag}@zarandsteel.ir"
    password = "req-password-1"
    with factory() as session:
        workplace = session.scalar(select(Workplace).where(Workplace.code == workplace_code))
        assert workplace is not None
        user = User(
            email=email,
            username=f"req-{_RUN}-{tag}",
            hashed_password=hash_password(password),
            is_active=True,
        )
        session.add(user)
        session.flush()
        employee = Employee(
            workplace_id=workplace.id,
            national_id=f"9{uuid.uuid4().int % 10**9:09d}"[:10],
            personnel_code=f"REQ-{_unique_tag()}",
            first_name="Requester",
            last_name=tag,
            is_active=True,
        )
        session.add(employee)
        session.flush()
        user.employee_id = employee.id
        session.commit()
    return email, password


def _scoped_keeper_token(
    client: TestClient,
    factory,
    tag: str,
    workplace_id: uuid.UUID,  # type: ignore[no-untyped-def]
) -> str:
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
        role = session.scalar(select(Role).where(Role.name == "WarehouseApprover"))
        assert role is not None
        session.add(UserRole(user_id=user.id, role_id=role.id))
        session.flush()
        for code in ("warehouse:request:read", "warehouse:request:decide"):
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


@requires_db
def test_self_service_creation_and_validation(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    email, password = _create_employee_user(factory, "CP1", "compose")
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]

    item_a = _create_item(client, _admin_token(client), _unique_tag())
    item_b = _create_item(client, _admin_token(client), _unique_tag())

    created = client.post(
        "/api/v1/warehouse/requests",
        json=_request_payload([item_a, item_b]),
        headers=_bearer(token),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "pending"
    assert len(body["lines"]) == 2
    assert body["lines"][0]["quantity"] == "2.000"

    no_lines = client.post(
        "/api/v1/warehouse/requests",
        json={"purpose_description": "x", "lines": []},
        headers=_bearer(token),
    )
    assert no_lines.status_code == 422

    blank_purpose = client.post(
        "/api/v1/warehouse/requests",
        json=_request_payload([item_a], purpose_description="   "),
        headers=_bearer(token),
    )
    assert blank_purpose.status_code == 422

    zero_qty = client.post(
        "/api/v1/warehouse/requests",
        json=_request_payload([item_a], lines=[{"item_id": item_a, "quantity": "0"}]),
        headers=_bearer(token),
    )
    assert zero_qty.status_code == 422

    duplicate = client.post(
        "/api/v1/warehouse/requests",
        json=_request_payload(
            [item_a],
            lines=[
                {"item_id": item_a, "quantity": "1"},
                {"item_id": item_a, "quantity": "2"},
            ],
        ),
        headers=_bearer(token),
    )
    assert duplicate.status_code == 422

    retired_item = client.post(
        "/api/v1/warehouse/items",
        json={
            "name": f"Retired {_unique_tag()}",
            "name_fa": "بازنشسته",
            "unit": "ad",
        },
        headers=_bearer(_admin_token(client)),
    ).json()
    client.post(
        f"/api/v1/warehouse/items/{retired_item['id']}/retire",
        json={"version": retired_item["version"]},
        headers=_bearer(_admin_token(client)),
    )
    retired_line = client.post(
        "/api/v1/warehouse/requests",
        json=_request_payload([retired_item["id"]]),
        headers=_bearer(token),
    )
    assert retired_line.status_code == 422

    with factory() as session:
        entries = session.scalars(
            select(AuditLog).where(AuditLog.action == "REQUEST_CREATED")
        ).all()
    assert any(
        entry.after_snapshot is not None and len(entry.after_snapshot.get("lines", [])) == 2
        for entry in entries
    )


@requires_db
def test_requester_anchored_to_workplace_and_scope_visibility(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    admin_token = _admin_token(client)

    cp1_email, cp1_password = _create_employee_user(factory, "CP1", "anchor-cp1")
    sp_email, sp_password = _create_employee_user(factory, "SP", "anchor-sp")
    cp1_token = client.post(
        "/api/v1/auth/login", json={"email": cp1_email, "password": cp1_password}
    ).json()["access_token"]
    sp_token = client.post(
        "/api/v1/auth/login", json={"email": sp_email, "password": sp_password}
    ).json()["access_token"]

    item_a = _create_item(client, admin_token, _unique_tag())
    item_b = _create_item(client, admin_token, _unique_tag())

    cp1_request = client.post(
        "/api/v1/warehouse/requests",
        json=_request_payload([item_a]),
        headers=_bearer(cp1_token),
    ).json()
    sp_request = client.post(
        "/api/v1/warehouse/requests",
        json=_request_payload([item_b]),
        headers=_bearer(sp_token),
    ).json()

    with factory() as session:
        workplace = session.scalar(select(Workplace).where(Workplace.code == "CP1"))
        assert workplace is not None
        cp1_id = workplace.id
    assert cp1_request  # anchored implicitly via requester employee

    keeper_token = _scoped_keeper_token(client, factory, "vis", cp1_id)
    keeper_list = client.get(
        "/api/v1/warehouse/requests", params={"page_size": 100}, headers=_bearer(keeper_token)
    )
    assert keeper_list.status_code == 200
    keeper_ids = {item["id"] for item in keeper_list.json()["items"]}
    assert cp1_request["id"] in keeper_ids
    assert sp_request["id"] not in keeper_ids

    cp1_list = client.get(
        "/api/v1/warehouse/requests", params={"page_size": 100}, headers=_bearer(cp1_token)
    )
    cp1_ids = {item["id"] for item in cp1_list.json()["items"]}
    assert cp1_request["id"] in cp1_ids
    assert sp_request["id"] not in cp1_ids

    sp_detail = client.get(
        f"/api/v1/warehouse/requests/{sp_request['id']}", headers=_bearer(cp1_token)
    )
    assert sp_detail.status_code == 403
    assert sp_detail.json()["code"] == "AUTHORIZATION_DENIED"

    admin_list = client.get(
        "/api/v1/warehouse/requests", params={"page_size": 100}, headers=_bearer(admin_token)
    )
    admin_ids = {item["id"] for item in admin_list.json()["items"]}
    assert {cp1_request["id"], sp_request["id"]} <= admin_ids


@requires_db
def test_decide_guards_and_version_race(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    admin_token = _admin_token(client)
    item_a = _create_item(client, admin_token, _unique_tag())

    first = client.post(
        "/api/v1/warehouse/requests",
        json=_request_payload([item_a]),
        headers=_bearer(admin_token),
    ).json()
    second = client.post(
        "/api/v1/warehouse/requests",
        json=_request_payload([item_a]),
        headers=_bearer(admin_token),
    ).json()

    approved = client.post(
        f"/api/v1/warehouse/requests/{first['id']}/approve",
        json={"version": first["version"], "note": "ok"},
        headers=_bearer(admin_token),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    re_decide = client.post(
        f"/api/v1/warehouse/requests/{first['id']}/reject",
        json={"version": approved.json()["version"]},
        headers=_bearer(admin_token),
    )
    assert re_decide.status_code == 422
    assert re_decide.json()["code"] == "BUSINESS_RULE_VIOLATION"

    rejected = client.post(
        f"/api/v1/warehouse/requests/{second['id']}/reject",
        json={"version": second["version"], "note": "not needed"},
        headers=_bearer(admin_token),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    outcomes: list[str] = []

    def decide_later(token: str, version: int) -> None:
        response = client.post(
            f"/api/v1/warehouse/requests/{stale_request['id']}/reject",
            json={"version": version},
            headers=_bearer(token),
        )
        if response.status_code == 200:
            outcomes.append("ok")
        elif response.json().get("code") == STALE_VERSION:
            outcomes.append(STALE_VERSION)
        else:
            outcomes.append(response.json().get("code", "unknown"))

    stale_request = client.post(
        "/api/v1/warehouse/requests",
        json=_request_payload([item_a]),
        headers=_bearer(admin_token),
    ).json()
    thread_a = Thread(
        target=decide_later,
        args=(_admin_token(client), stale_request["version"]),
    )
    thread_b = Thread(
        target=decide_later,
        args=(_admin_token(client), stale_request["version"]),
    )
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()
    assert outcomes.count("ok") == 1, f"outcomes={outcomes}"
    assert outcomes.count(STALE_VERSION) == 1, f"outcomes={outcomes}"


@requires_db
def test_request_status_filter(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    admin_token = _admin_token(client)
    item_a = _create_item(client, admin_token, _unique_tag())
    pending = client.post(
        "/api/v1/warehouse/requests",
        json=_request_payload([item_a]),
        headers=_bearer(admin_token),
    ).json()
    rejected = client.post(
        "/api/v1/warehouse/requests",
        json=_request_payload([item_a]),
        headers=_bearer(admin_token),
    ).json()
    client.post(
        f"/api/v1/warehouse/requests/{rejected['id']}/reject",
        json={"version": rejected["version"]},
        headers=_bearer(admin_token),
    )

    pending_list = client.get(
        "/api/v1/warehouse/requests",
        params={"status": "pending", "page_size": 100},
        headers=_bearer(admin_token),
    )
    ids = [item["id"] for item in pending_list.json()["items"]]
    assert pending["id"] in ids
    assert rejected["id"] not in ids
