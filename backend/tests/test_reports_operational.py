"""Operational report endpoint tests (Phase 9, T010-T013): scope filters,
below-min filter, status/date filters + counts, loan aggregates, audit
masking, permission gates."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, dispose_engine, init_engine
from app.main import create_app
from app.modules.user.models import User
from app.seeds.seed_dev import run_seed

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not _TEST_DATABASE_URL or _TEST_DATABASE_URL.startswith("sqlite"),
    reason="report tests require real PostgreSQL",
)

_REPORT_PERMS = [
    "reports:dashboard:read",
    "reports:inventory:read",
    "reports:request:read",
    "reports:loan:read",
    "reports:export:excel",
    "audit:log:read",
    "warehouse:stock:read",
    "warehouse:request:read",
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


def _unique() -> str:
    return uuid.uuid4().hex[:8]


def _setup_warehouse_stock(client: TestClient, token: str) -> dict:  # type: ignore[no-untyped-def]
    """Create warehouse + shelf + item + receive 5 + issue 4 (below min=10)."""
    unique = _unique()
    headers = _bearer(token)
    workplaces = client.get("/api/v1/org/workplaces?page_size=50", headers=headers)
    cp1 = next(w for w in workplaces.json()["items"] if w["code"] == "CP1")
    warehouse = client.post(
        "/api/v1/warehouse/warehouses",
        json={
            "workplace_id": cp1["id"],
            "code": f"WH-RPT-{unique}",
            "name": "Report WH",
            "name_fa": "انبار گزارش",
        },
        headers=headers,
    )
    shelf = client.post(
        f"/api/v1/warehouse/warehouses/{warehouse.json()['id']}/shelves",
        json={"code": "R-01"},
        headers=headers,
    )
    item = client.post(
        "/api/v1/warehouse/items",
        json={
            "name": f"Report item {unique}",
            "name_fa": f"کالای گزارش {unique}",
            "unit": "ad",
            "min_quantity": "10",
        },
        headers=headers,
    )
    receive = client.post(
        "/api/v1/warehouse/placements/receive",
        json={
            "item_id": item.json()["id"],
            "shelf_id": shelf.json()["id"],
            "quantity": "5",
            "reason": "report test",
        },
        headers=headers,
    )
    assert receive.status_code == 200, receive.text
    return {
        "warehouse_id": warehouse.json()["id"],
        "warehouse_code": warehouse.json()["code"],
        "item_id": item.json()["id"],
        "item_name": item.json()["name"],
        "placement_quantity": "5.000",
        "threshold": "10.000",
    }


# --- T010: inventory report ---


@requires_db
def test_inventory_report_scope_and_filters(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    stock = _setup_warehouse_stock(client, token)

    listed = client.get("/api/v1/reports/inventory", headers=_bearer(token))
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] >= 1
    mine = next(
        row for row in body["items"] if row["item_id"] == stock["item_id"]
    )
    assert mine["quantity"] == stock["placement_quantity"]
    assert mine["threshold"] == stock["threshold"]
    assert mine["below_min"] is True
    assert mine["warehouse_code"] == stock["warehouse_code"]

    below = client.get(
        "/api/v1/reports/inventory?below_min_only=true", headers=_bearer(token)
    )
    assert below.status_code == 200
    assert all(row["below_min"] for row in below.json()["items"])
    assert any(row["item_id"] == stock["item_id"] for row in below.json()["items"])

    by_warehouse = client.get(
        f"/api/v1/reports/inventory?warehouse_id={stock['warehouse_id']}",
        headers=_bearer(token),
    )
    assert by_warehouse.status_code == 200
    assert all(
        row["warehouse_code"] == stock["warehouse_code"]
        for row in by_warehouse.json()["items"]
    )


@requires_db
def test_inventory_report_requires_permission(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    unauthenticated = client.get("/api/v1/reports/inventory")
    assert unauthenticated.status_code == 401


# --- T011: requests report ---


@requires_db
def test_requests_report_filters_and_counts(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    headers = _bearer(token)
    unique = _unique()

    item = client.post(
        "/api/v1/warehouse/items",
        json={"name": f"Req report {unique}", "name_fa": "کالا", "unit": "ad", "min_quantity": "0"},
        headers=headers,
    )
    created = client.post(
        "/api/v1/warehouse/requests",
        json={
            "purpose_description": f"report request {unique}",
            "lines": [{"item_id": item.json()["id"], "quantity": "1"}],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]

    listed = client.get("/api/v1/reports/requests", headers=headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert set(body["status_counts"]) == {
        "pending",
        "approved",
        "rejected",
        "fulfilled",
    }
    mine = next(row for row in body["items"] if row["id"] == request_id)
    assert mine["status"] == "pending"
    assert mine["line_count"] == 1
    assert mine["purpose_description"] == f"report request {unique}"

    pending_only = client.get(
        "/api/v1/reports/requests?status=pending", headers=headers
    )
    assert pending_only.status_code == 200
    assert all(row["status"] == "pending" for row in pending_only.json()["items"])

    # date window excluding everything ("Z" suffix — a bare "+00:00" in a
    # URL query would be read as a space)
    far_past = (
        (datetime.now(tz=UTC) - timedelta(days=365))
        .isoformat()
        .replace("+00:00", "Z")
    )
    empty = client.get(
        f"/api/v1/reports/requests?date_from=2000-01-01T00:00:00Z&date_to={far_past}",
        headers=headers,
    )
    assert empty.status_code == 200
    assert empty.json()["total"] == 0
    assert empty.json()["items"] == []
    assert empty.json()["status_counts"] == {
        "pending": 0,
        "approved": 0,
        "rejected": 0,
        "fulfilled": 0,
    }


# --- T012: loans report ---


@requires_db
def test_loans_report_aggregates(pg):  # type: ignore[no-untyped-def]
    client, _factory = pg
    token = _admin_token(client)
    headers = _bearer(token)
    unique = _unique()

    workplaces = client.get("/api/v1/org/workplaces?page_size=50", headers=headers)
    cp1 = next(w for w in workplaces.json()["items"] if w["code"] == "CP1")

    ni = str(uuid.uuid4().int)[:10]
    employee = client.post(
        "/api/v1/employees",
        json={
            "national_id": ni,
            "personnel_code": f"LR-{unique}",
            "first_name": "Loan",
            "last_name": "Report",
            "workplace_id": cp1["id"],
            "user": {
                "email": f"loan-report-{unique}@zarandsteel.ir",
                "username": f"loanreport{unique}",
                "password": "loan-report-password-1",
            },
        },
        headers=headers,
    )
    assert employee.status_code == 201, employee.text
    emp_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"loan-report-{unique}@zarandsteel.ir",
            "password": "loan-report-password-1",
        },
    )
    emp_headers = _bearer(emp_login.json()["access_token"])

    from app.common.jalali import current_jalali_year

    year = current_jalali_year()

    # clean any active policy for (CP1, year)
    policies = client.get(f"/api/v1/loan/policies?year={year}", headers=headers)
    for policy in policies.json()["items"]:
        if policy["workplace"]["id"] == cp1["id"]:
            client.post(
                f"/api/v1/loan/policies/{policy['id']}/retire",
                json={"version": policy["version"]},
                headers=headers,
            )

    policy = client.post(
        "/api/v1/loan/policies",
        json={
            "workplace_id": cp1["id"],
            "year": year,
            "max_loan_amount": "100000000.00",
            "max_guarantee_amount": "50000000.00",
            "max_request_count_per_year": 20,
            "max_request_count_lifetime": 20,
        },
        headers=headers,
    )
    assert policy.status_code == 201, policy.text

    submitted = client.post(
        "/api/v1/loan/requests",
        json={"type": "loan", "amount": "40000000.00"},
        headers=emp_headers,
    )
    assert submitted.status_code == 201, submitted.text
    loan_id = submitted.json()["id"]
    activated = client.post(
        f"/api/v1/loan/requests/{loan_id}/activate",
        json={"version": submitted.json()["version"]},
        headers=headers,
    )
    assert activated.status_code == 200, activated.text

    report = client.get("/api/v1/reports/loans", headers=headers)
    assert report.status_code == 200, report.text
    rows = report.json()
    cp1_row = next(
        row
        for row in rows
        if row["workplace_id"] == cp1["id"] and row["year"] == year
    )
    assert cp1_row["requests_total"] >= 1
    assert cp1_row["requests_active"] >= 1
    assert cp1_row["active_loan_commitment"] == "40000000.00"
    assert cp1_row["policy_max_loan"] == "100000000.00"

    filtered = client.get(
        f"/api/v1/reports/loans?workplace_id={cp1['id']}&year={year}", headers=headers
    )
    assert filtered.status_code == 200
    assert all(
        row["workplace_id"] == cp1["id"] and row["year"] == year
        for row in filtered.json()
    )


# --- T013: audit report ---


@requires_db
def test_audit_report_filters_and_masking(pg):  # type: ignore[no-untyped-def]
    client, factory = pg
    token = _admin_token(client)
    headers = _bearer(token)

    # Produce a masked-sensitive audit row: an employee update snapshots
    # carry national_id (masked at write time by the standard masker).
    unique = _unique()
    ni = str(uuid.uuid4().int)[:10]
    workplaces = client.get("/api/v1/org/workplaces?page_size=50", headers=headers)
    cp1 = next(w for w in workplaces.json()["items"] if w["code"] == "CP1")
    employee = client.post(
        "/api/v1/employees",
        json={
            "national_id": ni,
            "personnel_code": f"AR-{unique}",
            "first_name": "Audit",
            "last_name": "Report",
            "workplace_id": cp1["id"],
            "user": {
                "email": f"audit-report-{unique}@zarandsteel.ir",
                "username": f"auditreport{unique}",
                "password": "audit-report-password-1",
            },
        },
        headers=headers,
    )
    assert employee.status_code == 201, employee.text

    # Admin (has audit:log:read_full via SuperAdmin) sees snapshot contents.
    listed = client.get("/api/v1/reports/audit", headers=headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] >= 1
    with_snapshots = [
        row for row in body["items"] if row["after_snapshot"] is not None
    ]
    assert with_snapshots  # read_full holder sees masked snapshots
    employee_row = next(
        row
        for row in body["items"]
        if row["entity_type"] == "employee" and row["action"] == "EMPLOYEE_CREATED"
    )
    # national_id is masked even for read_full holders (mask at write time)
    snapshot = employee_row["after_snapshot"] or {}
    assert "national_id" in snapshot
    assert snapshot["national_id"].startswith("***")

    # Masked user (audit:log:read only) gets null snapshots.
    from app.core.security import hash_password
    from app.modules.user.models import (
        Permission,
        Role,
        RolePermission,
        UserRole,
    )

    tag = uuid.uuid4().hex[:6]
    with factory() as session:
        user = User(
            email=f"auditor-{tag}@zarandsteel.ir",
            username=f"auditor{tag}",
            hashed_password=hash_password("auditor-password-1"),
        )
        session.add(user)
        session.flush()
        role = Role(name=f"AuditorMasked-{tag}", description="")
        session.add(role)
        session.flush()
        for code in ["audit:log:read", "reports:export:excel"]:
            permission = session.scalar(
                select(Permission).where(Permission.code == code)
            )
            session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        session.add(UserRole(user_id=user.id, role_id=role.id))
        session.commit()

    masked_login = client.post(
        "/api/v1/auth/login",
        json={"email": f"auditor-{tag}@zarandsteel.ir", "password": "auditor-password-1"},
    )
    masked_headers = _bearer(masked_login.json()["access_token"])
    masked_listed = client.get("/api/v1/reports/audit", headers=masked_headers)
    assert masked_listed.status_code == 200, masked_listed.text
    for row in masked_listed.json()["items"]:
        assert row["before_snapshot"] is None
        assert row["after_snapshot"] is None

    # Action filter narrows rows.
    only_settings = client.get(
        "/api/v1/reports/audit?action=SETTING_UPDATED", headers=headers
    )
    assert only_settings.status_code == 200
    assert all(
        row["action"] == "SETTING_UPDATED" for row in only_settings.json()["items"]
    )

    # Non-audit user is denied.
    plain_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"audit-report-{unique}@zarandsteel.ir",
            "password": "audit-report-password-1",
        },
    )
    denied = client.get(
        "/api/v1/reports/audit", headers=_bearer(plain_login.json()["access_token"])
    )
    assert denied.status_code == 403
