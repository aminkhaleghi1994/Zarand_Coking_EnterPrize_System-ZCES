"""Dashboard endpoint tests (Phase 9, T008-T009): contract aggregation,
scope filtering (global vs workplace), permission gates."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.main import create_app
from app.modules.user.models import (
    Permission,
    Role,
    RolePermission,
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
    reason="dashboard tests require real PostgreSQL",
)

_DASHBOARD_PERMS = [
    "reports:dashboard:read",
    "user:employee:read",
    "warehouse:request:read",
    "warehouse:alert:read",
    "warehouse:stock:read",
    "warehouse:item:read",
    "loan:request:read",
]


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
        json={
            "email": settings.INITIAL_ADMIN_EMAIL,
            "password": settings.INITIAL_ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_scoped_manager(factory, tag: str) -> str:  # type: ignore[no-untyped-def]
    """A user holding the dashboard permission with a workplace-level scope
    (CP1 only) — everything they see must be CP1-bounded."""
    from app.core.security import hash_password

    with factory() as session:
        existing = session.scalar(
            select(User).where(User.email == f"mgr-{tag}@zarandsteel.ir")
        )
        if existing is None:
            user = User(
                email=f"mgr-{tag}@zarandsteel.ir",
                username=f"mgr-{tag}",
                hashed_password=hash_password("manager-password-1"),
            )
            session.add(user)
            session.flush()

            role = Role(name=f"DashboardManager-{tag}", description="")
            session.add(role)
            session.flush()

            cp1 = session.scalar(select(Workplace).where(Workplace.code == "CP1"))
            assert cp1 is not None
            for code in _DASHBOARD_PERMS:
                permission = session.scalar(
                    select(Permission).where(Permission.code == code)
                )
                assert permission is not None, code
                session.add(RolePermission(role_id=role.id, permission_id=permission.id))
                module, resource, operation = code.split(":", 2)
                session.add(
                    ScopeAssignment(
                        user_id=user.id,
                        level=ScopeLevel.WORKPLACE,
                        module=module,
                        resource=resource,
                        operation=operation,
                        workplace_id=cp1.id,
                    )
                )
            session.add(UserRole(user_id=user.id, role_id=role.id))
            session.commit()
    return f"mgr-{tag}@zarandsteel.ir"


def _create_employee(client: TestClient, token: str, tag: str) -> str:  # type: ignore[no-untyped-def]
    """Create one CP1 employee via the API so counters are deterministic
    (the scratch seed has zero employees — the admin is a bootstrap identity)."""
    workplaces = client.get(
        "/api/v1/org/workplaces?page_size=50", headers=_bearer(token)
    )
    cp1 = next(
        item for item in workplaces.json()["items"] if item["code"] == "CP1"
    )
    ni = str(uuid.uuid4().int)[:10]  # digits only — matches ^\d{10}$
    created = client.post(
        "/api/v1/employees",
        json={
            "national_id": ni,
            "personnel_code": f"RP-{tag}",
            "first_name": "Report",
            "last_name": "Employee",
            "workplace_id": cp1["id"],
            "user": {
                "email": f"report-emp-{tag}@zarandsteel.ir",
                "username": f"reportemp{tag}",
                "password": "report-password-1",
            },
        },
        headers=_bearer(token),
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


@requires_db
def test_dashboard_counters_match_seeded_data(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    _create_employee(client, token, uuid.uuid4().hex[:6])
    response = client.get("/api/v1/reports/dashboard", headers=_bearer(token))
    assert response.status_code == 200, response.text
    body = response.json()
    counters = body["counters"]
    assert counters["active_employees"] >= 1
    assert counters["catalog_items"] >= 0
    assert set(body["item_requests_by_status"]) == {
        "pending",
        "approved",
        "rejected",
        "fulfilled",
    }
    assert set(body["loans_by_status"]) == {
        "pending",
        "active",
        "settled",
        "cancelled",
    }
    assert isinstance(body["low_stock_alerts_by_warehouse"], list)


@requires_db
def test_dashboard_workplace_scope_shrinks_counts(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    admin_token = _admin_token(client)
    _create_employee(client, admin_token, uuid.uuid4().hex[:6])
    admin = client.get(
        "/api/v1/reports/dashboard", headers=_bearer(admin_token)
    ).json()
    global_employees = admin["counters"]["active_employees"]
    assert global_employees >= 1

    tag = uuid.uuid4().hex[:6]
    email = _make_scoped_manager(factory, tag)
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "manager-password-1"}
    )
    assert login.status_code == 200, login.text

    scoped = client.get(
        "/api/v1/reports/dashboard", headers=_bearer(login.json()["access_token"])
    )
    assert scoped.status_code == 200, scoped.text
    scoped_employees = scoped.json()["counters"]["active_employees"]

    # CP1 coverage counts the CP1 employees but can never exceed the
    # global count (constitution II); at least one CP1 employee exists.
    assert 1 <= scoped_employees <= global_employees


@requires_db
def test_dashboard_requires_permission(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    unauthenticated = client.get("/api/v1/reports/dashboard")
    assert unauthenticated.status_code == 401

    tag = uuid.uuid4().hex[:6]
    from app.core.security import hash_password

    with pg[1]() as session:
        user = User(
            email=f"plain-{tag}@zarandsteel.ir",
            username=f"plain-{tag}",
            hashed_password=hash_password("plain-password-1"),
        )
        session.add(user)
        session.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": f"plain-{tag}@zarandsteel.ir", "password": "plain-password-1"},
    )
    assert login.status_code == 200
    denied = client.get(
        "/api/v1/reports/dashboard", headers=_bearer(login.json()["access_token"])
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "AUTHORIZATION_DENIED"
